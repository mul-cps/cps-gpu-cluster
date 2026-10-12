"""Offline, disabled Source and configuration proposals for CPS5/CIT20.

No transport, application initialization, credentials lookup or CRUD execution.
Root reviews complete current-state captures, applies audited backend methods,
checks each full readback and audit, and owns an independently reviewed inverse.
"""
import base64
import copy
import hashlib
import json
import re
import node_agent as agent

CIT_PEOPLE={'citgpumembera':'386feebb-df1a-4f3c-9ef9-6d9c026d5aea',
    'citgpumemberb':'d1fb4e43-64ec-4ac5-914f-e9cd39ad1c62'}
SCOPES={'cps':'native-group-b','cit':'native-group-a'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False)


def digest(value):
    return 'sha256:'+hashlib.sha256(canonical(value).encode()).hexdigest()


def one(rows,key,value):
    matches=[row for row in rows if row.get(key)==value]
    agent.require(len(matches)==1,'One exact complete existing record required')
    return matches[0]


def source_intent(before, registrations, *, policy_hash):
    agent.closed(before,{'cps','cit'},'Both complete actual Source captures required')
    agent.closed(registrations,{'cps:native-group-b','cit:native-group-a'},'Both complete current registrations required')
    agent.require(isinstance(policy_hash,str) and re.fullmatch('sha256:[0-9a-f]{64}',policy_hash),
        'Exact prospective compiled policy hash required')
    after=copy.deepcopy(before);registered=copy.deepcopy(registrations);operations=[]
    def operation(source,kind,target,old,new,backend):
        actor=before[source]['actor_model']['name']
        operations.append({'source':source,'actor':actor,'kind':kind,'target':target,
            'previous':copy.deepcopy(old),'current':copy.deepcopy(new),'backend_method':backend,
            'audit_required':True,'full_readback_required':True})
    for source,wid in SCOPES.items():
        full=before[source]
        agent.closed(full,{'actor_model','records','all_records','grants','people','aliases','servers'},
            'Complete Source state required, including unrelated records and aliases')
        actor=full['actor_model'];agent.require(actor.get('name')==('bjoern' if source=='cps' else 'akadmin')
            and actor.get('admin') is True,'Exact fresh owning Hub administrator model required')
        oldsize=5 if source=='cps' else 10;newsize=5 if source=='cps' else 20
        profile='interactive-native-qualification-'+str(oldsize)
        target_profile='interactive-native-qualification-'+str(newsize)
        ceiling={'cpu':'4','memory':'16Gi','gpuMemoryGiB':oldsize}
        newceiling=dict(ceiling,gpuMemoryGiB=newsize)
        workspace=one(full['records']['workspaces'],'id',wid)
        course=one(full['records']['courses'],'id',workspace['course_id'])
        agent.require(workspace.get('source')=='local' and workspace.get('external_id') is None
            and workspace.get('state')=='stopped' and workspace.get('profile')==profile
            and workspace.get('course_ceiling')==ceiling
            and not any(workspace.get(key) for key in ('archive_pending','reconciliation_pending','membership_removal_pending')),
            'Exact stopped source-owned qualification workspace required')
        agent.require(course.get('id')=='native-gpu-pilot-20261009' and course.get('source')=='local'
            and course.get('external_id') is None and course.get('resource_ceiling')==ceiling
            and not any(course.get(key) for key in ('reconciliation_pending','membership_removal_pending')),
            'Original source-owned course ceiling required')
        for kind,row in (('workspaces',workspace),('courses',course)):
            agent.require(one(full['all_records'][kind],'id',row['id'])==row,
                'Selected and complete Source record captures must agree')
        scope=source+':'+wid;registration=registrations[scope]
        agent.require(registration.get('workspace')==wid and registration.get('profiles')==[profile]
            and registration.get('principal')=='workspace:'+scope and registration.get('ceiling')==ceiling
            and registration.get('course_id')==workspace['course_id'] and registration.get('term_id')==workspace['term_id']
            and registration.get('storage',{}).get('state')=='active',
            'Complete original registration/member/storage/ceiling required')
        selected=[row for row in full['records']['memberships'] if row.get('group_id')==workspace['group_id']]
        agent.require(selected and all(row.get('source')=='local' and row.get('role')=='student'
            and full['people'].get(row.get('person_id'))==row.get('canonical_person_id') for row in selected)
            and registration.get('members')==sorted({row['canonical_person_id'] for row in selected})
            and len(registration['members'])==len(selected)
            and all(registration.get(key)==workspace.get(key) for key in ('namespace','pod','group_id'))
            and registration.get('owner')==workspace.get('hub_user')
            and registration.get('policy_hash')!=policy_hash,
            'Exact existing canonical members, neutral owner, namespace, Pod and previous policy required')
        if source=='cit':
            agent.require(len(course.get('workspace_bindings',[]))==1
                and [w['id'] for w in full['all_records']['workspaces'] if w.get('course_id')==course['id']]==[wid],
                'Raised CIT ceiling requires the dedicated single-workspace course')
            agent.require(full['people']==CIT_PEOPLE and registration.get('members')==sorted(CIT_PEOPLE.values()),
                'Exact existing CIT canonical identities required')
            for name,person in CIT_PEOPLE.items():
                grant=one(full['grants'][person],'id','native-pilot-cit-'+name)
                agent.require(grant.get('source')=='cit' and grant.get('person')==person
                    and grant.get('allowance')==1 and type(grant['allowance']) is int
                    and isinstance(grant.get('profiles'),list) and grant['profiles'].count(profile)==1
                    and target_profile not in grant['profiles'],'Exact two existing CIT grants required')
                newgrant=copy.deepcopy(grant);newgrant['profiles']=[target_profile if p==profile else p for p in grant['profiles']]
                target=one(after['cit']['grants'][person],'id',grant['id']);target.clear();target.update(newgrant)
                operation(source,'grants',grant['id'],grant,newgrant,'ComputePolicyClient.put_grant')
            newcourse=copy.deepcopy(course);newcourse['resource_ceiling']=newceiling
            operation(source,'courses',course['id'],course,newcourse,'LocalCourseProvider.put')
            newworkspace=copy.deepcopy(workspace);newworkspace.update(profile=target_profile,course_ceiling=newceiling)
            for kind,old,new in (('courses',course,newcourse),('workspaces',workspace,newworkspace)):
                for container in ('records','all_records'):
                    target=one(after[source][container][kind],'id',old['id']);target.clear();target.update(copy.deepcopy(new))
            operation(source,'workspaces',wid,workspace,newworkspace,'LocalCourseProvider.put')
        newregistration=copy.deepcopy(registration)
        newregistration.update(profiles=[target_profile],ceiling=newceiling,policy_hash=policy_hash)
        agent.require(newregistration['storage']==registration['storage'],'Existing workspace storage cannot change')
        registered[scope]=newregistration
        operation(source,'registrations',wid,registration,newregistration,'ComputePolicyClient.register_workspace')
    inverse_ops=[{**op,'previous':copy.deepcopy(op['current']),'current':copy.deepcopy(op['previous'])}
        for op in reversed(operations)]
    inverse={'enabled':False,'before':copy.deepcopy(after),'after':copy.deepcopy(before),
        'registrations_before':copy.deepcopy(registered),'registrations_after':copy.deepcopy(registrations),
        'operations':inverse_ops,'readback_sha256':digest({'sources':before,'registrations':registrations})}
    return {'version':1,'enabled':False,'hardware_qualified':False,'live_applied':False,
        'source_writers_stopped_required':True,'fixture_starts_excluded_required':True,
        'source_token_custody':'Root-exclusive','before':copy.deepcopy(before),'after':after,
        'registrations_before':copy.deepcopy(registrations),'registrations_after':registered,
        'operations':operations,'inverse':inverse,
        'before_sha256':digest({'sources':before,'registrations':registrations}),
        'after_sha256':digest({'sources':after,'registrations':registered})}


def object_guard(value,kind):
    meta=value.get('metadata',{})
    agent.require(value.get('kind')==kind and isinstance(meta,dict)
        and agent.canonical_uuid(meta.get('uid')) and isinstance(meta.get('resourceVersion'),str)
        and meta['resourceVersion'],'Full current object UID/resourceVersion required')
    return meta


def replace_patch(baseline,path,old,new):
    meta=object_guard(baseline,baseline['kind'])
    return [{'op':'test','path':'/metadata/uid','value':meta['uid']},
        {'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
        {'op':'test','path':path,'value':copy.deepcopy(old)},
        {'op':'replace','path':path,'value':copy.deepcopy(new)}]


def immutable_config(baseline,data,prefix):
    meta=object_guard(baseline,'ConfigMap')
    agent.require(baseline.get('immutable') is True,'Existing immutable configuration baseline required')
    name=prefix+'-'+digest(data).split(':',1)[1][:16]
    agent.require(name!=meta['name'],'Prospective configuration must use a distinct immutable name')
    return {'apiVersion':'v1','kind':'ConfigMap','immutable':True,
        'metadata':{'namespace':meta['namespace'],'name':name},'data':data}


def configuration_intent(proposal,baselines):
    """CAS patches only existing qualification data/references; never auth/images."""
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    agent.closed(baselines,{'policy','runtime','node_config','node_deployment','gateway_deployment','cps','cit'},
        'Complete current shared policy/runtime/node and both Hub baselines required')
    policy=Policy(proposal['policy.json']);mode=proposal['operator-qualification.json']
    NativeGroupQualification.from_config(mode,policy)
    agent.require(policy.catalog['gpuQualification']['qualified'] is False
        and mode['profile_caps']=={'interactive-native-qualification-5':5120,'interactive-native-qualification-20':20480}
        and mode['node_pool']['memory_budget_mib']==25600 and mode['node_pool']['headroom_mib']==1024
        and mode['node_pool']['max_workspaces']==2,'Exact unqualified CPS5/CIT20 configuration required')
    cm=baselines['policy'];object_guard(cm,'ConfigMap')
    oldpolicy=json.loads(cm['data']['policy.json']);oldhash=Policy(oldpolicy).hash
    agent.require(oldhash!=policy.hash,'New policy hash required')
    runtime_secret=baselines['runtime'];object_guard(runtime_secret,'Secret')
    runtime=json.loads(base64.b64decode(runtime_secret['data']['runtime.json'],validate=True))
    oldmode=runtime['nativeGpuQualification']
    agent.require(runtime['policy_hash']==oldhash and oldmode['policy_hash']==oldhash
        and oldmode['profile_caps']=={'interactive-native-qualification-5':5120,'interactive-native-qualification-10':10240}
        and runtime['nativeGpuGroups']==runtime['nativeGpuPilot']=={'enabled':False}
        and oldmode['gateImage']==mode['gateImage'] and oldmode['workloadImage']==mode['workloadImage'],
        'Exact existing 5/10-only qualification baseline and immutable images required')
    hub_settings={}
    for source in SCOPES:
        agent.closed(baselines[source],{'config','deployment'},'Both full Hub configuration and Deployment required')
        oldcm=baselines[source]['config'];settings=json.loads(oldcm['data']['settings.json'])
        agent.require(settings['source']==source and settings['qualificationDeployment']==oldmode
            and settings['profiles']==['interactive-native-qualification-'+('5' if source=='cps' else '10')]
            and json.loads(oldcm['data']['policy.json'])==oldpolicy,
            'Exact owning Hub qualification mode/profile/catalog required')
        newsettings=copy.deepcopy(settings);newsettings['qualificationDeployment']=copy.deepcopy(mode)
        newsettings['profiles']=['interactive-native-qualification-'+('5' if source=='cps' else '20')]
        hub_settings[source]=newsettings
    newruntime=copy.deepcopy(runtime);newruntime['policy_hash']=policy.hash
    newruntime['nativeGpuQualification']=copy.deepcopy(mode)
    return _configuration_updates(proposal,baselines,runtime,newruntime,hub_settings)


def _configuration_updates(proposal,baselines,runtime,newruntime,hub_settings):
    """Shared immutable ConfigMap, full-spec CAS and exact original inverse assembly."""
    from cps_compute.policy import Policy
    policy=Policy(proposal['policy.json']);cm=baselines['policy'];runtime_secret=baselines['runtime']
    mode=proposal['operator-qualification.json']
    data=copy.deepcopy(runtime_secret['data'])
    data['runtime.json']=base64.b64encode(canonical(newruntime).encode()).decode()
    result={'enabled':False,'hardware_qualified':False,'live_applied':False,
        'policy.patch.json':replace_patch(cm,'/data',cm['data'],dict(cm['data'],**{'policy.json':canonical(policy.catalog)})),
        'runtime.patch.json':replace_patch(runtime_secret,'/data',runtime_secret['data'],data),
        'full-runtime-before.json':copy.deepcopy(runtime),'full-runtime-after.json':newruntime,
        'configurations':{},'deployment_patches':{}}
    def deployment(source,baseline,oldname,newname):
        object_guard(baseline,'Deployment');spec=copy.deepcopy(baseline['spec'])
        changed=0
        for volume in spec['template']['spec'].get('volumes',[]):
            if volume.get('configMap',{}).get('name')==oldname:
                volume['configMap']['name']=newname;changed+=1
        agent.require(changed==1,'One exact existing configuration volume reference required')
        result['deployment_patches'][source]=replace_patch(baseline,'/spec',baseline['spec'],spec)
    oldnode=baselines['node_config'];nodejson=copy.deepcopy(oldnode['data'])
    nodejson['config.json']=canonical(proposal['node-config.json'])
    newnode=immutable_config(oldnode,nodejson,'cps-native-node-qualification')
    result['configurations']['node']=newnode
    deployment('node',baselines['node_deployment'],oldnode['metadata']['name'],newnode['metadata']['name'])
    for source in SCOPES:
        agent.closed(baselines[source],{'config','deployment'},'Both full Hub configuration and Deployment required')
        oldcm=baselines[source]['config'];newsettings=hub_settings[source]
        newdata=copy.deepcopy(oldcm['data']);newdata.update(**{'policy.json':canonical(policy.catalog),'settings.json':canonical(newsettings)})
        newcm=immutable_config(oldcm,newdata,'cps-native-hub-qualification')
        result['configurations'][source]=newcm
        deployment(source,baselines[source]['deployment'],oldcm['metadata']['name'],newcm['metadata']['name'])
    gateway=baselines['gateway_deployment'];object_guard(gateway,'Deployment')
    gateway_spec=copy.deepcopy(gateway['spec'])
    annotations=gateway_spec['template'].setdefault('metadata',{}).setdefault('annotations',{})
    annotations['cps.compute/native-qualification-config']=digest({'policy_hash':policy.hash,'mode':mode})
    result['deployment_patches']['gateway']=replace_patch(gateway,'/spec',gateway['spec'],gateway_spec)
    result['inverse']={'enabled':False,'original_configurations':copy.deepcopy({
        'node':oldnode,'cps':baselines['cps']['config'],'cit':baselines['cit']['config']}),
        'original_deployment_specs':{name:copy.deepcopy(obj['spec']) for name,obj in {
            'node':baselines['node_deployment'],'gateway':gateway,'cps':baselines['cps']['deployment'],
            'cit':baselines['cit']['deployment']}.items()},
        'original_policy_data':copy.deepcopy(cm['data']),'original_runtime_data':copy.deepcopy(runtime_secret['data']),
        'fresh_uid_resource_version_and_full_current_spec_tests_required':True}
    return result


def current_group_configuration_intent(proposal,baselines,*,current_agent_source=None):
    """Prepare the explicit d48 group-to-operator handover, without any apply.

    Complete objects remain Root-private. Raw capture pins and canonical typed
    projections are distinct: whitespace in an authenticated capture cannot be
    reconstructed from parsed JSON. Root retains and checks the original raw
    files; this function binds every projected field to the full CAS baselines.
    """
    from cps_compute.policy import Policy
    from cps_compute.native_groups import NativeGroupDeployment
    from cps_compute.native_qualification import NativeGroupQualification
    from qualification_proposal import (CURRENT_CONTROLLER,CURRENT_GROUP_POLICY,
        CURRENT_GROUP_APPROVALS,CURRENT_GATE_IMAGE)
    from current_group_historical_source import validation_context,runtime_history
    agent,map_history=validation_context(current_agent_source)
    agent.closed(baselines,{'policy','runtime','node_config','node_deployment','gateway_deployment','cps','cit'},
        'Complete current shared policy/runtime/node and both Hub baselines required')
    acceptance=proposal['acceptance.json'];source=proposal['current-source.json']
    agent.require((current_agent_source is None and 'source_node_agent_sha256' not in acceptance)
        or (current_agent_source is not None
            and acceptance.get('source_node_agent_sha256')=='sha256:'+hashlib.sha256(current_agent_source.encode()).hexdigest()),
        'Exact current node source proposal binding required')
    agent.closed(source,{'runtime','hubs'},'Exact current source native projections required')
    agent.require(acceptance.get('source_mode')=='current-approved-groups'
        and acceptance.get('hardware_qualified') is False and acceptance.get('live_applied') is False
        and acceptance.get('source_controller_sha256')==CURRENT_CONTROLLER
        and acceptance.get('controller_rollout_required') is False,
        'Separate current-source proposal with unchanged reviewed 630 controller required')
    for key in ('source_runtime_sha256','source_hubs_sha256'):
        value=acceptance.get(key)
        agent.require(isinstance(value,str) and re.fullmatch(r'sha256:[a-f0-9]{64}',value)
            and value!='sha256:'+'0'*64,'Original reviewed raw source pin required')
    cm=baselines['policy'];object_guard(cm,'ConfigMap')
    oldcatalog=json.loads(cm['data']['policy.json']);oldpolicy=Policy(oldcatalog)
    agent.require(oldpolicy.hash==CURRENT_GROUP_POLICY==acceptance.get('source_policy_hash'),
        'Exact reviewed d48 source policy required')
    secret=baselines['runtime'];object_guard(secret,'Secret')
    runtime=json.loads(base64.b64decode(secret['data']['runtime.json'],validate=True))
    fields={'policy_hash','nativeGpuGroups','nativeGpuPilot','nativeGpuQualification'}
    agent.closed(source['runtime'],fields,'Closed actual current native runtime projection required')
    projected_runtime={key:runtime[key] for key in fields}
    agent.require(projected_runtime==source['runtime'] and runtime['policy_hash']==oldpolicy.hash
        and runtime['nativeGpuPilot']==runtime['nativeGpuQualification']=={'enabled':False},
        'Full runtime and reviewed native source projection must agree')
    group=runtime['nativeGpuGroups'];deployment=NativeGroupDeployment.from_config(group,oldpolicy)
    agent.require(deployment is not None and group['gateImage']==CURRENT_GATE_IMAGE
        and agent.canonical_sha256(group['workspaces'])==CURRENT_GROUP_APPROVALS
        and group['evidence']['version']==2
        and group['evidence']['profile_caps']=={'interactive-shared-5':5120,'interactive-shared-10':10240},
        'Only exact current approved 5/10 group scopes may transition')
    policy=Policy(proposal['policy.json']);mode=proposal['operator-qualification.json']
    NativeGroupQualification.from_config(mode,policy)
    agent.require(mode['profile_caps']=={'interactive-native-qualification-5':5120,'interactive-native-qualification-20':20480}
        and mode['node_pool']['memory_budget_mib']==25600 and mode['node_pool']['headroom_mib']==1024
        and mode['node_pool']['max_workspaces']==2 and policy.catalog['gpuQualification']['qualified'] is False
        and mode['authorityNamespace']==group['authorityNamespace']
        and mode['gateImage']==group['gateImage'] and mode['workloadImage']==group['workloadImage'],
        'Exact disabled-profile operator CPS5/CIT20 target and unchanged images required')
    agent.require(all(mode['node_pool'][key]==group['node_pool'][key]
        for key in ('node','node_uid','gpu_uuid','boot_id','driver_generation')),
        'Unchanged physical node/device/driver epoch required')
    expected_approvals=copy.deepcopy(group['workspaces'])
    expected_catalog=copy.deepcopy(oldcatalog);expected_catalog.pop('policyHash',None)
    for hub,size in (('cps',5),('cit',20)):
        name='interactive-native-qualification-'+str(size)
        row=copy.deepcopy(oldcatalog['profiles']['interactive-shared-5'])
        row.update(enabled=False,kind='interactive',queue='interactive',cpu='4',memory='16Gi',images=[mode['workloadImage']])
        row.pop('qualificationRequired',None)
        row['gpu']={'mode':'shared','nominalMemoryGiB':size,'qualification':{
            'mechanism':'r615-native-cgroup-managed-deny','status':'pilot-unqualified'}}
        expected_catalog['profiles'][name]=row
        approval=expected_approvals[hub+':'+SCOPES[hub]]
        approval.update(profiles=[name],ceiling={'cpu':'4','memory':'16Gi','gpuMemoryGiB':size})
    expected_catalog['policyHash']=Policy(expected_catalog).hash
    agent.require(policy.catalog==expected_catalog and mode['workspaces']==expected_approvals,
        'Only reviewed disabled aliases may change the policy and workspace ceilings')
    oldnode=baselines['node_config'];object_guard(oldnode,'ConfigMap')
    node=agent.validate_config(json.loads(oldnode['data']['config.json']))
    snapshot=proposal['terminal-authority-snapshot.json']
    agent.closed(snapshot,{'ledger','previous_node','authority_maps','host_snapshot'},
        'Complete released terminal authority snapshot required')
    agent.require(node==snapshot['previous_node']
        and agent.canonical_sha256(node)==acceptance.get('source_node_config_sha256')
        and node['policy_hash']==oldpolicy.hash and node['mode']=='qualified-group'
        and node['pool']==group['node_pool'],'Exact existing current node configuration required')
    history=map_history({'authority_maps':snapshot['authority_maps'],'host_snapshot':snapshot['host_snapshot']},
        snapshot['ledger'],node)
    agent.require(agent.canonical_sha256(snapshot)==acceptance.get('terminal_authority_sha256'),
        'Original complete terminal snapshot binding required')
    target=agent.validate_config(proposal['node-config.json'])
    expected_node={'version':2,'enabled':True,'mode':'operator-qualification',
        'authority_namespace':mode['authorityNamespace'],'policy_hash':policy.hash,'pool':mode['node_pool'],
        'workspaces':{scope:{'profile':row['profiles'][0],
            'cap_mib':mode['profile_caps'][row['profiles'][0]]} for scope,row in mode['workspaces'].items()},
        'terminal_history':runtime_history(history,policy.hash,current_agent_source)}
    agent.require(target==expected_node and all(history.get(uid)==row for uid,row in node['terminal_history'].items()),
        'Every complete released lifetime and unchanged original historical entry required')
    expected_runtime={'policy_hash':policy.hash,'nativeGpuGroups':{'enabled':False},
        'nativeGpuPilot':{'enabled':False},'nativeGpuQualification':mode}
    agent.require(proposal['runtime-native-overlay.json']==expected_runtime,
        'Only exact target native runtime fields may change')
    agent.closed(source['hubs'],set(SCOPES),'Both actual current Hub native projections required')
    agent.closed(proposal['hub-native-overlays.json'],set(SCOPES),'Both exact target Hub native overlays required')
    hub_settings={};projected_hubs={}
    for hub,size in (('cps',5),('cit',20)):
        agent.closed(baselines[hub],{'config','deployment'},'Both full Hub configuration and Deployment required')
        config=baselines[hub]['config'];object_guard(config,'ConfigMap')
        settings=json.loads(config['data']['settings.json']);projection=source['hubs'][hub]
        optional={'qualificationDeployment','pilotDeployment'} & set(projection)
        agent.closed(projection,{'source','groupDeployment','profiles'}|optional,'Closed current Hub native projection required')
        projected_hubs[hub]={key:settings[key] for key in projection}
        oldname='interactive-shared-'+str(5 if hub=='cps' else 10)
        profiles=settings['profiles'];cpu=[p for p in profiles if p!=oldname]
        agent.require(projected_hubs[hub]==projection and settings['source']==hub
            and settings['groupDeployment']==group and profiles.count(oldname)==1
            and len(profiles)==len(set(profiles))
            and all(settings.get(key,{'enabled':False})=={'enabled':False}
                for key in ('qualificationDeployment','pilotDeployment'))
            and all(p in oldpolicy.catalog['profiles']
                and oldpolicy.catalog['profiles'][p].get('gpu',{}).get('mode')=='none'
                and oldpolicy.catalog['profiles'][p].get('kind')=='interactive' for p in cpu)
            and json.loads(config['data']['policy.json'])==oldcatalog,
            'Full owning Hub group/native profile and policy projections must agree')
        overlay={'groupDeployment':{'enabled':False},'pilotDeployment':{'enabled':False},
            'qualificationDeployment':mode,'profiles':cpu+['interactive-native-qualification-'+str(size)]}
        agent.require(proposal['hub-native-overlays.json'][hub]==overlay,
            'Only canonical GPU aliases may replace profiles; CPU choices stay unchanged')
        hub_settings[hub]=dict(copy.deepcopy(settings),**copy.deepcopy(overlay))
    newruntime=dict(copy.deepcopy(runtime),**copy.deepcopy(expected_runtime))
    result=_configuration_updates(proposal,baselines,runtime,newruntime,hub_settings)
    result['current-source-binding.json']={key:acceptance[key] for key in
        ('source_runtime_sha256','source_hubs_sha256','source_controller_sha256','source_policy_hash','source_node_config_sha256')}
    result['current-source-binding.json'].update(runtime_canonical_sha256=digest(projected_runtime),
        hubs_canonical_sha256=digest(projected_hubs),terminal_authority_sha256=acceptance['terminal_authority_sha256'],
        original_raw_source_capture_verification_required=True)
    result['inverse'].update(post_start_restore_requires_fresh_released_terminal_authority=True,
        new_lifetimes_must_not_be_overwritten=True,
        restored_node_history_excludes_restored_policy=True)
    return result


CURRENT_HUB_HOOK_PINS={
    'cps':'bd3a50f7e581ebf84fdcb7527a3cdd50105c81b866a997137d5b4c87a929e1ef',
    'cit':'e45710eb4f20ca85bada220cb2b2a93223032bfe3705379a05e634e59263448a'}
_GROUP_HOOK_PREFIX=("import json\nimport inspect as _native_pull_inspect\nfrom pathlib import Path\n"
    "from cps_compute.native_hub_config import install_native_group_hub_configuration\n"
    "install_native_group_hub_configuration(c, json.loads(Path('/etc/cps-native-hub/settings.json').read_text()))\n")
_QUALIFICATION_HOOK_PREFIX=("import json\nimport inspect as _native_pull_inspect\nfrom pathlib import Path\n"
    "from cps_compute.native_hub_config import install_native_qualification_hub_configuration\n"
    "_native_qualification_settings = json.loads(Path('/etc/cps-native-hub/settings.json').read_text())\n"
    "for _native_inactive_mode in ('groupDeployment', 'pilotDeployment'):\n"
    "    if _native_qualification_settings.get(_native_inactive_mode) != {'enabled': False}:\n"
    "        raise ValueError('Inactive native group/pilot configuration required for operator qualification')\n"
    "    _native_qualification_settings.pop(_native_inactive_mode)\n"
    "install_native_qualification_hub_configuration(c, _native_qualification_settings)\n")


def current_group_hub_hook_intent(proposal,configuration,hub_secrets):
    """Root-only full Hub Secret input; prepare explicit installer CAS, no apply.

    Only the two exact captured native hooks may change. YAML surrounding the
    hook is preserved semantically, every other Secret data value byte-exactly,
    and the existing private-image pull wrapper is preserved byte-exactly.
    """
    import yaml
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    agent.closed(hub_secrets,set(SCOPES),'Both actual full Hub Secrets required')
    agent.require(proposal['acceptance.json'].get('source_mode')=='current-approved-groups'
        and configuration.get('enabled') is False and configuration.get('live_applied') is False
        and configuration.get('hardware_qualified') is False,
        'Separate disabled current-source configuration intent required')
    policy=Policy(proposal['policy.json']);mode=proposal['operator-qualification.json']
    NativeGroupQualification.from_config(mode,policy)
    agent.require(mode['profile_caps']=={'interactive-native-qualification-5':5120,'interactive-native-qualification-20':20480}
        and policy.catalog['gpuQualification']['qualified'] is False,
        'Only operator CPS5/CIT20 hook handover is supported')
    class UniqueSafeLoader(yaml.SafeLoader):
        pass
    def unique_mapping(loader,node,deep=False):
        loader.flatten_mapping(node);result={}
        for key_node,value_node in node.value:
            key=loader.construct_object(key_node,deep=deep)
            agent.require(key not in result,'Duplicate full Hub values YAML key')
            result[key]=loader.construct_object(value_node,deep=deep)
        return result
    UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_mapping)
    load=lambda raw:yaml.load(raw,Loader=UniqueSafeLoader)
    result={'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,
        'secret_patches':{},'source_hooks':{},'inverse':{'enabled':False,'original_data':{},
            'fresh_uid_resource_version_and_full_current_data_tests_required':True}}
    for source in SCOPES:
        secret=hub_secrets[source];meta=object_guard(secret,'Secret')
        agent.require(secret.get('apiVersion')=='v1' and meta.get('name')=='hub'
            and meta.get('namespace')==('jupyterhub' if source=='cps' else 'cit-jhub'),
            'Exact owning existing Hub Secret namespace/name required')
        config=configuration['configurations'][source]
        settings=json.loads(config['data']['settings.json'])
        overlay=proposal['hub-native-overlays.json'][source]
        agent.require(settings.get('source')==source
            and all(settings.get(key)==value for key,value in overlay.items())
            and settings.get('groupDeployment')==settings.get('pilotDeployment')=={'enabled':False}
            and settings.get('qualificationDeployment')==mode
            and json.loads(config['data']['policy.json'])==policy.catalog,
            'Exact prepared operator-only Hub settings and policy required')
        raw=base64.b64decode(secret['data']['values.yaml'],validate=True)
        before=load(raw);agent.require(isinstance(before,dict),'Full Hub values mapping required')
        oldhook=before['hub']['extraConfig']['zz-native-group-pilot']
        agent.require(isinstance(oldhook,str)
            and hashlib.sha256(oldhook.encode()).hexdigest()==CURRENT_HUB_HOOK_PINS[source]
            and oldhook.startswith(_GROUP_HOOK_PREFIX),
            'Exact captured owning native group hook and pull wrapper required')
        suffix=oldhook[len(_GROUP_HOOK_PREFIX):]
        newhook=_QUALIFICATION_HOOK_PREFIX+suffix
        compile(newhook,'operator-qualification-hook-'+source,'exec')
        after=copy.deepcopy(before);after['hub']['extraConfig']['zz-native-group-pilot']=newhook
        newraw=yaml.safe_dump(after,sort_keys=False,allow_unicode=True).encode()
        decoded=load(newraw)
        agent.require(decoded==after,'Full Hub YAML semantic round trip required')
        oldother=copy.deepcopy(before);newother=copy.deepcopy(decoded)
        del oldother['hub']['extraConfig']['zz-native-group-pilot']
        del newother['hub']['extraConfig']['zz-native-group-pilot']
        agent.require(oldother==newother and newhook[len(_QUALIFICATION_HOOK_PREFIX):]==suffix,
            'All non-native values and original private pull source must remain unchanged')
        data=copy.deepcopy(secret['data']);data['values.yaml']=base64.b64encode(newraw).decode()
        result['secret_patches'][source]=replace_patch(secret,'/data',secret['data'],data)
        result['inverse']['original_data'][source]=copy.deepcopy(secret['data'])
        result['source_hooks'][source]={'key':'hub.extraConfig.zz-native-group-pilot',
            'previous_sha256':'sha256:'+CURRENT_HUB_HOOK_PINS[source],
            'current_sha256':'sha256:'+hashlib.sha256(newhook.encode()).hexdigest(),
            'private_pull_suffix_unchanged':True,'nonhook_yaml_unchanged':True,
            'installer':'install_native_qualification_hub_configuration'}
    return result
