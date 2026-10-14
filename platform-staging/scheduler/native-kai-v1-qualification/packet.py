"""Inert renderer for one existing CIT qualification10 scope; never contacts a cluster."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROFILE = 'interactive-native-qualification-10'
SCOPE = 'cit:native-group-a'
GATEWAY = 'https://compute-gateway.cps-compute.svc.cluster.local:8000'
CANDIDATE = 'ghcr.io/mul-cps/cps-compute@sha256:4dca3af5e19161c21cb851d188d026f8a4e7894e195dcd904b155c3ea9f2fc2d'
CATALOG_SHA = 'd48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
NODE_SHA = '2987526ec27154c5189b304daa654099b1c6ee1c9db7d6cfc2fcdd1f5db48289'
HUB_SHA = '0215e92c8488cb556153e132070a1cec40f4847249e2e139f8b3dfdf1d08921c'
INTERNAL_AUDIENCE = 'cps-native-kai-qualification-v1'


def require(value, message):
    if not value: raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(value): return hashlib.sha256(canonical(value)).hexdigest()


def compiler():
    p = ROOT / 'scripts/compile_compute_policy.py'
    spec = importlib.util.spec_from_file_location('reviewed_policy_compiler', p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def render(catalog, node, hub):
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    require(sha(catalog) == CATALOG_SHA and sha(node) == NODE_SHA and sha(hub) == HUB_SHA,
            'Exact reviewed catalog/node/Hub preimages required; rebase after Root review')
    require(catalog['gpuQualification']['qualified'] is False, 'No global qualification assertion')
    catalog = copy.deepcopy(catalog)
    # The ordinary compiler continues to validate the existing nominal fraction.
    # It is a scheduling hint, never a cap/SM proof. Every GPU profile stays off.
    for entry in catalog['profiles'].values():
        if entry['gpu']['mode'] != 'none':
            entry['enabled'] = False
            if entry['gpu']['mode'] == 'shared':
                entry['gpu'].pop('qualification', None)
                entry['gpu']['fraction'] = str(entry['gpu']['nominalMemoryGiB'] / 40)
    entry = copy.deepcopy(catalog['profiles']['interactive-shared-10'])
    entry.pop('qualificationRequired', None)
    entry['gpu']['qualification'] = {'mechanism': 'r615-native-cgroup-managed-deny', 'status': 'pilot-unqualified'}
    catalog['profiles'][PROFILE] = entry
    c = compiler(); policy_document = c.compile_catalog(catalog); policy = Policy(policy_document)
    require(policy.hash == policy_document['policyHash'], 'Normal compiler/SDK policy hash mismatch')
    approval = copy.deepcopy(hub['groupDeployment']['workspaces'][SCOPE])
    approval['profiles'] = [PROFILE]
    # No owner, membership, storage, course ceiling or native capacity is raised.
    mode = {'enabled': True, 'version': 1, 'operator_only': True,
            'policy_hash': policy.hash, 'policy_version': policy.version,
            'node_pool': copy.deepcopy(node['pool']), 'authorityNamespace': node['authority_namespace'],
            'gateImage': hub['gateImage'], 'workloadImage': hub['workloadImages'][0],
            'profile_caps': {PROFILE: 10240},
            'capacity_observation_sha256': hub['groupDeployment']['evidence']['capacity_evidence_sha256'],
            'workspaces': {SCOPE: approval}}
    NativeGroupQualification.from_config(mode, policy)
    after_node = copy.deepcopy(node)
    after_node.update(mode='operator-qualification', policy_hash=policy.hash,
                      workspaces={SCOPE: {'profile': PROFILE, 'cap_mib': 10240}})
    plain = copy.deepcopy(hub); plain.pop('groupDeployment'); plain.pop('groupShareTokenCompatibility', None)
    plain.update(profiles=[PROFILE], policyPath='/var/run/cps-kai-pilot/policy.json',
                 qualificationDeployment=mode)
    pending = {'enabled': True, 'version': 1, 'qualificationHub': plain,
               'coordinator': {'origin': GATEWAY, 'caFile': hub['gatewayCAFile'],
                               'tokenFile': '/var/run/cps-kai-service/token', 'queue': 'cps-interactive'}}
    return {'catalog.json': catalog, 'policy.json': policy_document,
            'queues-priorities.json': c.manifests(policy_document),
            'operator-qualification.json': mode, 'node-config.json': after_node,
            'hub-pending.json': pending,
            'gateway-runtime-overlay.json': {'policy_file': '/var/run/cps-kai-pilot/policy.json',
                'policy_hash': policy.hash, 'nativeGpuPilot': {'enabled': False},
                'nativeGpuGroups': {'enabled': False}, 'nativeGroupApprovals': {'enabled': False},
                'nativeGpuQualification': mode},
            'registration-proposal.json': {'workspace': 'native-group-a', 'policy_hash': policy.hash, **approval},
            'acceptance.json': {'version': 1, 'enabled': False, 'live_applied': False,
                'hardware_qualified': False, 'scope': SCOPE, 'profile': PROFILE, 'cap_mib': 10240,
                'candidate': CANDIDATE, 'policy_hash': policy.hash,
                'capacity_observation_is_prior_evidence_only': True,
                'fresh_capacity_health_epoch_and_terminal_history_revalidation_required': True,
                'source_owned_audited_profile_and_grant_delta_required': True,
                'normal_source_start_stop_required': True,
                'maintenance_and_signed_service_authorization_required': True}}


def source_delta(before, registration, proposal):
    """Full owned Source capture, never annotation authority; produce audited CAS intent only."""
    require(set(before) == {'actor_model', 'records', 'all_records', 'grants', 'people', 'aliases', 'servers'},
            'Complete fresh owning Source capture required')
    require(before['actor_model'].get('name') == 'akadmin' and before['actor_model'].get('admin') is True,
            'Current actual CIT admin required')
    def one(rows, key, value):
        found=[r for r in rows if r.get(key)==value]; require(len(found)==1, 'One exact record required'); return found[0]
    w=one(before['records']['workspaces'],'id','native-group-a')
    course=one(before['records']['courses'],'id',w['course_id'])
    require(w.get('state')=='stopped' and w.get('source')=='local' and w.get('external_id') is None
        and w.get('profile')=='interactive-shared-10' and not before['servers'], 'Original scope must be normally stopped')
    require(w.get('course_ceiling')==course.get('resource_ceiling')==proposal['ceiling']
        and course.get('id')==proposal['course_id'] and w.get('hub_user')==proposal['owner']
        and all(w.get(k)==proposal[k] for k in ['term_id','group_id','namespace','pod']),
        'No course, ceiling, neutral owner or placement changes permitted')
    require(not any(w.get(k) or course.get(k) for k in ['archive_pending','reconciliation_pending','membership_removal_pending']),
            'Source lifecycle pending mutation denied')
    require(one(before['all_records']['workspaces'],'id',w['id'])==w
        and one(before['all_records']['courses'],'id',course['id'])==course, 'Selected and complete Source captures differ')
    require(registration['profiles']==['interactive-shared-10'] and registration['workspace']==w['id']
        and registration['principal']==proposal['principal'] and registration['members']==proposal['members']
        and registration['storage']['state']=='active', 'Actual central registration required')
    for key in ['owner','server','ceiling','namespace','pod','group_id','course_id','term_id']:
        require(registration[key]==proposal[key], 'Registration scope changed')
    require({k:registration['storage'].get(k) for k in proposal['storage']}==proposal['storage'], 'Storage changed')
    selected=[r for r in before['records']['memberships'] if r.get('group_id')==w['group_id']]
    require(selected and sorted({r.get('canonical_person_id') for r in selected})==proposal['members']
        and all(r.get('source')=='local' and r.get('role')=='student'
            and before['people'].get(r['person_id'])==r['canonical_person_id'] for r in selected), 'Canonical current Source members required')
    ops=[]
    def op(kind, old, new, method):
        ops.append({'source':'cit','actor':'akadmin','kind':kind,'target':old.get('id',w['id']),
                    'previous':copy.deepcopy(old),'current':copy.deepcopy(new),'backend_method':method,
                    'audit_required':True,'full_readback_required':True})
    new=copy.deepcopy(w);new['profile']=PROFILE
    workspace_op=(w,new)
    for person in proposal['members']:
        grants=[g for g in before['grants'][person] if g.get('source')=='cit'
                and 'interactive-shared-10' in g.get('profiles',[])]
        require(len(grants)==1, 'One existing exact cap10 member grant required')
        old=grants[0];new=copy.deepcopy(old)
        new['profiles']=[PROFILE if x=='interactive-shared-10' else x for x in old['profiles']]
        require(type(new.get('allowance')) is int and new['allowance']==old['allowance']==1, 'Existing atomic member allowance must remain1')
        op('grants',old,new,'ComputePolicyClient.put_grant')
    op('workspaces',*workspace_op,'WorkspaceService.change_profile')
    new=copy.deepcopy(registration);new.update(policy_hash=proposal['policy_hash'],profiles=[PROFILE])
    expected_registration=new
    return {'version':1,'enabled':False,'before_sha256':sha(before),'registration_sha256':sha(registration),
            'expected_registration':expected_registration,'http_mutations':[
                {'path':'compute','body':{k:v for k,v in o['current'].items() if k!='source'}} for o in ops if o['kind']=='grants']+[
                {'path':'workspaces/native-group-a/profile','body':{'profile':PROFILE}}],
            'operations':ops,'inverse':[dict(o,previous=o['current'],current=o['previous']) for o in ops],
            'inverse_requires_original_policy_runtime_and_existing_cap10_grants_before_profile_change':True,
            'windows_memberships_aliases_storage_course_and_other_records_unchanged':True}


class CustodyHeld(RuntimeError): pass


def validate_terminal(x):
    require(set(x)=={'clean','native_zero','exact_pod_absent','maps_absent','ledger_released',
                    'member_reservations_zero','custody_clean','reservation_absent','shares_closed'}
            and all(type(v) is bool and v for v in x.values()), 'Complete genuine terminal proof required')


def run_lifecycle(backend):
    """An attempted Start always gets normal SourceClose; unknown outcomes retain custody."""
    error=None; result=None
    try:
        result=backend.start()
    except BaseException as caught: error=caught
    try:
        backend.close()
        validate_terminal(backend.terminal())
    except BaseException as caught:
        raise CustodyHeld('Normal SourceClose/physical cleanup unconfirmed; do not restore writers/config') from caught
    if error is not None: raise error
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--render',type=Path);a=p.parse_args()
    if a.render is None:
        print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'live_applied':False}));return
    base=ROOT/'platform-staging/gpu/native-group-pilot/qualification/cpu-runner-policy-20261012'
    result=render(json.loads((base/'catalog.json').read_text()),json.loads((HERE/'node-config-before.json').read_text()),
                  json.loads((base/'cit-settings.json').read_text()))
    a.render.mkdir(mode=0o700)
    for name,value in result.items():
        q=a.render/name;q.write_bytes(json.dumps(value,indent=2,sort_keys=True).encode()+b'\n');q.chmod(0o600)
    (a.render/'manifest.json').write_bytes(canonical({n:hashlib.sha256((a.render/n).read_bytes()).hexdigest() for n in result})+b'\n')
    print(json.dumps({'state':'rendered-disabled','policy_hash':result['policy.json']['policyHash'],'scope':SCOPE,'api_calls':False}))

if __name__=='__main__': main()
