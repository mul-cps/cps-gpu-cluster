"""Closed offline operator bridge for the reviewed Hub package image only.

No API access, journal writes, Source mutations or GPU operations occur here.
The three phases emit guarded intents; genuine observations come from the
operator's authenticated read-only capture and the actual Kubernetes API.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re

import native_group_approval_renderer as r

HUBS = ('hub:cps', 'hub:cit')
OLD_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:c22c7460ae3ddc3cac454a7f0fac41fc7308e4601e06162b91ca7af7ba301233'
REVIEWED_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:bc32b73d244738c3778560a1f48e701efd10f8c57ac4834f486b3f27a30d2623'
ACCOUNT_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:466b8398285a513499440dd00aaf0abc377cc49afe05f19e5556e79908106486'
REVIEWED_PAIRS = ((OLD_IMAGE, REVIEWED_IMAGE), (REVIEWED_IMAGE, ACCOUNT_IMAGE))
OBSERVATIONS = {'documents','reference_maps','bootstrap_maps','acknowledgments',
    'deployments','replicasets','pods','roles','source','epoch','gateway_runtime'}
REQUEST = {'version','previous_publication','previous_publication_sha256','policy',
    'qualification','reviewed_images','old_state','observations','gateway_runtime'}
PUBLICATION = {'version','source_sha256','revision','policy_hash','documents','baseline_guards','live_applied',
    'process_readiness_verified','references','reference_maps','bootstrap_maps','patches','expected_deployments',
    'requires_actual_process_ack','acknowledgment_references','process_declarations','runtime_settings'}
ACCESS = {'version','kind','plan_sha256','observations','captured_at','role_patches','actual_process_names',
    'bootstrap_maps','ready','requires_actual_fresh_acknowledgments'}
PLAN = {'version','kind','request','request_sha256','planned_at','projection',
    'bootstrap_candidates','deployment_patches','lineage','ready','gateway_runtime_patch',
    'gateway_runtime_target','gateway_pod_restart_precondition'}


def closed(value, keys, message):
    r.require(isinstance(value,dict) and set(value)==set(keys),message)


def moment(value):
    r.require(isinstance(value,str),'Timestamp required')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    r.require(result.tzinfo is not None,'Timezone-aware timestamp required')
    return result


def fresh(value,now):
    r.require(isinstance(now,datetime) and now.tzinfo is not None
        and 0<=(now-moment(value)).total_seconds()<=30,'Fresh capture within 30 seconds required')


def identity(obj,kind):
    meta=r.object_guard(obj,kind)
    r.require(not meta.get('ownerReferences') and not meta.get('deletionTimestamp'),
        'Unowned live original '+kind+' required')
    return {k:meta[k] for k in ('namespace','name','uid')}


def same_cm(actual,expected,*,bound=True):
    closed(actual,{'apiVersion','kind','metadata','immutable','data'},'Closed immutable ConfigMap readback required')
    am=identity(actual,'ConfigMap')
    r.require(actual['apiVersion']=='v1' and actual['immutable'] is True
        and actual['data']==expected['data']
        and all(am[k]==expected['metadata'][k] for k in ('namespace','name'))
        and (not bound or am['uid']==expected['metadata']['uid']),
        'Exact immutable ConfigMap data and actual custody required')



def runtime_binding(request):
    """Derive the one actual runtime Secret/key from the unchanged gateway spec."""
    p=request['previous_publication'];expected=p['expected_deployments']['gateway']
    pod=expected['spec']['template']['spec']
    container=next(c for c in pod['containers'] if c['name']==expected['container'])
    config=[e for e in container.get('env',[]) if e.get('name')=='CPS_COMPUTE_CONFIG']
    r.require(len(config)==1 and set(config[0])=={'name','value'}
        and isinstance(config[0]['value'],str) and config[0]['value'].startswith('/')
        and '..' not in config[0]['value'].split('/'),'One exact static gateway runtime path required')
    path=config[0]['value'];matches=[]
    for mount in container.get('volumeMounts',[]):
        prefix=mount.get('mountPath','').rstrip('/')
        if path.startswith(prefix+'/') and mount.get('readOnly') is True and 'subPath' not in mount:
            volumes=[v for v in pod['volumes'] if v.get('name')==mount.get('name') and 'secret' in v]
            if len(volumes)==1:
                relative=path[len(prefix)+1:];volume=volumes[0]['secret']
                key=relative
                if 'items' in volume:
                    items=[i for i in volume['items'] if i.get('path')==relative]
                    r.require(len(items)==1,'One actual mapped gateway runtime key required')
                    key=items[0]['key']
                r.require('/' not in key and key,'One exact gateway runtime Secret key required')
                matches.append((volume['secretName'],key))
    r.require(len(matches)==1,'One exact read-only runtime Secret projection required')
    return expected['namespace'],matches[0][0],matches[0][1]


def runtime_secret(actual,request,expected_data=None):
    r.require(isinstance(actual,dict) and set(actual) in ({'apiVersion','kind','metadata','type','data'},
        {'apiVersion','kind','metadata','type','data','immutable'}),'Closed actual gateway runtime Secret required')
    meta=identity(actual,'Secret');namespace,name,key=runtime_binding(request)
    r.require(actual['apiVersion']=='v1' and actual['type']=='Opaque'
        and actual.get('immutable') in (None,False) and isinstance(actual['data'],dict)
        and key in actual['data'] and (meta['namespace'],meta['name'])==(namespace,name)
        and (expected_data is None or (meta==identity(request['gateway_runtime'],'Secret')
            and actual['data']==expected_data)), 'Original exact mutable gateway runtime Secret custody and data required')
    try:
        config=r.parse(base64.b64decode(actual['data'][key],validate=True))
    except (ValueError,TypeError,UnicodeDecodeError):
        raise ValueError('Exact encoded gateway runtime JSON required') from None
    r.require(isinstance(config,dict),'Gateway runtime object required')
    return config,key


def runtime_intent(request,target_publication):
    previous_image, next_image = reviewed_pair(request)
    actual=request['gateway_runtime'];config,key=runtime_secret(actual,request)
    r.require(config.get('nativeGroupApprovals')==request['previous_publication']['runtime_settings']
        and config.get('policy_hash')==request['previous_publication']['policy_hash'],
        'Original complete image-bound gateway approval trust and policy required')
    target=copy.deepcopy(config)
    for c in HUBS:
        r.require(target['nativeGroupApprovals']['processes'][c]['image']==previous_image,
            'Exact old gateway trusted Hub image required')
        target['nativeGroupApprovals']['processes'][c]['image']=next_image
    r.require(target['nativeGroupApprovals']==target_publication['runtime_settings'],
        'New gateway trust must equal exact target publisher declarations')
    data=copy.deepcopy(actual['data']);data[key]=base64.b64encode(r.canonical(target).encode()).decode()
    planned=copy.deepcopy(actual);planned['data']=data
    return planned,r.replace_patch(actual,'/data',actual['data'],data)


def historical_projection(request,policy,qualification):
    """Bind renderer candidates through the completed journal's actual UIDs."""
    state=request.get('old_state',{})
    r.require(isinstance(state,dict),'Historical journal state required')
    journal=state.get('journal')
    required={'version','config_hash','publication','baselines','structural_prior','transition','process_names','role_guards'}
    r.require(isinstance(journal,dict) and required<=set(journal)<=required|{'process_refresh'}
        and type(journal['version']) is int and journal['version']==1
        and state.get('journal_sha256')==r.canonical_sha256(journal)
        and journal['publication']==request['previous_publication']
        and journal['transition'] is None and journal.get('process_refresh') is None
        and journal['structural_prior'] is False,
        'Exact completed historical journal projection custody required')
    previous=r._baselines(journal['baselines'],policy,qualification)
    r.require(set(previous)==set(r.COMPONENTS),'All four historical immutable projection pairs required')
    return journal['baselines']


def context(request,obs,now):
    policy=r.Policy(request['policy'])
    qualification=r.NativeGroupDeployment.from_config(request['qualification'],policy)
    p=request['previous_publication']
    rollover={'previous_publication_sha256','publisher_reinstall_required'}
    r.require(isinstance(p,dict) and set(p) in (PUBLICATION,PUBLICATION|{'initial_access'},
        PUBLICATION|rollover,PUBLICATION|rollover|{'initial_access'}), 'Closed installed publication required')
    r.require(type(p['version']) is int and p['version']==1 and p['requires_actual_process_ack'] is True
        and p['live_applied'] is False and p['process_readiness_verified'] is False
        and p['runtime_settings']['ttlSeconds']==30 and p['policy_hash']==policy.hash,
        'Unchanged qualified policy and 30-second acknowledgment TTL required')
    closed(obs,OBSERVATIONS,'Closed actual observation packet required')
    for key in ('documents','reference_maps','bootstrap_maps','acknowledgments','deployments','replicasets','pods'):
        closed(obs[key],r.COMPONENTS,'All four actual '+key+' required')
    source=obs['source']
    closed(source,{'version','source_raw','source_sha256','trusted_revision','captured_at'},
        'Authenticated protected capture v1 packet required')
    r.require(type(source['version']) is int and source['version']==1
        and isinstance(source['source_raw'],str),'Protected Source capture required')
    fresh(source['captured_at'],now)
    raw=source['source_raw'].encode()
    r.require(0<len(raw)<=1024*1024 and source['source_sha256']=='sha256:'+hashlib.sha256(raw).hexdigest()
        and source['trusted_revision']==p['revision'],'Exact unchanged trusted Source revision required')
    snapshot=r.ApprovalSnapshot.from_document(r.parse(raw),policy,qualification,expected_revision=p['revision'])
    closed(obs['epoch'],{'driver_epoch','captured_at'},'Independent protected epoch capture required')
    fresh(obs['epoch']['captured_at'],now)
    closed(obs['epoch']['driver_epoch'],{'node_uid','boot_id','driver_generation','gpu_uuid'},'Closed driver epoch required')
    epoch=r.DriverEpoch(**obs['epoch']['driver_epoch']);pool=qualification._config()['node_pool']
    r.require(epoch.__dict__=={k:pool[k] for k in epoch.__dict__},'Unchanged actual qualified driver epoch required')
    historical=historical_projection(request,policy,qualification)
    for c in r.COMPONENTS:
        revision=r.ApprovalRevision.from_configmap(obs['documents'][c],policy,qualification,expected_ref=p['references'][c])
        r.require(revision.document['registry']==snapshot.document,'Source bytes must describe the installed registry exactly')
        same_cm(obs['documents'][c],p['documents'][c],bound='uid' in p['documents'][c]['metadata'])
        same_cm(obs['reference_maps'][c],p['reference_maps'][c],bound='uid' in p['reference_maps'][c]['metadata'])
        same_cm(obs['documents'][c],historical[c]['previous_document'])
        same_cm(obs['reference_maps'][c],historical[c]['previous_reference'])
        ack=obs['acknowledgments'][c];am=identity(ack,'ConfigMap')
        r.require(ack.get('apiVersion')=='v1' and ack.get('immutable') in (None,False)
            and set(ack)<= {'apiVersion','kind','metadata','immutable','data'}
            and set(ack.get('data',{}))=={'ack.json'}
            and am==p['acknowledgment_references'][c], 'Original actual acknowledgment identity required')
    return policy,qualification,epoch


def bootstrap_data(p,c,qualification,epoch):
    if c=='node':
        return {'template.json':r.canonical(qualification._config()),
            'process.json':r.canonical(p['process_declarations'][c]),
            'acknowledgment.json':r.canonical(p['acknowledgment_references'][c])}
    return {'publisher.json':r.canonical({'version':1,'component':c,
        'acknowledgment':p['acknowledgment_references'][c],
        'process':p['process_declarations'][c],'driver_epoch':epoch.__dict__,'ttlSeconds':30})}


def publication_inputs(p,obs,qualification,epoch):
    r._publisher_scope(p)
    for c in r.COMPONENTS:
        candidate=r.immutable_config(obs['documents'][c],bootstrap_data(p,c,qualification,epoch),
            'cps-native-approval-bootstrap' if c=='node' else 'cps-native-approval-publisher')
        same_cm(obs['bootstrap_maps'][c],candidate,bound=False)
        same_cm(obs['bootstrap_maps'][c],p['bootstrap_maps'][c])
        dep=obs['deployments'][c];expected=p['expected_deployments'][c]
        r.require(identity(dep,'Deployment')=={k:expected[k] for k in ('namespace','name','uid')}
            and dep['spec']==expected['spec'],'Complete original Deployment identity and spec required')
        container=next(cn for cn in dep['spec']['template']['spec']['containers'] if cn['name']==expected['container'])
        volumes,mounts,env=r._installed_publication_rows(c,obs['documents'][c],obs['reference_maps'][c],obs['bootstrap_maps'][c])
        r.require([v for v in dep['spec']['template']['spec'].get('volumes',[]) if v.get('name') in r.OWNED_VOLUMES]==volumes
            and [m for m in container.get('volumeMounts',[]) if m.get('name') in r.OWNED_VOLUMES]==mounts
            and [e for e in container.get('env',[]) if e.get('name') in set(r.ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT',r.PUBLISHER_ENV}]==env,
            'Exact installed publication mount, environment and bootstrap required')


def role_guards(p,names,roles,original=None):
    rows={o['metadata']['namespace']+'/'+o['metadata']['name']:o for o in r._access_rows(p,names) if o['kind']=='Role'}
    closed(roles,rows,'Exact seven observed publisher Roles required')
    for key,actual in roles.items():
        closed(actual,{'apiVersion','kind','metadata','rules'},'Closed full actual Role required')
        am=identity(actual,'Role');expected=rows[key]
        r.require(actual['apiVersion']=='rbac.authorization.k8s.io/v1'
            and all(am[k]==expected['metadata'][k] for k in ('namespace','name'))
            and actual['rules']==expected['rules']
            and (original is None or am['uid']==original[key]['metadata']['uid']),
            'Original Role custody and exact singleton GET/own acknowledgment PATCH rules required')


def readiness(p,obs,policy,qualification,epoch,now):
    processes={}
    for c in r.COMPONENTS:
        processes[c]={k:p['process_declarations'][c][k] for k in ('namespace','container','image','service_account')}
        processes[c].update(name=obs['pods'][c]['metadata']['name'],uid=obs['pods'][c]['metadata']['uid'])
    return r.readiness_intent(projection=p,documents=obs['documents'],policy=policy,qualification=qualification,
        **{k:obs[k] for k in ('deployments','replicasets','pods')},expected_processes=processes,
        acknowledgments={c:r.parse(obs['acknowledgments'][c]['data']['ack.json']) for c in r.COMPONENTS},
        driver_epoch=epoch,now=now,ttl_seconds=30)


def lineage(request,obs,names):
    state=request['old_state']
    closed(state,{'seed','seed_sha256','journal','journal_sha256','controller','journal_pvc','next_journal','next_input_secret'},
        'Closed previous controller custody and separate new journal identities required')
    seed=state['seed'];journal=state['journal']
    closed(seed,{'version','policy','qualification','previous_publication','previous_publication_sha256','baselines','ttlSeconds'},
        'Closed previous seed required')
    r.require(type(seed['version']) is int and seed['version']==1 and seed['ttlSeconds']==30
        and seed['policy']==request['policy'] and seed['qualification']==request['qualification']
        and seed['previous_publication_sha256']==r.canonical_sha256(seed['previous_publication'])
        and state['seed_sha256']==r.canonical_sha256(seed)
        and state['journal_sha256']==r.canonical_sha256(journal),'Exact original seed and journal hashes required')
    required={'version','config_hash','publication','baselines','structural_prior','transition','process_names','role_guards'}
    r.require(isinstance(journal,dict) and required<=set(journal)<=required|{'process_refresh'}
        and type(journal['version']) is int and journal['version']==1
        and journal['config_hash']==state['seed_sha256'] and journal['publication']==request['previous_publication']
        and journal['transition'] is None and journal.get('process_refresh') is None
        and journal['structural_prior'] is False and journal['process_names']==names,
        'Completed genuine prior journal; no pending transition or structural readiness required')
    for c in r.COMPONENTS:
        row=journal['baselines'][c];expected=request['previous_publication']['expected_deployments'][c]
        r.require(row['container']==expected['container'] and row['deployment']['spec']==obs['deployments'][c]['spec']
            and identity(row['deployment'],'Deployment')==identity(obs['deployments'][c],'Deployment'),
            'Complete current journal Deployment custody required')
        same_cm(row['previous_document'],obs['documents'][c]);same_cm(row['previous_reference'],obs['reference_maps'][c])
    r.require(journal['role_guards']=={k:{'uid':v['metadata']['uid'],'rules':v['rules']} for k,v in obs['roles'].items()},
        'All current journal Role custody required')
    controller=state['controller'];cm=identity(controller,'Deployment');pvc=state['journal_pvc'];pm=identity(pvc,'PersistentVolumeClaim')
    pod=controller['spec']['template']['spec']
    r.require(controller['apiVersion']=='apps/v1' and cm['namespace']=='cps-compute'
        and cm['name']=='cps-native-approval-delivery' and controller['spec']['replicas']==0
        and pod['serviceAccountName']=='cps-native-approval-delivery'
        and pvc['apiVersion']=='v1' and pvc.get('status',{}).get('phase')=='Bound'
        and pm['namespace']==cm['namespace'] and len([v for v in pod['volumes'] if v.get('name')=='journal'
            and v.get('persistentVolumeClaim')=={'claimName':pm['name']}])==1,
        'Paused exact controller and preserved bound prior journal PVC required')
    retained_secret_names={v['secret']['secretName'] for v in pod['volumes'] if 'secret' in v}
    for key in ('next_journal','next_input_secret'):
        v=state[key];closed(v,{'namespace','name'},'Closed new isolated object name required')
        r.require(v['namespace']==cm['namespace'] and isinstance(v['name'],str)
            and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',v['name']) is not None
            and v['name'] not in {pm['name'],cm['name']}|retained_secret_names,'Distinct bounded new journal/input names required')
    r.require(state['next_journal']!=state['next_input_secret'],'Separate new journal and input names required')
    return {'previous_seed_sha256':state['seed_sha256'],'previous_journal_sha256':state['journal_sha256'],
        'previous_publication_sha256':request['previous_publication_sha256'],'controller':cm,
        'controller_resource_version':controller['metadata']['resourceVersion'],
        'controller_spec_sha256':r.canonical_sha256(controller['spec']),'previous_journal_pvc':pm,
        'previous_journal_pvc_spec_sha256':r.canonical_sha256(pvc['spec']),
        'next_journal':copy.deepcopy(state['next_journal']),'next_input_secret':copy.deepcopy(state['next_input_secret'])}


def reviewed_pair(request):
    closed(request['reviewed_images'],HUBS,'Only both reviewed Hub images may change')
    pairs = []
    for c,image in request['reviewed_images'].items():
        closed(image,{'previous','next'},'Closed reviewed immutable image pair required')
        pair = image['previous'], image['next']
        r.require(pair in REVIEWED_PAIRS,'Only an exact reviewed package image pair is permitted')
        pairs.append(pair)
    r.require(pairs[0] == pairs[1], 'Both Hubs must use the same reviewed image pair')
    return pairs[0]


def plan_intent(request,*,now):
    closed(request,REQUEST,'Closed operator-only reviewed image handover packet required')
    r.require(type(request['version']) is int and request['version']==1
        and request['previous_publication_sha256']==r.canonical_sha256(request['previous_publication']),
        'Exact pinned current reviewed publication required')
    previous_image, next_image = reviewed_pair(request)
    obs=request['observations'];policy,qualification,epoch=context(request,obs,now);p=request['previous_publication']
    publication_inputs(p,obs,qualification,epoch)
    names=r._revision_process_names(p,**{k:obs[k] for k in ('deployments','replicasets','pods')})
    role_guards(p,names,obs['roles']);readiness(p,obs,policy,qualification,epoch,now)
    r.require(obs['gateway_runtime']==request['gateway_runtime'],
        'Exact original observed gateway runtime Secret required')
    chain=lineage(request,obs,names);target=copy.deepcopy(p);candidates={};patches={}
    for c in HUBS:
        r.require(p['process_declarations'][c]['image']==previous_image,'Exact old Hub image required')
        target['process_declarations'][c]['image']=next_image
    target['runtime_settings']['processes']=copy.deepcopy(target['process_declarations'])
    for c in HUBS:
        data=bootstrap_data(target,c,qualification,epoch)
        bootstrap=r.immutable_config(obs['documents'][c],data,'cps-native-approval-publisher')
        candidates[c]=bootstrap;target['bootstrap_maps'][c]=copy.deepcopy(bootstrap)
        dep=obs['deployments'][c];spec=copy.deepcopy(dep['spec']);pod=spec['template']['spec']
        next(cn for cn in pod['containers'] if cn['name']==target['expected_deployments'][c]['container'])['image']=next_image
        next(v for v in pod['volumes'] if v['name']==r.PUBLISHER_VOLUME)['configMap']['name']=bootstrap['metadata']['name']
        patches[c]=r.replace_patch(dep,'/spec',dep['spec'],spec)
        target['patches'][c]=copy.deepcopy(patches[c]);target['expected_deployments'][c]['spec']=spec
        target['baseline_guards'][c]={'uid':dep['metadata']['uid'],'resourceVersion':dep['metadata']['resourceVersion'],
            'spec_sha256':r.canonical_sha256(dep['spec'])}
    r._publisher_scope(target)
    runtime_target,runtime_patch=runtime_intent(request,target)
    chain.update(gateway_runtime=identity(request['gateway_runtime'],'Secret'),
        gateway_runtime_resource_version=request['gateway_runtime']['metadata']['resourceVersion'],
        previous_gateway_runtime_data_sha256=r.canonical_sha256(request['gateway_runtime']['data']),
        next_gateway_runtime_data_sha256=r.canonical_sha256(runtime_target['data']))
    return {'version':1,'kind':'qualified-hub-package-handover','request':copy.deepcopy(request),
        'request_sha256':r.canonical_sha256(request),'planned_at':now.isoformat(),'projection':target,
        'bootstrap_candidates':candidates,'deployment_patches':patches,'lineage':chain,'ready':False,
        'gateway_runtime_target':runtime_target,'gateway_runtime_patch':runtime_patch,
        'gateway_pod_restart_precondition':{k:obs['pods']['gateway']['metadata'][k] for k in ('namespace','name','uid')}}


def validated_plan(plan):
    closed(plan,PLAN,'Closed reviewed operator handover intent required')
    expected=plan_intent(plan['request'],now=moment(plan['planned_at']))
    r.require(plan==expected,'Handover intent differs from its complete independently reproducible request')
    return plan['projection']


def post_inputs(plan,obs,now):
    p=validated_plan(plan);request=plan['request']
    policy,qualification,epoch=context(request,obs,now)
    config,_=runtime_secret(obs['gateway_runtime'],request,plan['gateway_runtime_target']['data'])
    r.require(config['nativeGroupApprovals']==p['runtime_settings']
        and obs['pods']['gateway']['metadata']['uid']!=plan['gateway_pod_restart_precondition']['uid'],
        'Exact new gateway trusted configuration and genuine replacement gateway Pod required')
    target=copy.deepcopy(p)
    for c in r.COMPONENTS:
        same_cm(obs['bootstrap_maps'][c],p['bootstrap_maps'][c],bound=c not in HUBS)
        target['bootstrap_maps'][c]=copy.deepcopy(obs['bootstrap_maps'][c])
    publication_inputs(target,obs,qualification,epoch)
    return target,policy,qualification,epoch


def process_access_intent(plan,observations,*,now):
    p,_,_,_=post_inputs(plan,observations,now)
    old=plan['request']['previous_publication'];prior=plan['request']['observations']
    old_names=r._revision_process_names(old,**{k:prior[k] for k in ('deployments','replicasets','pods')})
    names=r._revision_process_names(p,**{k:observations[k] for k in ('deployments','replicasets','pods')},permission_bootstrap=True)
    role_guards(old,old_names,observations['roles'],prior['roles'])
    targets={o['metadata']['namespace']+'/'+o['metadata']['name']:o for o in r._access_rows(p,names) if o['kind']=='Role'}
    patches={k:r.replace_patch(actual,'/rules',actual['rules'],targets[k]['rules']) for k,actual in observations['roles'].items()}
    return {'version':1,'kind':'qualified-hub-package-process-access','plan_sha256':r.canonical_sha256(plan),
        'observations':copy.deepcopy(observations),'captured_at':now.isoformat(),
        'role_patches':patches,'actual_process_names':names,'bootstrap_maps':copy.deepcopy(observations['bootstrap_maps']),
        'ready':False,'requires_actual_fresh_acknowledgments':True}


def finalize_intent(plan,access,observations,*,now):
    closed(access,ACCESS,'Closed actual structural permission readback required')
    r.require(access==process_access_intent(plan,access['observations'],now=moment(access['captured_at'])),
        'Exact independently reproducible structural permission intent required')
    p,policy,qualification,epoch=post_inputs(plan,observations,now)
    for c in r.COMPONENTS:
        same_cm(observations['bootstrap_maps'][c],access['bootstrap_maps'][c])
    names=r._revision_process_names(p,**{k:observations[k] for k in ('deployments','replicasets','pods')})
    role_guards(p,names,observations['roles'],plan['request']['observations']['roles'])
    proof=readiness(p,observations,policy,qualification,epoch,now)
    baselines={c:{'deployment':copy.deepcopy(observations['deployments'][c]),'container':p['process_declarations'][c]['container'],
        'previous_document':copy.deepcopy(observations['documents'][c]),
        'previous_reference':copy.deepcopy(observations['reference_maps'][c])} for c in r.COMPONENTS}
    seed={'version':1,'policy':copy.deepcopy(plan['request']['policy']),'qualification':copy.deepcopy(plan['request']['qualification']),
        'previous_publication':p,'previous_publication_sha256':r.canonical_sha256(p),'baselines':baselines,'ttlSeconds':30}
    return {'version':1,'kind':'qualified-hub-package-handover-readback','ready':True,'publication':p,
        'readiness':proof,'seed':seed,'seed_sha256':r.canonical_sha256(seed),'plan_sha256':r.canonical_sha256(plan),
        'lineage':{**copy.deepcopy(plan['lineage']),'next_seed_sha256':r.canonical_sha256(seed),
            'next_publication_sha256':r.canonical_sha256(p)},'old_journal_must_remain_untouched':True,
        'requires_new_empty_journal':True,'production_qualified':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('plan','process-access','finalize'))
    parser.add_argument('--input',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.phase is None:
        print('Inert: no API, Source, GPU or filesystem mutation performed.');return 0
    r.require(args.input is not None and args.output is not None,'Private input and new output directory required')
    request=r._private_json(args.input);now=datetime.now(timezone.utc)
    if args.phase=='plan':result=plan_intent(request,now=now)
    else:
        closed(request,{'version','plan','observations'}|({'access'} if args.phase=='finalize' else set()),
            'Closed plan and fresh actual readbacks required')
        r.require(type(request['version']) is int and request['version']==1,'Request version1 required')
        result=(process_access_intent(request['plan'],request['observations'],now=now) if args.phase=='process-access'
            else finalize_intent(request['plan'],request['access'],request['observations'],now=now))
    args.output.mkdir(mode=0o700,parents=False,exist_ok=False)
    target=args.output/'intent.json'
    with target.open('x',encoding='utf-8') as handle:
        os.chmod(target,0o600);handle.write(r.canonical(result)+'\n')
    print(r.canonical({'version':1,'phase':args.phase,'ready':result['ready'],
        'output_sha256':'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest(),'live_applied':False}))
    return 0


if __name__=='__main__':raise SystemExit(main())
