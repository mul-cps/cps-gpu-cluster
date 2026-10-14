"""CPU counterexamples for separate, process-observed approval authority."""
import copy
from dataclasses import replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import node_agent as base
from test_node_agent import EnrollmentTest, POD, BINDING, NODE, GPU


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(v):return 'sha256:'+hashlib.sha256(canonical(v).encode()).hexdigest()


class ApprovalNodeTest(unittest.TestCase):
    def setUp(self):
        self.mod=importlib.import_module('native_approval_revision')
        self.fixture=EnrollmentTest();self.fixture.setUp();self.models=self.fixture.models
        _,self.record,_=self.fixture.retired_cleanup_fixture()
        self.pool=dict(self.fixture.config['pool'],total_memory_mib=40960,free_memory_mib=40470,
            headroom_mib=1024,memory_budget_mib=15360,boot_id=self.record.identity.boot_id,
            driver_generation=self.record.identity.driver_generation)
        self.config=dict(version=2,enabled=True,mode='qualified-group',authority_namespace='cps-native-authority',
            policy_hash=self.fixture.config['policy_hash'],pool=self.pool,
            workspaces={'cps:old':{'profile':'interactive-shared-5','cap_mib':5120}})
        self.approval=dict(owner='neutral-new',server='group',members=['person:one','person:two'],
            principal='workspace:cps:new',profiles=['interactive-shared-5'],ceiling={'cpu':'4','memory':'16Gi','gpuMemoryGiB':5},
            namespace='jupyterhub',pod='jupyter-new',group_id='group-new',course_id='course-new',term_id='term-new',
            storage=dict(namespace='jupyterhub',pvc='group-new',pv='pv-group-new',path='/mnt/groups/new',
                group_hash='c'*64,storage_version=2,readonly_mounts=[]))
        self.template=dict(enabled=True,policy_hash=self.config['policy_hash'],node_pool=self.pool,
            authorityNamespace='cps-native-authority',gateImage='example/gate@sha256:'+'d'*64,
            workloadImage='example/workload@sha256:'+'e'*64,
            evidence={'profile_caps':{'interactive-shared-5':5120,'interactive-shared-10':10240}},
            evidence_sha256='sha256:'+'f'*64,workspaces={})
        self.cm,self.ref=self.document({'cps:new':self.approval})

    def document(self,approvals,generation=1,history=None):
        registry=dict(version=1,generation=generation,deployment=dict(self.template,workspaces=approvals))
        revision=sha(registry);body=dict(version=1,revision=revision,policy_hash=self.config['policy_hash'],registry=registry,history=history or [])
        cm=dict(apiVersion='v1',kind='ConfigMap',immutable=True,
            metadata=dict(namespace='cps-native-authority',name='cps-native-approvals-'+revision[7:47],
                uid='55555555-5555-4555-8555-555555555555',resourceVersion='12'),data={'approval.json':canonical(body)})
        ref=dict(namespace=cm['metadata']['namespace'],name=cm['metadata']['name'],uid=cm['metadata']['uid'],
            data_sha256=sha(cm['data']),revision=revision,policy_hash=self.config['policy_hash'])
        return cm,ref

    def consumer(self,maps=None):
        maps=maps or {self.ref['name']:self.cm}
        return self.mod.ApprovalConsumer(base,self.config,self.template,self.ref,
            lambda namespace,name:copy.deepcopy(maps.get(name)))

    def enrollment(self):
        body=copy.deepcopy(self.fixture.enrollment)
        body.update(workspace='new',principal='workspace:cps:new',profile='interactive-shared-5',name='jupyter-new',approval_ref=self.ref)
        body['intent']['name']='jupyter-new';cm=copy.deepcopy(self.fixture.cm);cm['data']['enrollment.json']=canonical(body)
        return cm,body

    def test_current_new_scope_preserves_base(self):
        cm,body=self.enrollment();before=copy.deepcopy(self.config)
        with self.assertRaises(ValueError):base.validate_enrollment(cm,self.config,self.models)
        self.assertEqual(self.consumer().validate_enrollment(cm,self.models)['enrollment'],body)
        self.assertEqual(self.config,before)

    def test_actual_document_uid_revision_full_hash_and_canonical_bytes_are_required(self):
        for fault in ('uid','revision','data','mutable','namespace','owner','noncanonical','unknown'):
            with self.subTest(fault=fault):
                cm=copy.deepcopy(self.cm)
                if fault=='uid':cm['metadata']['uid']=NODE
                elif fault=='revision':cm['data']['approval.json']=cm['data']['approval.json'].replace(self.ref['revision'],'sha256:'+'0'*64)
                elif fault=='data':cm['data']['extra']='untrusted'
                elif fault=='mutable':cm['immutable']=False
                elif fault=='namespace':cm['metadata']['namespace']='jupyterhub'
                elif fault=='owner':cm['metadata']['ownerReferences']=[{'uid':POD}]
                elif fault=='noncanonical':cm['data']['approval.json']=json.dumps(json.loads(cm['data']['approval.json']))
                else:
                    body=json.loads(cm['data']['approval.json']);body['unknown']=True;cm['data']['approval.json']=canonical(body)
                with self.assertRaises(ValueError):self.consumer({self.ref['name']:cm}).current()

    def test_members_pod_profile_and_reference_cannot_override_approval(self):
        cm,_=self.enrollment()
        for fault in ('members','name','profile','reference'):
            with self.subTest(fault=fault):
                changed=copy.deepcopy(cm);body=json.loads(changed['data']['enrollment.json'])
                if fault=='members':body['members']=['person:outsider']
                elif fault=='name':body['name']='jupyter-other';body['intent']['name']='jupyter-other'
                elif fault=='profile':body['profile']='interactive-shared-10';body['cap_mib']=10240;body['intent']['cap_mib']=10240
                else:body['approval_ref']['uid']=NODE
                changed['data']['enrollment.json']=canonical(body)
                with self.assertRaises(ValueError):self.consumer().validate_enrollment(changed,self.models)

    def terminal_values(self,root,legacy=False):
        cm,body=self.enrollment();consumer=self.consumer()
        if legacy:
            self.config['workspaces']={'cps:new':{'profile':'interactive-shared-5','cap_mib':5120}}
            del body['approval_ref'];cm['data']['enrollment.json']=canonical(body)
            envelope=base.validate_enrollment(cm,self.config,self.models)
        else:envelope=consumer.validate_enrollment(cm,self.models)
        store=base.EnrollmentStore(root,self.models,trusted_uid=os.getuid());store.synchronize([envelope])
        if not legacy:consumer.remember(envelope,store)
        record=replace(self.record,intent=self.models.CapIntent(**body['intent']))
        completion=base.cleanup_object(envelope,record);completion['metadata'].update(uid='66666666-6666-4666-8666-666666666666',resourceVersion='13')
        store.mark_cleanup_published(POD,envelope,completion,record)
        ledger=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(namespace='cps-native-authority',name='cps-native-gpu-allocations',
            uid='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',resourceVersion='14'),data={'state.json':canonical({'version':1,'allocations':{BINDING:dict(body,state='released')}})})
        current,ref=self.document({},2,[self.ref]);current['metadata']['uid']='77777777-7777-4777-8777-777777777777';ref['uid']=current['metadata']['uid']
        maps={item['metadata']['name']:item for item in (self.cm,current,cm,completion,ledger)}
        kube=SimpleNamespace(configmap=lambda ns,name:copy.deepcopy(maps.get(name)),pod=lambda intent:None)
        consumer=self.mod.ApprovalConsumer(base,self.config,self.template,ref,kube.configmap)
        journal=SimpleNamespace(read=lambda uid:record if uid==POD else None)
        return consumer,cm,store,journal,kube,maps,body

    def test_revoked_revision_retains_cleanup_but_cannot_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            consumer,cm,store,journal,kube,maps,body=self.terminal_values(Path(tmp))
            with self.assertRaises(ValueError):consumer.validate_enrollment(cm,self.models)
            envelopes,terminal=consumer.validate_enrollments([cm],self.models,store,journal,kube)
            self.assertEqual(terminal,{POD});self.assertEqual(envelopes[0]['enrollment'],body)

    def test_revoked_custody_requires_original_mirror_reference_journal_ledger_and_absence(self):
        for fault in ('mirror','reference','journal','completion','ledger','pod','missing'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                consumer,cm,store,journal,kube,maps,body=self.terminal_values(Path(tmp))
                if fault=='mirror':(store.state/'enrollments'/(POD+'.json')).unlink()
                elif fault=='reference':(store.state/'approval-references'/(POD+'.json')).unlink()
                elif fault=='journal':journal.read=lambda uid:None
                elif fault=='completion':maps['cps-native-cleanup-'+BINDING[:40]]['metadata']['uid']=NODE
                elif fault=='ledger':
                    value=json.loads(maps['cps-native-gpu-allocations']['data']['state.json']);value['allocations'][BINDING]['state']='gated';maps['cps-native-gpu-allocations']['data']['state.json']=canonical(value)
                elif fault=='pod':kube.pod=lambda intent:dict(apiVersion='v1',kind='Pod',metadata={'uid':POD})
                with self.assertRaises(ValueError):consumer.validate_enrollments([] if fault=='missing' else [cm],self.models,store,journal,kube)

    def test_unreferenced_seed_new_start_cannot_bypass_revocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            consumer,cm,store,journal,kube,maps,body=self.terminal_values(Path(tmp),legacy=True)
            value=json.loads(maps['cps-native-gpu-allocations']['data']['state.json']);value['allocations'][BINDING]['state']='enrolled'
            maps['cps-native-gpu-allocations']['data']['state.json']=canonical(value)
            with self.assertRaises(ValueError):consumer.validate_enrollments([cm],self.models,store,journal,kube)

    def test_existing_released_seed_remains_terminal_without_invented_approval_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            consumer,cm,store,journal,kube,maps,body=self.terminal_values(Path(tmp),legacy=True)
            envelopes,terminal=consumer.validate_enrollments([cm],self.models,store,journal,kube)
            self.assertEqual(terminal,{POD});self.assertNotIn('approval_ref',envelopes[0]['enrollment'])

    def test_active_enrollment_requires_exact_actual_allocation(self):
        for fault in ('missing','intent','member','state'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                consumer,cm,store,journal,kube,maps,body=self.terminal_values(Path(tmp))
                consumer=self.consumer(maps)
                value=json.loads(maps['cps-native-gpu-allocations']['data']['state.json']);row=value['allocations'][BINDING];row['state']='enrolled'
                if fault=='missing':del value['allocations'][BINDING]
                elif fault=='intent':row['intent']['pod_uid']=NODE
                elif fault=='member':row['members']=['person:outsider']
                else:row['state']='unknown'
                maps['cps-native-gpu-allocations']['data']['state.json']=canonical(value)
                with self.assertRaises(ValueError):consumer.validate_enrollments([cm],self.models,store,journal,kube)

    def test_shared_history_contains_other_components_without_granting_node_authority(self):
        foreign=dict(self.ref,namespace='jupyterhub',uid='88888888-8888-4888-8888-888888888888')
        cm,ref=self.document({},2,[self.ref,foreign])
        consumer=self.mod.ApprovalConsumer(base,self.config,self.template,ref,lambda ns,name:cm)
        self.assertEqual(consumer.current()['history'],[self.ref,foreign])

    def test_prior_ref_pending_lifetime_cannot_open_a_gate_after_head_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,cm,store,journal,kube,maps,body=self.terminal_values(Path(tmp))
            current,ref=self.document({'cps:new':self.approval},2,[self.ref]);maps[current['metadata']['name']]=current
            consumer=self.mod.ApprovalConsumer(base,self.config,self.template,ref,kube.configmap)
            journal.read=lambda uid:None
            state=json.loads(maps['cps-native-gpu-allocations']['data']['state.json']);state['allocations'][BINDING]['state']='enrolled'
            maps['cps-native-gpu-allocations']['data']['state.json']=canonical(state)
            with self.assertRaises(ValueError):consumer.validate_enrollments([cm],self.models,store,journal,kube)

    def test_admitted_spec_hash_does_not_override_approved_images_or_storage(self):
        for fault in (None,'image','pvc','readonly','hostpath'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                consumer,cm,store,journal,kube,maps,body=self.terminal_values(Path(tmp));consumer=self.consumer(maps);consumer.models=self.models
                spec={'nodeName':self.pool['node'],'initContainers':[{'name':'cps-native-cap-gate','image':self.template['gateImage']}],
                    'containers':[{'name':'notebook','image':self.template['workloadImage'],'volumeMounts':[{'name':'group','mountPath':'/workspace'}]}],
                    'volumes':[{'name':'group','persistentVolumeClaim':{'claimName':self.approval['storage']['pvc']}}]}
                if fault=='image':spec['containers'][0]['image']='example/foreign@sha256:'+'0'*64
                elif fault=='pvc':spec['volumes'][0]['persistentVolumeClaim']['claimName']='foreign'
                elif fault=='readonly':
                    spec['volumes'].append({'name':'extra','nfs':{'server':'nas.local','path':'/other','readOnly':True}})
                    spec['containers'][0]['volumeMounts'].append({'name':'extra','mountPath':'/data','readOnly':True})
                elif fault=='hostpath':
                    spec['volumes'].append({'name':'host','hostPath':{'path':'/etc','type':'Directory'}})
                    spec['containers'][0]['volumeMounts'].append({'name':'host','mountPath':'/host','readOnly':True})
                body['intent']['spec_sha256']=hashlib.sha256(base.canonical_json(spec).encode()).hexdigest()
                cm['data']['enrollment.json']=canonical(body)
                state=json.loads(maps['cps-native-gpu-allocations']['data']['state.json']);state['allocations'][BINDING]=dict(body,state='enrolled')
                maps['cps-native-gpu-allocations']['data']['state.json']=canonical(state)
                envelope=consumer.validate_enrollment(cm,self.models)
                pod=dict(apiVersion='v1',kind='Pod',metadata={'namespace':body['namespace'],'name':body['name'],'uid':POD},spec=spec)
                if fault is None:consumer.validate_approved_pod(pod,envelope)
                else:
                    with self.assertRaises(ValueError):consumer.validate_approved_pod(pod,envelope)

    def test_failed_iteration_or_stale_process_never_acknowledges(self):
        consumer=self.consumer();consumer.current();process=dict(namespace='cps-native-authority',name='agent',uid=POD,container='node',
            image='example/node@sha256:'+'a'*64,service_account='agent')
        epoch=dict(node_uid=NODE,boot_id=self.pool['boot_id'],driver_generation=self.pool['driver_generation'],gpu_uuid=GPU)
        pod=dict(apiVersion='v1',kind='Pod',metadata={'namespace':process['namespace'],'name':process['name'],'uid':POD},
            spec={'nodeName':self.pool['node'],'serviceAccountName':'agent','containers':[{'name':'node','image':process['image']}]},
            status={'phase':'Running','conditions':[{'type':'Ready','status':'True'}],'containerStatuses':[{'name':'node','ready':True,'imageID':'docker-pullable://example/node@sha256:'+'a'*64}]})
        published=[]
        with self.assertRaises(ValueError):consumer.acknowledge(process,pod,epoch,False,published.append)
        self.assertFalse(published);ack=consumer.acknowledge(process,pod,epoch,True,published.append)
        self.assertEqual(ack['document'],self.ref);self.assertEqual(len(published),1)
        pod['metadata']['uid']=NODE
        with self.assertRaises(ValueError):consumer.acknowledge(process,pod,epoch,True,lambda _:self.fail('stale process ack'))

class CurrentAgentReplayTest(unittest.TestCase):
    """Private CPU replay; never manufactures hardware or API receipts."""
    def capture(self):
        raw=os.environ.get('CPS_NATIVE_APPROVAL_CAPTURE')
        if not raw:self.skipTest('Explicit safe current38/41 capture required')
        return Path(raw)

    def source(self):
        return (self.capture()/'profile20-restart-safe-source-v1/actual-node-agent-3bae.py').read_text()

    def test_adapter_default_is_inert_and_only_changes_run_and_main(self):
        import ast
        from contextlib import redirect_stdout
        from io import StringIO
        from types import ModuleType
        import native_approval_revision as module
        source=self.source();derived=module.render_current_agent(source,Path(module.__file__).read_bytes())
        before={n.name:ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        after={n.name:ast.get_source_segment(derived,n) for n in ast.parse(derived).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        self.assertEqual(set(before),set(after));self.assertEqual({k for k in before if before[k]!=after[k]},{'run','main'})
        current=ModuleType('_current_native_approval_inert');current.__file__=str(Path(module.__file__).parent/'node_agent.py')
        import sys
        sys.modules[current.__name__]=current
        exec(compile(derived,current.__file__,'exec'),current.__dict__)
        current.load_bundle=lambda _:self.fail('Default-inert invocation must not load drivers/clients')
        output=StringIO()
        with redirect_stdout(output):current.main([])
        self.assertEqual(json.loads(output.getvalue())['state'],'inert')
        self.assertFalse(json.loads(output.getvalue())['gpu_calls'])
        with self.assertRaises(ValueError):module.render_current_agent(source+'\n',Path(module.__file__).read_bytes())
        with self.assertRaises(ValueError):module.render_current_agent(source,Path(module.__file__).read_bytes()+b'\n')

    def test_actual_full38_archive41_released_preserves36_runtime_and_denies_custody_changes(self):
        import ast
        from types import FunctionType
        import current_group_historical_source as historical
        import terminal_policy_proposal as terminal
        import native_approval_revision as module
        root=self.capture();source=self.source();derived=module.render_current_agent(source,Path(module.__file__).read_bytes())
        reviewed,_=historical.validation_context(source)
        namespace=dict(vars(reviewed))
        for node in ast.parse(derived).body:
            if isinstance(node,ast.FunctionDef) and node.name in ('validate_config','validate_configuration_reference','validate_historical_configuration','validate_enrollment'):
                exec(compile(ast.get_source_segment(derived,node),'<actual-derived-pure-validator>','exec'),namespace)
        reviewed=SimpleNamespace(**namespace)
        mapper=FunctionType(terminal.map_history.__code__,dict(terminal.map_history.__globals__,agent=reviewed))
        capture=json.loads((root/'profile20-restart-stop-witness-v1/inverse-captures-with-measured-physical.json').read_text())
        ledger=json.loads((root/'profile20-restart-restored-terminal-capture-v1/ledger.json').read_text())
        maps=json.loads((root/'profile20-restart-restored-terminal-capture-v1/maps.json').read_text())
        selected=next(c for c in maps['items'] if c['metadata']['name']=='cps-native-node-qualification-c2ae3af20952ef1f')
        config=json.loads(selected['data']['config.json']);before=copy.deepcopy(config)
        authority=copy.deepcopy(capture['current']['authority']);authority['authority_maps']=maps
        history=mapper(authority,ledger,config)
        self.assertEqual(len(history),38);self.assertEqual(len(config['terminal_history']),36)
        self.assertEqual(len(json.loads(ledger['data']['state.json'])['allocations']),41);self.assertEqual(config,before)
        for fault in ('ledger','completion','journal','history'):
            with self.subTest(fault=fault):
                a=copy.deepcopy(authority);l=copy.deepcopy(ledger);c=copy.deepcopy(config)
                if fault=='ledger':
                    state=json.loads(l['data']['state.json']);next(iter(state['allocations'].values()))['state']='enrolled';l['data']['state.json']=canonical(state)
                elif fault=='completion':
                    cm=next(cm for cm in a['authority_maps']['items'] if cm['metadata']['name'].startswith('cps-native-cleanup-'))
                    cm['metadata']['uid']='11111111-1111-4111-8111-111111111111'
                elif fault=='journal':a['host_snapshot']['directories']['journal']=[]
                else:next(iter(c['terminal_history'].values()))['enrollment_uid']='11111111-1111-4111-8111-111111111111'
                with self.assertRaises(ValueError):mapper(a,l,c)

    def test_real_generated_loop_keeps_revoked_lifetime_terminal_and_writes_postflight_ack(self):
        import ast
        from contextlib import nullcontext,redirect_stdout,ExitStack
        from io import StringIO
        from unittest.mock import patch
        import native_approval_revision as module
        fixture=ApprovalNodeTest();fixture.setUp()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);consumer,cm,store,journal,kube,maps,body=fixture.terminal_values(root)
            journal.locked=lambda:nullcontext();journal.records=lambda:[journal.read(POD)]
            kube.node=lambda _:dict(metadata={'name':fixture.pool['node'],'uid':NODE})
            kube.enrollments=lambda _:[cm]
            kube.delete=lambda _:self.fail('No terminal Pod deletion')
            process=dict(namespace=consumer.reference['namespace'],container='node',image='example/node@sha256:'+'a'*64,service_account='agent')
            process_pod=dict(apiVersion='v1',kind='Pod',metadata={'namespace':process['namespace'],'name':'agent','uid':NODE},
                spec={'nodeName':fixture.pool['node'],'serviceAccountName':'agent','containers':[{'name':'node','image':process['image']}]},
                status={'phase':'Running','conditions':[{'type':'Ready','status':'True'}],
                    'containerStatuses':[{'name':'node','ready':True,'imageID':process['image']}]})
            kube.call=lambda method,path:copy.deepcopy(process_pod)
            epoch=fixture.models.DriverEpoch(NODE,fixture.pool['boot_id'],fixture.pool['driver_generation'],GPU)
            namespace=dict(vars(base),EnrollmentStore=lambda *a:store,abort_current_epoch=lambda *a:epoch,ExitStack=ExitStack)
            derived=module.render_current_agent(self.source(),Path(module.__file__).read_bytes())
            run=next(n for n in ast.parse(derived).body if isinstance(n,ast.FunctionDef) and n.name=='run')
            exec(compile(ast.get_source_segment(derived,run),'<actual-generated-loop>','exec'),namespace)
            runtime_agent=SimpleNamespace(**vars(base));runtime_agent.abort_current_epoch=lambda *a:epoch
            runtime=module.NodeApprovalRuntime(runtime_agent,root/'reference.json',root/'template.json',root/'process.json',root)
            runtime.begin=lambda *a:consumer;runtime.consumer=consumer
            actual_backend_intents=[]
            def backend(*a,**kwargs):
                actual_backend_intents.extend(kwargs['intents']);return SimpleNamespace(seal_gate=lambda *a:self.fail('No retired gate'))
            class Controller:
                def __init__(self,*a,**kwargs):pass
                def reconcile(self,*a):raise AssertionError('Terminal lifetime cannot be reconciled')
                def cleanup(self,*a):raise AssertionError('Terminal lifetime cannot manufacture cleanup')
            qualification=SimpleNamespace(cri_reader=lambda *a:None,gpu_clients=lambda _:(),health=lambda *a,**k:self.fail('No hardware'))
            bundle=(SimpleNamespace(QualificationNodeBackend=backend),qualification,
                {'models':fixture.models,'manual':None,'health':None,'cdi':None})
            def private(path,**kwargs):
                if Path(path).name=='process.json':return copy.deepcopy(process)
                if Path(path).name=='approval.json':return copy.deepcopy(consumer.loaded)
                raise AssertionError('Unexpected filesystem read')
            with patch.object(fixture.models,'PrivateJournal',return_value=journal),patch.object(fixture.models,'NativeCapController',Controller), \
                patch.object(module,'read_private',side_effect=private),patch.dict(os.environ,{'CPS_NATIVE_APPROVAL_POD_UID':NODE,
                    'CPS_NATIVE_APPROVAL_POD_NAME':'agent','CPS_NATIVE_APPROVAL_POD_NAMESPACE':process['namespace']}),redirect_stdout(StringIO()):
                namespace['run'](fixture.config,bundle,root,kube,None,iterations=1,interval=0,crictl='unused',cri_socket='unused',approval=runtime)
            self.assertEqual(actual_backend_intents,[])
            ack=store.backend.private_read(root/'approval-loaded.json',store.uid)
            self.assertEqual(ack['revision'],consumer.reference['revision']);self.assertEqual(ack['process']['uid'],NODE)
            self.assertEqual(stat_mode(root/'approval-loaded.json'),0o600)


def stat_mode(path):
    import stat
    return stat.S_IMODE(Path(path).stat().st_mode)


if __name__=='__main__':unittest.main()
