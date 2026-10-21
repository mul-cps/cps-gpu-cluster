"""Offline, review-pinned compiler of cold SDK immutable ConfigMap GET closure.

No client, environment, file, network or apply operations. Mutable head pointers
retain their existing permissions. Outputs authorize only reads, never readiness,
private custody, software execution or hardware qualification. Run again after
publication changes; future envelopes are never invented from a name list.
"""
import copy
import hashlib
import json
import re

COMPONENTS = ('gateway', 'hub:cps', 'hub:cit', 'node')
MAX_CONFIGMAPS = 4 * 256 + 128
MAX_CAPTURE_BYTES = 64 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def digest(value):
    return 'sha256:'+hashlib.sha256(canonical(value).encode()).hexdigest()


def _inventory(values, kind, version, maximum):
    from cps_compute.native_observer_permissions import valid_uid
    require(type(values) is list and 1 <= len(values) <= maximum, 'Bounded explicit '+kind+' capture required')
    result = {}
    for value in values:
        require(type(value) is dict and value.get('kind') == kind and value.get('apiVersion') == version,
                'Actual captured '+kind+' required')
        meta = value.get('metadata', {}); key = (meta.get('namespace'), meta.get('name'))
        require(all(type(x) is str and re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?',x) for x in key)
                and key not in result and valid_uid(meta.get('uid'))
                and type(meta.get('resourceVersion')) is str and re.fullmatch(r'[1-9][0-9]{0,63}',meta['resourceVersion'])
                and not meta.get('ownerReferences') and not meta.get('deletionTimestamp'), 'Exact unique captured identity required')
        result[key] = value
    return result


class CapturedCore:
    """Only SDK-initiated actual reads enter a consumer's output proof set."""
    def __init__(self, maps, pointers, namespaces):
        self.maps, self.pointers, self.namespaces = maps, pointers, namespaces
        self.proofs = {}

    def read_namespaced_config_map(self, name, namespace):
        key = namespace, name
        require(namespace in self.namespaces and key in self.maps, 'Missing or foreign actual cold proof read')
        cm = self.maps[key]
        if key not in self.pointers:
            require(cm.get('immutable') is True and not cm.get('binaryData') and type(cm.get('data')) is dict
                    and all(type(k) is str and type(v) is str for k,v in cm['data'].items())
                    and sum(len(v.encode()) for v in cm['data'].values()) <= 1024*1024,
                    'Only actual immutable proof payloads may acquire new GET rights')
            self.proofs[key] = {'namespace':namespace, 'name':name, 'uid':cm['metadata']['uid'], 'data_sha256':digest(cm['data'])}
        return copy.deepcopy(cm)


def _terminal_reads(core, reference):
    """SDK-authenticated immutable index metadata, not private terminal acceptance."""
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    from cps_compute.native_node.history import TerminalCustodyIndex
    from cps_compute.native_node.migration import resolve_legacy_map
    index = TerminalCustodyIndex.load(core,ImmutableConfigMapRef.from_dict(reference))
    refs = []
    if index.archive is not None:
        archive = index.archive.document
        refs.extend(archive['inventory_refs'])
        refs.extend(archive['root_acceptance']['source_refs'])
        for provenance in archive['configuration_provenance'].values():
            refs.extend(provenance['references'])
    for entry in index.entries.values():
        for field in ('enrollment_ref','completion_ref','configuration_ref','recovery_ref','slot_ref'):
            if field in entry: refs.append(entry[field])
    for raw in refs:
        resolve_legacy_map(core,ImmutableConfigMapRef.from_dict(raw),version=1)
    if index.document['version'] == 3:
        _terminal_reads(core,index.document['legacy_index_ref'])


def _bootstrap(configuration, deployments, maps, policy):
    """Validate mutable packaged bootstrap separately; never a proof Role grant."""
    from cps_compute.native_group_process import _object, _template
    from cps_compute.native_group_capture_protocol import json_document
    declarations = configuration.document['component_declarations']
    for declaration in declarations.values():
        dep = deployments[(declaration['namespace'],declaration['name'])]
        _object(dep,'Deployment',declaration['namespace'],declaration['name'],declaration['uid'])
        spec = _template(dep)['spec']
        containers = [c for c in spec.get('containers',[]) if c.get('name') == declaration['container']]
        require(len(containers) == 1 and containers[0].get('image') == declaration['image']
                and spec.get('serviceAccountName') == declaration['service_account'], 'Actual consumer controller declaration drift')
    declaration = declarations['node']
    spec = _template(deployments[(declaration['namespace'],declaration['name'])])['spec']
    volumes = [v for v in spec.get('volumes',[]) if v.get('name') == 'packaged-bootstrap-input']
    require(len(volumes) == 1 and set(volumes[0]) == {'name','configMap'}, 'Exact Node bootstrap projection required')
    key = declaration['namespace'],volumes[0]['configMap']['name']
    require(key in maps, 'Actual reviewed Node bootstrap missing')
    actual = maps[key]; data = actual.get('data',{})
    require(not actual.get('binaryData') and set(data) == {'config-ref.json','policy.json','release'}
            and digest(json_document(data['config-ref.json'])) == digest(configuration.reference.to_dict())
            and digest(json_document(data['policy.json'])) == digest(policy.catalog)
            and data['release'] in ('true','false'), 'Actual Node bootstrap payload differs')
    return {'namespace':key[0], 'name':key[1], 'uid':actual['metadata']['uid'], 'data_sha256':digest(data)}


def _context_intents(release, roles, configuration, consumers, bootstrap):
    from cps_compute.native_observer_permissions import mutable_rows, names
    document = configuration.document; ns = configuration.reference.to_dict()['namespace']
    baseline = {(r['namespace'],r['name']):r for r in release['roles']}
    indexes = {(r['namespace'],r['name']):r['index'] for r in release['head_get_rows']}
    intents = []
    for key, expected in baseline.items():
        actual=roles[key]; index=indexes[key]
        require(actual['metadata']['uid']==expected['uid'] and mutable_rows(actual.get('rules'))==mutable_rows(expected['rules']),
                'Actual reviewed process Role UID/schema changed')
        normalized=copy.deepcopy(actual['rules'])
        for i in set(mutable_rows(expected['rules']).values())|{index}:
            normalized[i]['resourceNames']=expected['rules'][i]['resourceNames']
        require(digest(normalized)==digest(expected['rules']), 'Unrelated static process Role rules changed')
    for component in ('gateway','node'):
        key = ns,'cps-native-approval-'+component
        require(key in baseline and key in roles and key in indexes, 'Exact two system process Role baselines required')
        expected, actual = baseline[key],roles[key]; meta = actual['metadata']; index = indexes[key]
        require(meta['uid'] == expected['uid'] and mutable_rows(actual.get('rules')) == mutable_rows(expected['rules']),
                'Current process Role UID/schema changed')
        normalized = copy.deepcopy(actual['rules'])
        for i in mutable_rows(expected['rules']).values():
            normalized[i]['resourceNames'] = expected['rules'][i]['resourceNames']
        normalized[index]['resourceNames'] = expected['rules'][index]['resourceNames']
        require(digest(normalized) == digest(expected['rules']), 'Unrelated static process Role rules changed')
        row = actual['rules'][index]; required = set(expected['rules'][index]['resourceNames'])
        require((row['apiGroups'],row['resources'],row['verbs']) == ([''],['configmaps'],['get']), 'Only exact named ConfigMap GET row may grow')
        added = required-set(row['resourceNames'])
        justified = {p['name'] for p in consumers[component]['proofs'] if p['namespace'] == ns} | {bootstrap['name']}
        require(added <= justified, 'Unrelated baseline context cannot acquire new GET permission')
        desired = copy.deepcopy(actual['rules']); desired[index]['resourceNames'] = names(sorted(set(row['resourceNames'])|required))
        if not added: continue
        intents.append({'target':{k:meta[k] for k in ('namespace','name','uid','resourceVersion')}, 'added_names':sorted(added),
            'patch':[{'op':'test','path':'/metadata/uid','value':meta['uid']},
                     {'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
                     {'op':'test','path':'/rules','value':copy.deepcopy(actual['rules'])},
                     {'op':'replace','path':'/rules','value':desired}]})
    return intents


def compile_proof_reads(payload, *, reviewed_sha256):
    """Compile selected-head cold closure from independently reviewed captures.

    Existing mutable pointer/ACK/list/process permissions remain prerequisites.
    The Node metadata closure grants no terminal/private/Pod validation result.
    Supplemental Roles must be read back and consumer UID pins rechecked before
    restart. No future head selection or prospective envelope is manufactured.
    """
    from cps_compute.native_observer_permissions import ObserverRelease, role_targets, names, _MAX_NAMES
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    from cps_compute.native_approval_head import HeadSnapshot
    from cps_compute.native_group_revision import validate_retained_approval_identity
    from cps_compute.policy import Policy
    require(type(payload) is dict and set(payload) == {'version','release','policy','capture'}
            and type(payload['version']) is int and payload['version'] == 1
            and type(reviewed_sha256) is str and digest(payload) == reviewed_sha256, 'Exact independently reviewed compiler inputs required')
    require(len(canonical(payload['capture']).encode()) <= MAX_CAPTURE_BYTES, 'Captured proof graph exceeds byte bound')
    capture = payload['capture']
    require(type(capture) is dict and set(capture) == {'configmaps','deployments','roles','serviceaccounts'}, 'Closed actual consumer capture required')
    maps = _inventory(capture['configmaps'],'ConfigMap','v1',MAX_CONFIGMAPS)
    deployments = _inventory(capture['deployments'],'Deployment','apps/v1',4)
    roles = _inventory(capture['roles'],'Role','rbac.authorization.k8s.io/v1',7)
    accounts = _inventory(capture['serviceaccounts'],'ServiceAccount','v1',4)
    release = ObserverRelease.from_dict(payload['release']).document
    require(release['version'] == 2, 'Explicit current four-head release required')
    policy = Policy(payload['policy']); expected = ImmutableConfigMapRef.from_dict(release['node_configuration'])
    pointers = {(h['anchor']['pointer']['namespace'],h['anchor']['pointer']['name']) for h in release['heads'].values()}
    namespaces = {namespace for namespace,_ in pointers}
    require(len(namespaces) == 4, 'Four closed component namespaces required')
    consumers, manifests, registry_hashes = {}, [], set()
    for component in COMPONENTS:
        core = CapturedCore(maps,pointers,namespaces)
        configuration = NodeConfiguration.load(core,expected,policy)
        require(configuration is not None and configuration.document['version'] == 4
                and configuration.approval_head == release['heads']['node'], 'Actual enabled current v4 Node context required')
        declarations = configuration.document['component_declarations']; declaration = declarations[component]
        require({(d['namespace'],d['name']) for d in declarations.values()} == set(deployments)
                and set(role_targets(configuration.document)) == set(roles), 'Exact captured controllers/seven Roles required')
        identities = {(d['namespace'],d['service_account']) for d in declarations.values()}
        require(identities == set(accounts), 'Exact four consumer ServiceAccounts required')
        account = accounts[(declaration['namespace'],declaration['service_account'])]
        require(account['metadata']['uid'] == declaration['service_account_uid'], 'Actual consumer ServiceAccount UID changed')
        # Readiness Reader on Gateway/Hubs consumes all four heads. Node consumes
        # its own head plus authenticated historical terminal metadata.
        observed = {}
        for target in (('node',) if component == 'node' else COMPONENTS):
            head = HeadSnapshot.load(core,release['heads'][target],policy,configuration.deployment,component=target)
            for reference in head.approval.document['history']:
                actual=core.read_namespaced_config_map(reference['name'],reference['namespace'])
                validate_retained_approval_identity(actual,reference,policy,configuration.deployment)
            observed[target] = head
            registry_hashes.add(digest(head.approval.document['registry']))
        if component == 'node': _terminal_reads(core,configuration.document['terminal_index_ref'])
        subject = {'namespace':declaration['namespace'],'name':declaration['service_account'],'uid':account['metadata']['uid']}
        proofs = [core.proofs[key] for key in sorted(core.proofs)]
        consumers[component] = {'subject':subject,'proofs':proofs,'head_reference':observed[component].reference}
        for namespace in sorted({p['namespace'] for p in proofs}):
            selected = sorted(p['name'] for p in proofs if p['namespace'] == namespace)
            identity = digest({'subject':subject,'namespace':namespace,'proofs':[p for p in proofs if p['namespace']==namespace]})[7:23]
            name = 'cps-native-proof-'+component.replace(':','-')+'-'+identity
            metadata = {'namespace':namespace,'name':name}
            manifests += [{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':metadata,
                'rules':[{'apiGroups':[''],'resources':['configmaps'],'verbs':['get'],
                    'resourceNames':names(selected[start:start+_MAX_NAMES])}
                    for start in range(0,len(selected),_MAX_NAMES)]},
                {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':dict(metadata),
                'subjects':[{'kind':'ServiceAccount','namespace':subject['namespace'],'name':subject['name']}],
                'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':name}}]
    require(len(registry_hashes) == 1, 'All actual current head registries must agree')
    bootstrap = _bootstrap(configuration,deployments,maps,policy)
    return {'version':1,'reviewed_input_sha256':reviewed_sha256,'consumers':consumers,'manifests':manifests,
        'bootstrap':bootstrap,'process_context_intents':_context_intents(release,roles,configuration,consumers,bootstrap),
        'limits':{'selected_heads_only':True,'private_custody_verified':False,'mutable_pointer_permissions_inherited':True}}


if __name__ == '__main__':
    print(json.dumps({'execute':False,'operation':'compile-reviewed-cold-immutable-proof-reads'}))
