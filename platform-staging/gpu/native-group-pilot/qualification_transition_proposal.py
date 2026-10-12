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
    newruntime=copy.deepcopy(runtime);newruntime['policy_hash']=policy.hash
    newruntime['nativeGpuQualification']=copy.deepcopy(mode)
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
        oldcm=baselines[source]['config'];settings=json.loads(oldcm['data']['settings.json'])
        agent.require(settings['source']==source and settings['qualificationDeployment']==oldmode
            and settings['profiles']==['interactive-native-qualification-'+('5' if source=='cps' else '10')]
            and json.loads(oldcm['data']['policy.json'])==oldpolicy,
            'Exact owning Hub qualification mode/profile/catalog required')
        newsettings=copy.deepcopy(settings);newsettings['qualificationDeployment']=copy.deepcopy(mode)
        newsettings['profiles']=['interactive-native-qualification-'+('5' if source=='cps' else '20')]
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
