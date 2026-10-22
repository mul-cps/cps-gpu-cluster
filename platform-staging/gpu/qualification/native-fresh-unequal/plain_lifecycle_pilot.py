"""Pure two-5GiB legacy pilot projections; never Source qualification/activation.

Caller supplies reviewed identities, grants/storage and canonical DB paths.
Offline verification (default Python never imports the SDK):
  python -m pytest -q platform-staging/gpu/qualification/native-fresh-unequal/test_plain_lifecycle_pilot.py
Each test starts /home/bjoern/git/cps-compute/.venv/bin/python with explicit
SDK768 src/tests/packages/hub/src paths in a separate process. No parent sys.path
or sys.modules changes are made. Run from the shared QA cluster worktree.
Legacy runtime/source-pin and complete prior-inventory compatibility are NOT
established by this builder or its structural Node validator.

This validates consistency only; it cannot authenticate those inputs or authorize
new hardware, revive old custody, create files, or install a process.
"""
import copy
import re
from pathlib import PurePosixPath

PROFILE='interactive-native-pilot-5'

def require(ok,message):
    if not ok:raise ValueError(message)

def build(*,policy,approvals,pool,authority_namespace,gate_image,workload_image,
          hub_transports,database_paths):
    from cps_compute.policy import Policy
    from cps_compute.native_groups import validate_approvals
    from cps_compute.native_gpu_control import NativeGpuAuthority
    from cps_compute_hub.native_hub_config import _validate
    require(type(policy) is Policy,'Actual typed current policy required')
    require(type(approvals) is dict and len(approvals)==2,'Exactly two reviewed workspace approvals required')
    require(type(pool) is dict and pool.get('node')=='k3s-wk-gpu2' and pool.get('max_workspaces')==2
            and type(pool.get('max_workspaces')) is int,'Exact two-slot GPU2 pool required')
    NativeGpuAuthority._validate_pool(None,pool)
    require(type(authority_namespace) is str and re.fullmatch(r'[a-z0-9](?:[-a-z0-9]*[a-z0-9])?',authority_namespace)
            and authority_namespace not in ('default','jupyterhub','cit-jhub','cps-native-system','cps-native-runtime'),
            'Explicit separate fresh pilot authority namespace required')
    for image in (gate_image,workload_image):
        require(type(image) is str and re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}',image)
                and not image.endswith('0'*64),'Exact reviewed immutable images required')
    require(type(database_paths) is dict and set(database_paths)=={'store','reservations'}
            and len(set(database_paths.values()))==2
            and all(type(v) is str and v.startswith('/data/') and '..' not in PurePosixPath(v).parts
                    and str(PurePosixPath(v))==v for v in database_paths.values()),
            'Explicit existing canonical /data database paths required')
    require(type(hub_transports) is dict and set(hub_transports)=={k.split(':')[0] for k in approvals},
            'Exact owning Hub transport projections required')
    rows=copy.deepcopy(approvals)
    for row in rows.values():
        require(type(row) is dict and row.get('profiles')==['interactive-shared-5'],
                'Only reviewed shared5 approvals can enter the two5 pilot')
        row['profiles']=[PROFILE]
    validate_approvals(rows,{PROFILE:5120})
    owners=[v['owner'] for v in rows.values()];members=[set(v['members']) for v in rows.values()]
    require(len(set(owners))==2 and not members[0].intersection(members[1])
            and not set(owners).intersection(set.union(*members))
            and len({(v['namespace'],v['pod']) for v in rows.values()})==2
            and len({(v['namespace'],v['storage']['pvc']) for v in rows.values()})==2,
            'Disjoint neutral owners/members, Pods and storage required')
    raw=copy.deepcopy(policy.catalog);raw.pop('policyHash',None)
    candidate=copy.deepcopy(raw['profiles']['interactive-shared-5'])
    require(candidate.get('cpu')=='4' and candidate.get('memory')=='16Gi'
            and candidate.get('images')==[workload_image]
            and candidate.get('gpu',{}).get('nominalMemoryGiB')==5,
            'Current selected shared5 workload/resources must match reviewed input')
    candidate['enabled']=False
    candidate['gpu']['qualification']={'mechanism':'r615-native-cgroup-managed-deny','status':'pilot-unqualified'}
    require(PROFILE not in raw['profiles'] or raw['profiles'][PROFILE]==candidate,
            'Conflicting existing pilot alias cannot be overwritten')
    raw['profiles'][PROFILE]=candidate
    derived=Policy(raw);derived.native_pilot_resources(PROFILE);raw['policyHash']=derived.hash
    scopes={k:{'profile':PROFILE} for k in rows}
    hubs={}
    for source,transport in hub_transports.items():
        require(type(transport) is dict and set(transport)=={'policyPath','gatewayUrl','gatewayCAFile',
                'serviceTokenEnv','canonicalMappingPath'},'Closed protected Hub transport references required')
        owned=[v for k,v in rows.items() if k.startswith(source+':')]
        mounts={(m['server'],m['path'],m['mount_path']) for v in owned for m in v['storage']['readonly_mounts']}
        h={**copy.deepcopy(transport),'enabled':True,'source':source,'profiles':[PROFILE],
           'owners':sorted(v['owner'] for v in owned),'workspaces':sorted(k for k in rows if k.startswith(source+':')),
           'gateImage':gate_image,'workloadImages':[workload_image],
           'writablePVCClaims':sorted({v['storage']['pvc'] for v in owned}),
           'writableMountPaths':['/workspace'],
           'readonlyNFS':[{'server':s,'path':p,'mountPath':m} for s,p,m in sorted(mounts)],
           'groupShareTokenCompatibility':True}
        _validate(h);hubs[source]=h
    return {'version':1,'proposal_only':True,'production_qualified':False,'lifecycle_runnable':False,'source_registry_update':None,
            'base_policy_hash':policy.hash,'policy':raw,'profile':PROFILE,'reviewed_approvals':rows,
            'authority':{'native_pilot_workspaces':copy.deepcopy(scopes),'node_pool':copy.deepcopy(pool)},
            'node':{'version':1,'enabled':True,'authority_namespace':authority_namespace,
                    'policy_hash':derived.hash,'pool':copy.deepcopy(pool),'workspaces':copy.deepcopy(scopes)},
            'hubs':hubs,'database_paths':copy.deepcopy(database_paths)}
