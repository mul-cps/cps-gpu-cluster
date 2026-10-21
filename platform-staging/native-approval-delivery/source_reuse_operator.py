"""Explicit Source SQL reuse executor; inert until independently pinned execution.

The immutable sealed capsule authenticates inputs, never physical authorization.
Both SQL boundaries freshly observe Kubernetes and hydrate the original capsule.
Callbacks never query Source/SQLite. Root must supply a separate read-only SA.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

DATABASE = '/data/control.sqlite'
RESERVATIONS_DATABASE = '/data/reservations.sqlite'


def require(value, message):
    if not value:
        raise ValueError(message)


def _guard():
    name = 'aborted_reuse_guard'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[name] = module
    return sys.modules[name]


def _sealed(core, reference):
    from cps_compute.immutable_configmap import resolve_immutable_configmap
    _, body = resolve_immutable_configmap(core, reference)
    require(type(body) is dict and set(body) == {'version', 'physical_plan', 'quiescence_plan', 'source'}
            and type(body['version']) is int and body['version'] == 1, 'Closed sealed operator capsule required')
    return body


def _hydrate(core, physical, evidence):
    from cps_compute.native_group_revision import _api_document
    g = _guard(); pinned = physical['capsule']
    require(type(pinned) is dict and set(pinned) == {'namespace', 'name', 'uid', 'data_sha256'},
            'Compact original abort capsule reference required')
    actual = _api_document(core, core.read_namespaced_config_map(pinned['name'], pinned['namespace'], _request_timeout=15))
    require(g.identity(actual) == ('v1', 'ConfigMap', pinned['namespace'], pinned['name'], pinned['uid'])
            and actual.get('immutable') is True and not actual.get('binaryData')
            and type(actual.get('data')) is dict and g.sha(actual['data']) == pinned['data_sha256']
            == physical['capsule_sha256'] == evidence['sha256'] and pinned['uid'] == evidence['identity'],
            'Actual original immutable abort capsule differs from independent evidence')
    result = copy.deepcopy(physical); result['capsule'] = actual
    return result


def _quiescence(plan, core, apps):
    from cps_compute.native_group_revision import _api_document
    g = _guard()
    require(type(plan) is dict and set(plan) == {'version', 'source_services', 'writer', 'binder'}
            and type(plan['version']) is int and plan['version'] == 1
            and type(plan['source_services']) is dict and set(plan['source_services']) == {'cps', 'cit'},
            'Closed explicit quiescence preimages required')
    for expected in plan['source_services'].values():
        m = expected['metadata']
        actual = _api_document(core, core.read_namespaced_service(m['name'], m['namespace'], _request_timeout=15))
        require(g.identity(actual) == g.identity(expected) and g.sha(actual['spec']) == g.sha(expected['spec'])
                and type(expected['spec'].get('selector')) is dict and expected['spec']['selector'],
                'Actual Source Service fence differs')
        endpoints = _api_document(core, core.read_namespaced_endpoints(m['name'], m['namespace'], _request_timeout=15))
        metadata = endpoints.get('metadata', {})
        require(endpoints.get('apiVersion') == 'v1' and endpoints.get('kind') == 'Endpoints'
                and metadata.get('namespace') == m['namespace'] and metadata.get('name') == m['name']
                and not metadata.get('deletionTimestamp') and type(endpoints.get('subsets', [])) is list,
                'Complete actual Source Endpoints required')
        require(all(type(subset) is dict and not subset.get('addresses') and not subset.get('notReadyAddresses')
                    for subset in endpoints.get('subsets', [])), 'Source fence has live endpoints')
    for key in ('writer', 'binder'):
        expected = plan[key]; m = expected['metadata']
        actual = _api_document(apps, apps.read_namespaced_deployment(m['name'], m['namespace'], _request_timeout=15))
        require(g.identity(actual) == g.identity(expected) and g.sha(actual['spec']) == g.sha(expected['spec']),
                'Actual paused writer or disabled Binder differs')
    require(type(plan['writer']['spec'].get('replicas')) is int and plan['writer']['spec']['replicas'] == 0,
            'Normal writer must remain paused')
    args = [arg for c in plan['binder']['spec']['template']['spec']['containers'] for arg in c.get('args', [])]
    require(args.count('--native-pending-coordinator-enabled=false') == 1
            and not any(a == '--native-pending-coordinator-enabled' or
                        (a.startswith('--native-pending-coordinator-enabled=') and a != '--native-pending-coordinator-enabled=false')
                        for a in args), 'Binder must remain explicitly disabled')
    return True


def _source_inputs(body, core, evidence):
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.policy import Policy
    from cps_compute.native_group_approvals import ApprovalSnapshot
    from cps_compute.native_groups import canonical_sha256
    from cps_compute.native_group_capture_protocol import json_document
    from cps_compute.native_registry_migration import _database
    s = body['source']; physical = body['physical_plan']
    require(type(s) is dict and set(s) == {'old_policy', 'policy', 'previous_node_configuration', 'node_configuration',
        'previous_revision', 'target_revision', 'actor', 'revision_rows_sha256', 'revision_rows_count',
        'audit_rows_sha256', 'audit_rows_count', 'head_rows', 'retained_target_document_sha256',
        'retained_target_document_bytes'}, 'Closed complete Source preimages required')
    old_policy, policy = Policy(s['old_policy']), Policy(s['policy'])
    old = NodeConfiguration.load(core, ImmutableConfigMapRef.from_dict(s['previous_node_configuration']), old_policy)
    target = NodeConfiguration.load(core, ImmutableConfigMapRef.from_dict(s['node_configuration']), policy)
    require(old is not None and target is not None and target.previous_configuration is not None
            and target.previous_configuration.reference.to_dict() == old.reference.to_dict()
            and canonical_sha256(physical['policy']) == canonical_sha256(old_policy.catalog)
            and canonical_sha256(physical['node_configuration']) == canonical_sha256(old.reference.to_dict())
            and physical['target_revision'] == s['target_revision'] and physical['target_policy_hash'] == policy.hash
            and canonical_sha256(body['quiescence_plan']['writer']) == canonical_sha256(physical['deployments']['writer']),
            'Exact authenticated previous/current Node and physical Source context required')
    # This is the only read-only Source capture; callbacks below never enter it.
    with _database(DATABASE, RESERVATIONS_DATABASE, write=False) as (db, schema):
        revisions = db.execute('SELECT revision,document FROM native_group_approval_revision ORDER BY revision').fetchall()
        heads = db.execute('SELECT id,revision FROM native_group_approval_head ORDER BY id').fetchall()
        audits = db.execute('SELECT seq,record FROM audit_record ORDER BY seq').fetchall()
        for table in ('reservation', 'reservation_binding'):
            require(db.execute('SELECT count(*) FROM '+schema+'.'+table).fetchone()[0] == 0,
                    'Actual Source reservations must be empty')
    require(type(s['revision_rows_count']) is int and len(revisions) == s['revision_rows_count']
            and canonical_sha256(revisions) == s['revision_rows_sha256']
            and type(s['audit_rows_count']) is int and len(audits) == s['audit_rows_count']
            and canonical_sha256(audits) == s['audit_rows_sha256']
            and canonical_sha256(heads) == canonical_sha256(s['head_rows']), 'Complete Source SQL preimages differ')
    rows = dict(revisions); retained = rows[s['target_revision']]; raw = retained.encode()
    require(type(s['retained_target_document_bytes']) is int and len(raw) == s['retained_target_document_bytes']
            and 'sha256:'+hashlib.sha256(raw).hexdigest() == s['retained_target_document_sha256'],
            'Original retained target document bytes differ')
    previous = ApprovalSnapshot.from_document(json_document(rows[s['previous_revision']]), old_policy, old.deployment,
        expected_revision=s['previous_revision'])
    current = ApprovalSnapshot.from_document(json_document(retained), policy, target.deployment,
        expected_revision=s['target_revision'])
    require(previous._document.decode() == rows[s['previous_revision']], 'Original previous Source bytes required')
    return dict(old_policy=old_policy, policy=policy, previous=previous, target=current, revision_rows=revisions,
        head_rows=heads, audit_rows=audits, retained_target_document=retained, abort_evidence=evidence, actor=s['actor'])


def execute(packet, reviewed_plan_sha256, *, core, apps, rbac, batch):
    """Execute with actual clients, never caller-supplied physical callbacks."""
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    from cps_compute.native_groups import canonical_sha256
    from cps_compute.native_registry_aborted_reuse import plan_aborted_policy_reuse, apply_aborted_policy_reuse
    require(type(packet) is dict and set(packet) == {'version', 'capsule_ref', 'abort_evidence'}
            and type(packet['version']) is int and packet['version'] == 1, 'Closed independently pinned input required')
    packet = copy.deepcopy(packet); reference = ImmutableConfigMapRef.from_dict(packet['capsule_ref'])
    require(reference.to_dict()['key'] == 'operator.json', 'Exact sealed operator payload required')
    body = _sealed(core, reference); evidence = packet['abort_evidence']
    require(type(evidence) is dict and set(evidence) == {'identity', 'sha256'}, 'Closed original abort descriptor required')
    _hydrate(core, body['physical_plan'], evidence)
    args = _source_inputs(body, core, evidence)
    plan = plan_aborted_policy_reuse(**args)
    require(type(reviewed_plan_sha256) is str and canonical_sha256(plan) == reviewed_plan_sha256,
            'Exact independently reviewed SQL reuse plan required')
    def fresh():
        current = _sealed(core, reference)
        require(canonical_sha256(current) == canonical_sha256(body), 'Sealed operator inputs changed')
        return current
    def quiescence():
        return _quiescence(fresh()['quiescence_plan'], core, apps)
    def physical(detached, *, phase):
        require(phase in ('before-cas', 'before-commit') and canonical_sha256(detached) == canonical_sha256(plan),
                'Exact kernel boundary and detached review plan required')
        current = fresh()
        hydrated = _hydrate(core, current['physical_plan'], evidence)
        require(_guard().observe(hydrated, core, apps, rbac, batch) is True,
                'Fresh physical abort/preimage observer denied reuse')
        return True
    return apply_aborted_policy_reuse(**args, database=DATABASE, reservations_database=RESERVATIONS_DATABASE,
        reviewed_plan_sha256=reviewed_plan_sha256, verify_quiescence=quiescence, verify_abort_preimage=physical)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--input'); parser.add_argument('--input-sha256'); parser.add_argument('--reviewed-plan-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'execute': False, 'operation': 'retained-aborted-source-reuse'})); return 0
    require(all((args.input, args.input_sha256, args.reviewed_plan_sha256)), 'Independent input and reviewed plan pins required')
    from cps_compute.native_group_capture_protocol import private_bytes, json_document
    raw = private_bytes(args.input, maximum=16384)
    require('sha256:'+hashlib.sha256(raw).hexdigest() == args.input_sha256, 'Protected input raw SHA differs')
    packet = json_document(raw, maximum=16384)
    from kubernetes import client, config
    config.load_incluster_config()
    print(json.dumps(execute(packet, args.reviewed_plan_sha256, core=client.CoreV1Api(), apps=client.AppsV1Api(),
        rbac=client.RbacAuthorizationV1Api(), batch=client.BatchV1Api()), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
