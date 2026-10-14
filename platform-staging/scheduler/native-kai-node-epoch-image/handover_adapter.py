"""Single-node adapter for the pinned sealed four-process handover protocol.

The upstream protocol phases and schema stay unchanged. This adapter admits one
exact image pair and removes the exact code projection masking that image.
Nothing here invokes Kubernetes, changes a journal, or claims currentness.
"""
import base64,copy
import hashlib
import importlib.util
from pathlib import Path

HELPER_SHA='fb88d3c9f01932c2454ad22db0ce60ad9afaa1b1f9975e82dade32509e318ec5'
OLD_IMAGE='ghcr.io/mul-cps/cps-compute:qualification-native-node-980408a@sha256:5079458fe0fcb3c11231b21f1bbc1f4c12ad3ac578799932aa0bc9f46d5510c7'
NEW_IMAGE='ghcr.io/mul-cps/cps-compute@sha256:8c2c456b90330622645d509f94882a11a465ac208a6fa7fc824900d6320e5c0b'


def need(ok,text):
    if not ok:raise ValueError(text)


class NodeHandover:
    def __init__(self,h,code,capture_input):
        need(hashlib.sha256(Path(h.__file__).read_bytes()).hexdigest()==HELPER_SHA,'Exact sealed helper required')
        self.h=h;self.r=h.r;self.code=copy.deepcopy(code)
        self.capture_input=copy.deepcopy(capture_input)
        cm=capture_input['metadata']
        need(capture_input.get('immutable') is True and capture_input.get('type')=='Opaque'
             and cm['namespace']=='cps-compute' and cm['name']=='cps-native-approval-capture-input'
             and cm['uid']=='c575bd98-0137-44d9-b27a-b306be394b75' and cm['resourceVersion']=='368234908'
             and not cm.get('deletionTimestamp') and not cm.get('ownerReferences')
             and set(capture_input['data'])=={'config.json','qualification.json','export.token'}
             and self.r.canonical_sha256(capture_input['data'])=='sha256:63e6858d19cffad8910d9ddc63836f9265eaebeee22f3eb1b7e4e37cfe551a6c',
             'Exact immutable capture input custody and all opaque bytes required')
        # Verify the complete code object before changing the helper instance.
        meta=code.get('metadata',{})
        need(code.get('apiVersion')=='v1' and code.get('kind')=='ConfigMap' and code.get('immutable') is True
             and meta.get('namespace')=='cps-native-system' and meta.get('name')=='cps-native-node-code-458e77184d1a5c56'
             and meta.get('uid')=='6e67ad3a-3379-4f05-bc70-ca6b781d6f0e' and meta.get('resourceVersion')=='367985380'
             and not meta.get('deletionTimestamp') and not meta.get('ownerReferences') and not code.get('binaryData'),
             'Exact immutable retained code custody required')
        root=Path(__file__).parent
        expected={p.name:p.read_bytes() for p in (root/'bundle').iterdir() if p.name!='native_operator_epoch.py'}
        expected['node_agent.py']=(root/'tests/original-node-agent.py').read_bytes()
        need(set(code['data'])==set(expected) and all(v.encode()==expected[k] for k,v in code['data'].items()),
             'Exact original fifteen-file code bytes required')
        s=importlib.util.spec_from_file_location('node_image_plan',root/'plan.py')
        self.image_plan=importlib.util.module_from_spec(s);s.loader.exec_module(self.image_plan)
        h.HUBS=('node',);h.REVIEWED_IMAGE=OLD_IMAGE;h.ACCOUNT_IMAGE=NEW_IMAGE
        h.PLAN=h.PLAN|{'capture_input_candidate','capture_input_preimage'}
        h.reviewed_pair=self.reviewed_pair;h.plan_intent=self.plan_intent

    def reviewed_pair(self,request):
        self.h.closed(request['reviewed_images'],{'node'},'Only exact Node image may change')
        pair=request['reviewed_images']['node'];self.h.closed(pair,{'previous','next'},'Closed exact Node pair required')
        need((pair['previous'],pair['next'])==(OLD_IMAGE,NEW_IMAGE),'Only exact tested507-to8c2 pair admitted')
        return OLD_IMAGE,NEW_IMAGE

    def plan_intent(self,request,*,now):
        h,r=self.h,self.r
        h.closed(request,h.REQUEST,'Closed existing sealed handover request required')
        need(type(request['version']) is int and request['version']==1
             and request['previous_publication_sha256']==r.canonical_sha256(request['previous_publication']),
             'Exact pinned current publication required')
        self.reviewed_pair(request)
        obs=request['observations'];policy,qualification,epoch=h.context(request,obs,now)
        old=request['previous_publication'];h.publication_inputs(old,obs,qualification,epoch)
        names=r._revision_process_names(old,**{k:obs[k] for k in ('deployments','replicasets','pods')})
        h.role_guards(old,names,obs['roles']);h.readiness(old,obs,policy,qualification,epoch,now)
        need(obs['gateway_runtime']==request['gateway_runtime'],'Exact observed runtime custody required')
        chain=h.lineage(request,obs,names);target=copy.deepcopy(old)
        target['process_declarations']['node']['image']=NEW_IMAGE
        target['runtime_settings']['processes']=copy.deepcopy(target['process_declarations'])
        candidate=r.immutable_config(obs['documents']['node'],h.bootstrap_data(target,'node',qualification,epoch),
                                     'cps-native-approval-bootstrap')
        delta=self.image_plan.v2(obs['deployments']['node'],self.code,obs['bootstrap_maps']['node'])
        expected=delta['create_bootstrap']
        need(candidate['metadata']['name']==expected['metadata']['name'] and candidate['data']==expected['data'],
             'Sealed node bootstrap must match independently derived image delta')
        target['bootstrap_maps']['node']=copy.deepcopy(candidate)
        target['patches']['node']=copy.deepcopy(delta['patch'])
        target['expected_deployments']['node']['spec']=copy.deepcopy(delta['after_spec'])
        dep=obs['deployments']['node']
        target['baseline_guards']['node']={'uid':dep['metadata']['uid'],'resourceVersion':dep['metadata']['resourceVersion'],
                                         'spec_sha256':r.canonical_sha256(dep['spec'])}
        capture=self.capture_candidate(old)
        gateway=obs['deployments']['gateway'];gs=copy.deepcopy(gateway['spec'])
        volumes=[v for v in gs['template']['spec']['volumes'] if v['name']=='capture-seed']
        need(len(volumes)==1 and volumes[0]['secret']['secretName']==self.capture_input['metadata']['name'],
             'Exact retained Gateway capture seed volume required')
        volumes[0]['secret']['secretName']=capture['metadata']['name']
        target['expected_deployments']['gateway']['spec']=gs
        target['patches']['gateway']=r.replace_patch(gateway,'/spec',gateway['spec'],gs)
        target['baseline_guards']['gateway']={'uid':gateway['metadata']['uid'],'resourceVersion':gateway['metadata']['resourceVersion'],
                                             'spec_sha256':r.canonical_sha256(gateway['spec'])}
        r._publisher_scope(target);runtime_target,runtime_patch=h.runtime_intent(request,target)
        chain.update(gateway_runtime=h.identity(request['gateway_runtime'],'Secret'),
            gateway_runtime_resource_version=request['gateway_runtime']['metadata']['resourceVersion'],
            previous_gateway_runtime_data_sha256=r.canonical_sha256(request['gateway_runtime']['data']),
            next_gateway_runtime_data_sha256=r.canonical_sha256(runtime_target['data']))
        return {'version':1,'kind':'qualified-hub-package-handover','request':copy.deepcopy(request),
            'request_sha256':r.canonical_sha256(request),'planned_at':now.isoformat(),'projection':target,
            'bootstrap_candidates':{'node':candidate},'deployment_patches':{'node':copy.deepcopy(delta['patch']),
                'gateway':copy.deepcopy(target['patches']['gateway'])},
            'capture_input_candidate':capture,'capture_input_preimage':copy.deepcopy(self.capture_input),
            'lineage':chain,'ready':False,'gateway_runtime_target':runtime_target,'gateway_runtime_patch':runtime_patch,
            'gateway_pod_restart_precondition':{k:obs['pods']['gateway']['metadata'][k] for k in ('namespace','name','uid')}}

    def validate_scope(self,plan):
        self.h.validated_plan(plan)
        old=plan['request']['previous_publication'];target=plan['projection']
        need(set(plan['deployment_patches'])=={'node','gateway'} and set(plan['bootstrap_candidates'])=={'node'},
             'Only Node plus exact Gateway capture-seed companion permitted')
        for c in set(self.r.COMPONENTS)-{'node'}:
            for field in ('process_declarations','bootstrap_maps','documents','reference_maps',
                          'references','acknowledgment_references'):
                need(target[field][c]==old[field][c],'Peer image/spec/projection/custody cannot change')
            expected=copy.deepcopy(old['expected_deployments'][c])
            if c=='gateway':
                volume=next(v for v in expected['spec']['template']['spec']['volumes'] if v['name']=='capture-seed')
                volume['secret']['secretName']=plan['capture_input_candidate']['metadata']['name']
            need(target['expected_deployments'][c]==expected,'Only exact Gateway capture-seed volume may change')
        before,_=self.h.runtime_secret(plan['request']['gateway_runtime'],plan['request'])
        after,_=self.h.runtime_secret(plan['gateway_runtime_target'],plan['request'])
        expected=copy.deepcopy(before);expected['nativeGroupApprovals']['processes']['node']['image']=NEW_IMAGE
        need(after==expected,'Only existing runtime Node trust image may change')
        need(plan['request']['policy']==plan['request']['old_state']['seed']['policy']
             and plan['request']['qualification']==plan['request']['old_state']['seed']['qualification'],
             'Whole policy, native scopes and qualified history must remain exact')
        return target

    def capture_candidate(self,previous):
        cfg=self.r.parse(base64.b64decode(self.capture_input['data']['config.json'],validate=True))
        need(cfg['node_process']==previous['process_declarations']['node'],'Exact captured current Node declaration required')
        cfg['node_process']['image']=NEW_IMAGE
        data=copy.deepcopy(self.capture_input['data']);data['config.json']=base64.b64encode(self.r.canonical(cfg).encode()).decode()
        name='cps-native-approval-capture-node-'+self.r.canonical_sha256(data).split(':')[1][:16]
        return {'apiVersion':'v1','kind':'Secret','type':'Opaque','immutable':True,
            'metadata':{'namespace':'cps-compute','name':name},'data':data}


def install(helper,node_code,capture_input):
    return NodeHandover(helper,node_code,capture_input)


class RestoreHandover:
    """Pre-activation inverse using fresh ACKs and a new empty journal.

    This does not resume an old journal or adopt a completed successor. The
    operator must prove the original delivery controller is still paused and
    the forward lineage names remain unused before invoking it.
    """
    def __init__(self,forward_adapter):
        self.a=forward_adapter;self.h=forward_adapter.h;self.r=forward_adapter.r
        self.original_validated=self.h.validated_plan
        self.original_post=self.h.post_inputs
        self.original_access=self.h.process_access_intent

    def plan(self,forward,roles,runtime,gateway,access):
        self.a.validate_scope(forward);h,r=self.h,self.r
        prior=forward['request']['observations']['roles']
        h.closed(roles,prior,'Exact seven retained inverse Role objects required')
        if access is not None:
            need(access==self.original_access(forward,access['observations'],now=h.moment(access['captured_at'])),
                 'Only exact owned forward process-access intent admitted')
        for k,row in roles.items():
            need(h.identity(row,'Role')==h.identity(prior[k],'Role') and row['rules'] in
                 ([prior[k]['rules']] if access is None else [prior[k]['rules'],access['role_patches'][k][-1]['value']]),
                 'Inverse cannot adopt foreign Role custody or rules')
        original=forward['request']['gateway_runtime']
        need(h.identity(runtime,'Secret')==h.identity(original,'Secret') and runtime['data'] in
             (original['data'],forward['gateway_runtime_target']['data']),'Only exact known runtime states admitted')
        need(gateway['metadata']['namespace']==forward['gateway_pod_restart_precondition']['namespace'],
             'Exact retained Gateway namespace required')
        auth={'forward':copy.deepcopy(forward),'roles':copy.deepcopy(roles),'runtime':copy.deepcopy(runtime),
              'gateway':copy.deepcopy(gateway),'access':copy.deepcopy(access)}
        request=copy.deepcopy(forward['request']);request['gateway_runtime']=copy.deepcopy(runtime)
        request['observations']['gateway_runtime']=copy.deepcopy(runtime);request['observations']['roles']=copy.deepcopy(roles)
        target=copy.deepcopy(forward['request']['previous_publication'])
        lineage=copy.deepcopy(forward['lineage']);lineage.update(gateway_runtime=h.identity(runtime,'Secret'),
            gateway_runtime_resource_version=runtime['metadata']['resourceVersion'],
            previous_gateway_runtime_data_sha256=r.canonical_sha256(runtime['data']),
            next_gateway_runtime_data_sha256=r.canonical_sha256(original['data']))
        return {'version':1,'kind':'qualified-node-package-inverse','request':request,'request_sha256':r.canonical_sha256(request),
            'planned_at':forward['planned_at'],'projection':target,
            'bootstrap_candidates':{'node':copy.deepcopy(target['bootstrap_maps']['node'])},
            'deployment_patches':{'node':copy.deepcopy(forward['deployment_patches']['node'])},
            'lineage':lineage,'ready':False,'gateway_runtime_target':copy.deepcopy(original),
            'gateway_runtime_patch':r.replace_patch(runtime,'/data',runtime['data'],original['data']),
            'gateway_pod_restart_precondition':{k:gateway['metadata'][k] for k in ('namespace','name','uid')},
            'inverse_authorization':auth}

    def validate(self,plan):
        auth=plan.get('inverse_authorization',{})
        self.h.closed(auth,{'forward','roles','runtime','gateway','access'},'Closed inverse authority required')
        need(plan==self.plan(auth['forward'],auth['roles'],auth['runtime'],auth['gateway'],auth['access']),
             'Exact independently reproducible original-spec inverse required')
        return copy.deepcopy(plan['projection'])

    def post(self,plan,obs,now):
        p=self.validate(plan);h=self.h
        policy,qualification,epoch=h.context(plan['request'],obs,now)
        config,_=h.runtime_secret(obs['gateway_runtime'],plan['request'],plan['gateway_runtime_target']['data'])
        need(config['nativeGroupApprovals']==p['runtime_settings'] and
             obs['pods']['gateway']['metadata']['uid']!=plan['gateway_pod_restart_precondition']['uid'],
             'Actual replacement Gateway must consume the exact restored trust configuration')
        # All original immutable projection/ACK references and full specs are
        # retained, including original code projection and physical history.
        h.publication_inputs(p,obs,qualification,epoch)
        return p,policy,qualification,epoch

    def process_access(self,plan,obs,*,now):
        p,_,_,_=self.post(plan,obs,now);h,r=self.h,self.r
        prior=plan['inverse_authorization']['roles'];h.closed(obs['roles'],prior,'Exact inverse Role set required')
        need(all(h.identity(obs['roles'][k],'Role')==h.identity(prior[k],'Role') and
                 obs['roles'][k]['rules']==prior[k]['rules'] for k in prior),'Exact pre-inverse Role custody/rules required')
        names=r._revision_process_names(p,**{k:obs[k] for k in ('deployments','replicasets','pods')},permission_bootstrap=True)
        targets={o['metadata']['namespace']+'/'+o['metadata']['name']:o for o in r._access_rows(p,names) if o['kind']=='Role'}
        return {'version':1,'kind':'qualified-hub-package-process-access','plan_sha256':r.canonical_sha256(plan),
            'observations':copy.deepcopy(obs),'captured_at':now.isoformat(),
            'role_patches':{k:r.replace_patch(row,'/rules',row['rules'],targets[k]['rules']) for k,row in obs['roles'].items()},
            'actual_process_names':names,'bootstrap_maps':copy.deepcopy(obs['bootstrap_maps']),
            'ready':False,'requires_actual_fresh_acknowledgments':True}

    def install(self):
        h=self.h
        h.validated_plan=lambda p:self.validate(p) if p.get('kind')=='qualified-node-package-inverse' else self.original_validated(p)
        h.post_inputs=lambda p,o,n:self.post(p,o,n) if p.get('kind')=='qualified-node-package-inverse' else self.original_post(p,o,n)
        h.process_access_intent=lambda p,o,now:self.process_access(p,o,now=now) if p.get('kind')=='qualified-node-package-inverse' else self.original_access(p,o,now=now)
        return self
