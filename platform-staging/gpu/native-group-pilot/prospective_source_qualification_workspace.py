"""Explicit Root-pinned single-scope531 qualification through normal Source APIs.

Default execution is inert. Source records/accounts must already exist through
normal console APIs. External isolation and hardware qualification stay with Root.
"""
import argparse
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID

HANDOVER_SHA = '53c5ed41ad95729a6f4248cf9d3f384c4c5c834b0bbef92134fe25c9ede8f870'
WORKLOAD_IMAGE = 'ghcr.io/mul-cps/cps-jupyter-notebook@sha256:531027c8e330d4ce818598e998a29d502433e9064f06a32dfc208a06ef2d0ba4'
GATE_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:bc5b128f582641eae8395e1121d1fb248eddc39a56c9e863b7c564badd94b167'
SOURCE_IMAGE = 'ghcr.io/mul-cps/e2x-course-hub@sha256:51f7f392397e41be512b356fbee91980fb233296cee7557d25a758b99b045f44'
PROFILE = 'interactive-native-qualification-5'
CEILING = {'cpu':'4','memory':'16Gi','gpuMemoryGiB':5}
ACTOR = 'bjoern'
STUDENT_PEOPLE = frozenset({'15164372-7ae5-4cfd-8b5d-fd402aa891bd','85de720c-94b0-4bc7-807e-c04512133494'})
STUDENT_OWNER = 'cps-ws-27c474f74f9d41c53eac0be01fcca8a3'
APPROVAL_FIELDS = frozenset({'owner','server','members','principal','profiles','ceiling','namespace','pod','group_id','course_id','term_id','storage'})
PINNED_FILES = ('source_closure','source_policy','policy','qualification_config','target_snapshot','node_config','config_file','handover_file')


def require(value,message):
    if not value: raise ValueError(message)


def canonical_sha256(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def raw_sha(value):
    return isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) is not None and value!='0'*64


def canonical_sha(value):
    return isinstance(value,str) and value.startswith('sha256:') and raw_sha(value[7:])


def uuid_value(value):
    try: return isinstance(value,str) and str(UUID(value))==value and UUID(value).int!=0
    except (ValueError,TypeError,AttributeError): return False


def decode(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate JSON field');result[key]=value
        return result
    def nonfinite(value): raise ValueError('Nonfinite JSON forbidden')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=nonfinite)


def protected(path,expected_sha):
    require(raw_sha(expected_sha),'Exact Root raw SHA required before private input')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==10001 and info.st_nlink==1
            and stat.S_IMODE(info.st_mode) in (0o400,0o600) and 0<info.st_size<=1024*1024,
            'Trusted UID10001 bounded private regular input required')
        with os.fdopen(fd,'rb',closefd=False) as stream: raw=stream.read(1024*1024+1)
        require(len(raw)==info.st_size and hashlib.sha256(raw).hexdigest()==expected_sha,'Exact Root private input bytes required')
        return raw
    finally: os.close(fd)


def validate_arguments(args):
    require(args.source=='cps' and args.operation in ('get','start','stop'),'Explicit CPS-only normal operation required')
    require(raw_sha(args.source_sha256) and all(isinstance(getattr(args,key,None),str)
        and Path(getattr(args,key)).is_absolute() and raw_sha(getattr(args,key+'_sha256',None)) for key in PINNED_FILES)
        and args.handover_file_sha256==HANDOVER_SHA and canonical_sha(args.current_authority_sha256)
        and canonical_sha(args.terminal_history_sha256),'All explicit Root file, current authority and history pins required before private/API access')


def validate_target(target,*,now=None):
    fields={'version','source','workspace','profile','workload_image','operator_members','source_policy_hash',
        'source_closure_sha256','current_authority_sha256','source_instance','registration','state','observed_at'}
    require(type(target) is dict and set(target)==fields and type(target['version']) is int and target['version']==1,
        'Closed version1 Root target snapshot required')
    workspace=target['workspace']
    require(target['source']=='cps' and isinstance(workspace,str)
        and re.fullmatch(r'operator-qualification-531-[a-z0-9](?:[a-z0-9-]{0,36}[a-z0-9])?',workspace) is not None
        and target['profile']==PROFILE and target['workload_image']==WORKLOAD_IMAGE and target['state']=='stopped',
        'Dedicated stopped CPS531 single5 operator scope required')
    members=target['operator_members']
    require(type(members) is list and 1<=len(members)<=8 and all(uuid_value(v) for v in members)
        and len(set(members))==len(members) and not set(members)&STUDENT_PEOPLE,'Only explicit nonstudent canonical operator members required')
    require(canonical_sha(target['source_policy_hash']) and raw_sha(target['source_closure_sha256'])
        and canonical_sha(target['current_authority_sha256']),'Root source policy/closure/current authority pins required')
    instance=target['source_instance']
    require(type(instance) is dict and set(instance)=={'namespace','deployment_uid','pod_uid','image'}
        and instance['namespace']=='cps-compute' and instance['image']==SOURCE_IMAGE
        and uuid_value(instance['deployment_uid']) and uuid_value(instance['pod_uid']),'Exact actual Source51f instance binding required')
    registered=target['registration']
    require(type(registered) is dict and set(registered)==APPROVAL_FIELDS|{'workspace','policy_hash','workspace_label','workspace_hash'},
        'Closed full existing Source registration required')
    owner=registered['owner']
    require(isinstance(owner,str) and re.fullmatch(r'cps-ws-[0-9a-f]{32}',owner) is not None and owner!=STUDENT_OWNER
        and registered['workspace']==workspace and registered['namespace']=='jupyterhub' and registered['server']=='rtc'
        and registered['pod']=='jupyter-'+owner+'--rtc' and registered['principal']=='workspace:cps:'+workspace
        and registered['members']==members and registered['profiles']==['interactive-cpu']
        and registered['policy_hash']==target['source_policy_hash']
        and all(isinstance(registered[k],str) and registered[k].startswith('operator-') for k in ('course_id','term_id','group_id')),
        'Exact existing operator-only neutral CPU registration required')
    require(type(registered['storage']) is dict and registered['storage'].get('state')=='active'
        and registered['storage'].get('namespace')=='jupyterhub' and isinstance(registered['storage'].get('pvc'),str)
        and bool(registered['storage']['pvc']),'Exact existing active operator PVC required')
    try: observed=datetime.fromisoformat(target['observed_at'].replace('Z','+00:00'))
    except (ValueError,TypeError,AttributeError): raise ValueError('UTC target observation required') from None
    now=now or datetime.now(timezone.utc)
    require(observed.tzinfo is not None and observed.utcoffset().total_seconds()==0 and now.tzinfo is not None
        and 0<=(now-observed).total_seconds()<=900,'Fresh Root UTC target snapshot within 15 minutes required')
    return target


def expected_registration(target,policy):
    body=copy.deepcopy(target['registration'])
    body.update(profiles=[PROFILE],ceiling=copy.deepcopy(CEILING),policy_hash=policy.hash,
        workspace_label=policy.labels['workspace'],workspace_hash=policy.owner_label('cps:'+target['workspace']))
    return body


def validate_configuration(target,source_policy,policy,mode,node,*,source_closure_sha256,current_authority_sha256,terminal_history_sha256):
    from cps_compute.native_qualification import NativeGroupQualification
    require(type(mode) is NativeGroupQualification and mode.workload_image==WORKLOAD_IMAGE and mode.gate_image==GATE_IMAGE
        and mode.profiles==frozenset({PROFILE}) and set(mode.workspaces)=={'cps:'+target['workspace']}
        and mode.cap_mib(PROFILE)==5120 and mode.node_pool['max_workspaces']==1
        and mode.node_pool['memory_budget_mib']==5120,'Exact typed prospective531 one5 scope and retained gate required')
    require(source_policy.hash==target['source_policy_hash'] and source_closure_sha256==target['source_closure_sha256']
        and current_authority_sha256==target['current_authority_sha256'],'Exact current Root source/closure/authority binding required')
    before=target['registration']
    require(before['workspace_label']==source_policy.labels['workspace']
        and before['workspace_hash']==source_policy.owner_label('cps:'+target['workspace']),'Actual old Source policy-derived ownership labels required')
    require(policy.catalog['gpuQualification']['qualified'] is False and policy.catalog['profiles'][PROFILE]['enabled'] is False
        and policy.catalog['profiles'][PROFILE]['images']==[WORKLOAD_IMAGE],'Disabled matching unqualified531 policy required')
    after=expected_registration(target,policy);mode.authorize('cps',after,PROFILE)
    require(type(node) is dict and set(node)=={'version','enabled','mode','authority_namespace','policy_hash','pool','workspaces','terminal_history'}
        and type(node['version']) is int and node['version']==2 and node['enabled'] is True and node['mode']=='operator-qualification'
        and node['authority_namespace']==mode.authority_namespace and node['policy_hash']==policy.hash and node['pool']==mode.node_pool
        and node['workspaces']=={'cps:'+target['workspace']:{'profile':PROFILE,'cap_mib':5120}}
        and type(node['terminal_history']) is dict and canonical_sha256(node['terminal_history'])==terminal_history_sha256,
        'Exact reviewed node configuration and complete retained history required')
    return after


def workspace_guard(workspace,target):
    require(type(workspace) is dict,'Operator workspace missing; create it through normal Source console/API before qualification')
    body=target['registration']
    expected={'id':target['workspace'],'course_id':body['course_id'],'term_id':body['term_id'],'group_id':body['group_id'],
        'hub_user':body['owner'],'hub_server':body['server'],'namespace':body['namespace'],'pod':body['pod'],
        'source':'local','profile':PROFILE,'course_ceiling':CEILING}
    require(all(workspace.get(k)==v for k,v in expected.items()) and workspace.get('external_id') is None
        and not workspace.get('archived') and not workspace.get('archive_pending'),'Exact normal Source operator workspace/profile required')


def registration_guard(actual,expected,mode):
    require(actual==expected,'Exact normal Source registration and retained members/storage required')
    mode.authorize('cps',actual,PROFILE)


async def operate(service,target,operation,mode,expected):
    require(operation in ('get','start','stop'),'Exact normal operation required')
    try: before=await service.get(target['workspace'])
    except KeyError:
        raise ValueError('Operator workspace missing; create it through normal Source console/API before qualification') from None
    workspace_guard(before,target)
    actor=await service.hub.hub.get_user(ACTOR)
    require(type(actor) is dict and actor.get('name')==ACTOR and actor.get('admin') is True,'Fresh actual CPS administrator required')
    from urllib.parse import quote
    path='workspaces/'+quote(target['workspace'],safe='')
    registration_guard(await service.compute._request(path),expected,mode)
    if operation=='start':
        require(before.get('state')=='stopped','Normal Start requires stopped state')
        await service.start(target['workspace'],actor=ACTOR)
    elif operation=='stop': await service.close(target['workspace'],actor=ACTOR,archive=False)
    after=await service.get(target['workspace']);workspace_guard(after,target)
    registration_guard(await service.compute._request(path),expected,mode)
    require(operation!='start' or after.get('state')=='running','Normal Start must read back running')
    require(operation!='stop' or after.get('state')=='stopped','Normal Stop must read back stopped')
    return {'version':1,'source':'cps','workspace':target['workspace'],'profile':PROFILE,'operation':operation,
        'state':after.get('state'),'normal_workspace_service':True,'hardware_qualified':False}


async def execute(args):
    validate_arguments(args)  # No file, app, credential or API access before all pins.
    require(os.geteuid()==10001,'Exact trusted operator UID10001 required')
    protected(__file__,args.source_sha256)
    target=validate_target(decode(protected(args.target_snapshot,args.target_snapshot_sha256)))
    require(target['source_closure_sha256']==args.source_closure_sha256
        and target['current_authority_sha256']==args.current_authority_sha256,'Exact Root closure/authority argument binding required')
    raw=protected(args.handover_file,HANDOVER_SHA)
    namespace={'__name__':'pinned_prospective_normal_app_loader','__file__':args.handover_file}
    exec(compile(raw,args.handover_file,'exec'),namespace)
    closure=decode(protected(args.source_closure,args.source_closure_sha256));namespace['verify_source_closure'](closure)
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    source_policy=Policy(decode(protected(args.source_policy,args.source_policy_sha256)))
    policy=Policy(decode(protected(args.policy,args.policy_sha256)))
    mode=NativeGroupQualification.from_config(decode(protected(args.qualification_config,args.qualification_config_sha256)),policy)
    node=decode(protected(args.node_config,args.node_config_sha256))
    expected=validate_configuration(target,source_policy,policy,mode,node,source_closure_sha256=args.source_closure_sha256,
        current_authority_sha256=args.current_authority_sha256,terminal_history_sha256=args.terminal_history_sha256)
    app,service=namespace['load_configured_service'](args.config_file,args.config_file_sha256,source='cps',
        database_path='/data/courses.sqlite',server_config_path='/data/config.yml')
    from e2x_course_hub.cps.workspaces import WorkspaceService
    require(type(service) is WorkspaceService and app.console_owner=='cps' and app.service_prefix=='/services/cps-admin/'
        and service.provider is app.tornado_settings['course_provider'] and service.compute is app.tornado_settings['compute_policy']
        and service.compute.console=='cps' and service.compute.base_url=='https://compute-gateway.cps-compute.svc.cluster.local:8000'
        and service.hub.hub.api_url.rstrip('/')=='http://hub.jupyterhub.svc.cluster.local:8081/hub/api',
        'Genuine owning Source app, service and original endpoints required')
    return await operate(service,target,args.operation,mode,expected)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--source');parser.add_argument('--operation');parser.add_argument('--source-sha256')
    for field in PINNED_FILES:
        name=field.replace('_','-');parser.add_argument('--'+name);parser.add_argument('--'+name+'-sha256')
    parser.add_argument('--current-authority-sha256');parser.add_argument('--terminal-history-sha256');args=parser.parse_args()
    if not args.execute:print('{"version":1,"state":"inert","live_execution":false}');return
    print(json.dumps(asyncio.run(execute(args)),sort_keys=True,allow_nan=False))


if __name__=='__main__':main()
