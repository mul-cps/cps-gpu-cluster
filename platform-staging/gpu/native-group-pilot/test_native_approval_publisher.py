"""Offline own-SA acknowledgment CAS; no real API or GPU calls."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import native_approval_revision as n


TARGET={'namespace':'cps-native-system','name':'cps-native-approval-ack-test',
        'uid':'44444444-4444-4444-8444-444444444444'}


def candidate():
    return {'version':1,'component':'node','revision':'sha256:'+'a'*64,'policy_hash':'sha256:'+'b'*64,
        'document':{'namespace':TARGET['namespace'],'name':'approved-test','uid':'55555555-5555-4555-8555-555555555555',
            'data_sha256':'sha256:'+'c'*64,'revision':'sha256:'+'a'*64,'policy_hash':'sha256:'+'b'*64},
        'process':{'namespace':TARGET['namespace'],'name':'node-pod','uid':'66666666-6666-4666-8666-666666666666',
            'container':'node','image':'example/node@sha256:'+'d'*64,'service_account':'node'},
        'driver_epoch':{'node_uid':'77777777-7777-4777-8777-777777777777','boot_id':'88888888-8888-4888-8888-888888888888',
            'driver_generation':'generation-1','gpu_uuid':'GPU-99999999-9999-4999-8999-999999999999'},
        'observed_at':'2026-10-13T07:00:00+00:00'}


class FakeKube:
    def __init__(self):
        self.cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{**TARGET,'resourceVersion':'17',
            'labels':{'preserved':'value'},'annotations':{'preserved':'also'}},'data':{'ack.json':'{}'}}
        self.gets=[];self.patches=[];self.before_patch=lambda:None;self.response=lambda cm:cm

    def call(self,method,path,value=None):
        if method!='GET':raise AssertionError('No generic create/update/list transport')
        self.gets.append(path);return copy.deepcopy(self.cm)

    def apply(self,path,operations):
        self.patches.append((path,copy.deepcopy(operations)));self.before_patch()
        fields={'/metadata/uid':self.cm['metadata']['uid'],
            '/metadata/resourceVersion':self.cm['metadata']['resourceVersion'],'/data':self.cm['data']}
        for op in operations[:3]:
            if op['op']!='test' or fields[op['path']]!=op['value']:raise ValueError('CAS conflict')
        self.cm['data']=copy.deepcopy(operations[-1]['value']);self.cm['metadata']['resourceVersion']='18'
        return self.response(copy.deepcopy(self.cm))


class PublisherTests(unittest.TestCase):
    def publish(self,kube,value=None,verify=None):
        value=value or candidate()
        return n.publish_existing_acknowledgment(kube,TARGET,value,verify or (lambda:copy.deepcopy(value)),patch=kube.apply)

    def test_exact_existing_uid_rv_full_data_cas_preserves_other_fields(self):
        kube=FakeKube();before=copy.deepcopy(kube.cm);value=candidate();checks=[]
        result=self.publish(kube,value,lambda:checks.append(True) or copy.deepcopy(value))
        self.assertEqual(kube.patches[0][1],[
            {'op':'test','path':'/metadata/uid','value':TARGET['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':'17'},
            {'op':'test','path':'/data','value':{'ack.json':'{}'}},
            {'op':'replace','path':'/data','value':{'ack.json':n.canonical(value)}}])
        before['data']=result['data'];before['metadata']['resourceVersion']='18'
        self.assertEqual(result,before);self.assertGreaterEqual(len(checks),2)
        self.assertTrue(all(path=='/api/v1/namespaces/cps-native-system/configmaps/cps-native-approval-ack-test' for path in kube.gets))

    def test_missing_replaced_foreign_or_extra_data_never_patches(self):
        for mutation in ('missing','uid','name','namespace','owner','immutable','binary','deleting','extra','noncanonical','foreign'):
            with self.subTest(mutation=mutation):
                kube=FakeKube()
                if mutation=='missing':kube.cm=None
                elif mutation in ('uid','name','namespace'):kube.cm['metadata'][mutation]='foreign'
                elif mutation=='owner':kube.cm['metadata']['ownerReferences']=[{'uid':TARGET['uid']}]
                elif mutation=='immutable':kube.cm['immutable']=True
                elif mutation=='binary':kube.cm['binaryData']={'bad':'eA=='}
                elif mutation=='deleting':kube.cm['metadata']['deletionTimestamp']='now'
                elif mutation=='extra':kube.cm['data']['bad']='extra'
                elif mutation=='noncanonical':kube.cm['data']['ack.json']='{ }'
                else:
                    value=candidate();value['component']='gateway';kube.cm['data']['ack.json']=n.canonical(value)
                with self.assertRaises(ValueError):self.publish(kube)
                self.assertEqual(kube.patches,[])

    def test_fresh_proof_change_conflict_and_bad_patch_response_fail_closed(self):
        kube=FakeKube();calls=[]
        def drift():
            calls.append(True);value=candidate()
            if len(calls)>1:value['process']['uid']=TARGET['uid']
            return value
        with self.assertRaises(ValueError):self.publish(kube,verify=drift)
        self.assertEqual(kube.patches,[])
        for field in ('uid','resourceVersion','data'):
            kube=FakeKube()
            def change(field=field):
                if field=='data':kube.cm['data']['ack.json']=n.canonical(candidate())
                else:kube.cm['metadata'][field]='changed'
            kube.before_patch=change
            with self.assertRaises(ValueError):self.publish(kube)
            self.assertEqual(len(kube.patches),1)
        for field in ('uid','data'):
            kube=FakeKube()
            def invalid(cm,field=field):
                if field=='data':cm['data']={'ack.json':'{}'}
                else:cm['metadata'][field]='changed'
                return cm
            kube.response=invalid
            with self.assertRaises(ValueError):self.publish(kube)

    def test_server_managed_fields_may_change_but_annotations_may_not(self):
        kube=FakeKube();kube.cm['metadata']['managedFields']=[{'manager':'operator','fieldsType':'FieldsV1'}]
        def server(cm):
            cm['metadata']['managedFields'].append({'manager':'node-agent','fieldsType':'FieldsV1'})
            kube.cm=copy.deepcopy(cm);return cm
        kube.response=server
        self.publish(kube)
        kube=FakeKube()
        def foreign(cm):cm['metadata']['annotations']['preserved']='changed';return cm
        kube.response=foreign
        with self.assertRaises(ValueError):self.publish(kube)

    def test_patch_http_content_type_timeout_and_body_bound(self):
        requests=[]
        class Opener:
            def open(self,request,timeout):
                requests.append((request,timeout));return io.BytesIO(n.canonical(FakeKube().cm).encode())
        kube=SimpleNamespace(base='https://kubernetes.default.svc',token='private-test-token',opener=Opener())
        n.patch_acknowledgment(kube,'/api/v1/namespaces/cps-native-system/configmaps/cps-native-approval-ack-test',[])
        request,timeout=requests[0]
        self.assertEqual(request.method,'PATCH');self.assertEqual(timeout,5)
        self.assertEqual(request.get_header('Content-type'),'application/json-patch+json')
        self.assertEqual(json.loads(request.data),[])
        kube.opener=SimpleNamespace(open=lambda *a,**k:io.BytesIO(b' '*1048577))
        with self.assertRaises(ValueError):n.patch_acknowledgment(kube,'/api/v1/namespaces/cps-native-system/configmaps/cps-native-approval-ack-test',[])

    def test_observer_overlay_changes_only_import_adapter_and_is_pinned(self):
        import cps_compute.native_group_process as source
        raw=Path(source.__file__).read_bytes()
        derived=n.render_process_observer(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),n.PROCESS_SOURCE_SHA256)
        self.assertNotIn('from .',derived);namespace={};exec(derived,namespace)
        self.assertTrue(callable(namespace['observe_process']))
        with self.assertRaises(ValueError):n.render_process_observer(raw+b'\n')


class RendererPublisherIntegration(unittest.TestCase):
    def setup_projection(self):
        folder=os.environ.get('CPS_NATIVE_APPROVAL_RENDERER')
        if not folder:self.skipTest('Explicit renderer source fixture required')
        import sys
        sys.path.insert(0,folder)
        import native_group_approval_renderer as renderer
        from test_native_group_approval_renderer import fixture,request,actual_documents,readiness_fixture,uid
        from cps_compute.native_gpu_controller import DriverEpoch
        f=fixture();plan=renderer.document_intent(**request(f));documents=actual_documents(plan)
        projection=renderer.projection_intent(documents=documents,**request(f))
        pool=f[1]._config()['node_pool'];epoch=DriverEpoch(pool['node_uid'],pool['boot_id'],pool['driver_generation'],pool['gpu_uuid'])
        acks={component:{'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':cm['metadata']['namespace'],
            'name':'cps-native-approval-ack-'+component.replace(':','-'),'uid':uid(100+index),'resourceVersion':'4'},
            'data':{'ack.json':'{}'}} for index,(component,cm) in enumerate(documents.items())}
        projection=renderer.publisher_intent(projection=projection,documents=documents,baselines=f[-1],
            acknowledgments=acks,policy=f[0],qualification=f[1],driver_epoch=epoch,ttl_seconds=30)
        ready=readiness_fixture(f,projection,documents)
        for component in ready['pods']:
            pod=ready['pods'][component];rs=ready['replicasets'][component]
            pod['metadata']['labels']=copy.deepcopy(rs['spec']['template']['metadata']['labels'])
            for item in (pod,rs):
                for owner in item['metadata']['ownerReferences']:owner['apiVersion']='apps/v1'
        return f,documents,projection,acks,ready

    def test_renderer_to_real_node_finish_and_existing_ack_cas(self):
        from cps_compute.native_group_revision import ApprovalRevision,validate_ack
        import cps_compute.native_group_process as source
        import node_agent as base
        from test_node_agent import EnrollmentTest
        f,documents,projection,ack_maps,ready=self.setup_projection();pool=f[1]._config()['node_pool']
        config=dict(version=2,enabled=True,mode='qualified-group',authority_namespace=f[1].authority_namespace,
            policy_hash=f[0].hash,pool=pool,workspaces={scope:{'profile':row['profiles'][0],
                'cap_mib':row['ceiling']['gpuMemoryGiB']*1024} for scope,row in f[1].workspaces.items()})
        fixture=EnrollmentTest();fixture.setUp();models=fixture.models
        doc=documents['node'];ref=projection['references']['node']
        consumer=n.ApprovalConsumer(base,config,f[1]._config(),ref,lambda ns,name:copy.deepcopy(doc))
        consumer.current();observer=SimpleNamespace();exec(n.render_process_observer(Path(source.__file__).read_bytes()),observer.__dict__)
        data=projection['bootstrap_maps']['node']['data'];declaration=json.loads(data['process.json'])
        target=json.loads(data['acknowledgment.json']);self.assertEqual(set(declaration),{'namespace','kind','name','uid','container','image','service_account'})
        self.assertEqual(target,{key:ack_maps['node']['metadata'][key] for key in ('namespace','name','uid')})
        actual={('/api/v1/namespaces/'+ref['namespace']+'/configmaps/'+ref['name']):doc}
        for component in ready['pods']:
            pod=ready['pods'][component];rs=ready['replicasets'][component];deploy=ready['deployments'][component]
            ns=pod['metadata']['namespace']
            actual['/api/v1/namespaces/'+ns+'/pods/'+pod['metadata']['name']]=pod
            actual['/apis/apps/v1/namespaces/'+ns+'/replicasets/'+rs['metadata']['name']]=rs
            actual['/apis/apps/v1/namespaces/'+ns+'/deployments/'+deploy['metadata']['name']]=deploy
        ack_path='/api/v1/namespaces/'+target['namespace']+'/configmaps/'+target['name'];actual[ack_path]=copy.deepcopy(ack_maps['node'])
        actual['/api/v1/namespaces/'+ref['namespace']+'/configmaps/cps-native-gpu-allocations']={
            'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':ref['namespace'],'name':'cps-native-gpu-allocations',
                'uid':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','resourceVersion':'3'},
            'data':{'state.json':n.canonical({'version':1,'allocations':{}})}}
        writes=[]
        class Opener:
            def open(self,req,timeout):
                self_timeout=timeout;self_ops=json.loads(req.data);self_path=req.full_url.removeprefix('https://test')
                self_current=actual[self_path]
                fields={'/metadata/uid':self_current['metadata']['uid'],'/metadata/resourceVersion':self_current['metadata']['resourceVersion'],
                    '/data':self_current['data']}
                for op in self_ops[:3]:
                    if fields[op['path']]!=op['value']:raise ValueError('CAS conflict')
                self_current['data']=copy.deepcopy(self_ops[3]['value']);self_current['metadata']['resourceVersion']='5'
                writes.append((req,self_timeout));return io.BytesIO(n.canonical(self_current).encode())
        kube=SimpleNamespace(base='https://test',token='test-only',opener=Opener(),enrollments=lambda ns:[],
            call=lambda method,path:copy.deepcopy(actual.get(path)),
            configmap=lambda ns,name:copy.deepcopy(actual.get('/api/v1/namespaces/'+ns+'/configmaps/'+name)),
            pod=lambda _:None,delete=lambda _:self.fail('No Pod deletion in offline fixture'))
        epoch=ready['driver_epoch'];agent=SimpleNamespace(**vars(base));agent.abort_current_epoch=lambda *a:epoch
        journal=SimpleNamespace(records=lambda:[])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=base.EnrollmentStore(root,models,trusted_uid=os.getuid())
            runtime=n.NodeApprovalRuntime(agent,root/'reference.json',root/'template.json',root/'process.json',root,
                acknowledgment_path=root/'acknowledgment.json',process_observer=observer)
            runtime.consumer=consumer
            def private(path,**kwargs):
                key=Path(path).name
                if key=='approval.json':return copy.deepcopy(consumer.loaded)
                return json.loads(data[key])
            process=ready['expected_processes']['node']
            with patch.object(n,'read_private',side_effect=private),patch.dict(os.environ,{
                'CPS_NATIVE_APPROVAL_POD_UID':process['uid'],'CPS_NATIVE_APPROVAL_POD_NAME':process['name'],
                'CPS_NATIVE_APPROVAL_POD_NAMESPACE':process['namespace']}):
                ack=runtime.finish(config,models,store,journal,kube,{},None,None,True)
                self.assertEqual(len(writes),1);self.assertEqual(json.loads(actual[ack_path]['data']['ack.json']),ack)
                self.assertEqual(writes[0][0].get_header('Content-type'),'application/json-patch+json')
                loaded=ApprovalRevision.from_configmap(doc,f[0],f[1],expected_ref=ref)
                self.assertEqual(validate_ack(ack,component='node',document=loaded,actual_pod=ready['pods']['node'],
                    expected_process=process,driver_epoch=epoch,now=n.datetime.now(n.timezone.utc)),ack)
                writes.clear()
                capture=os.environ.get('CPS_NATIVE_APPROVAL_CAPTURE')
                if capture:
                    import ast
                    from contextlib import nullcontext,redirect_stdout,ExitStack
                    source_path=Path(capture)/'profile20-restart-safe-source-v1/actual-node-agent-3bae.py'
                    derived=n.render_current_agent(source_path.read_text(),Path(n.__file__).read_bytes())
                    self.assertIn("parser.add_argument('--approval-acknowledgment'",derived)
                    self.assertIn(n.PROCESS_OVERLAY_SHA256,derived)
                    journal.locked=lambda:nullcontext()
                    kube.node=lambda name:{'metadata':{'name':pool['node'],'uid':pool['node_uid']}}
                    runtime.begin=lambda *a:consumer
                    namespace=dict(vars(base),EnrollmentStore=lambda *a:store,abort_current_epoch=lambda *a:epoch,ExitStack=ExitStack)
                    run=next(row for row in ast.parse(derived).body if isinstance(row,ast.FunctionDef) and row.name=='run')
                    exec(compile(ast.get_source_segment(derived,run),'<actual-derived-node-loop>','exec'),namespace)
                    def backend(*a,**kwargs):
                        self.assertEqual(kwargs['intents'],[])
                        return SimpleNamespace(seal_gate=lambda *a:self.fail('No gate work in empty fixture'))
                    class Controller:
                        def __init__(self,*a,**k):pass
                        def reconcile(self,*a):raise AssertionError('No GPU reconciliation in offline fixture')
                    bundle=(SimpleNamespace(QualificationNodeBackend=backend),
                        SimpleNamespace(cri_reader=lambda *a:None,gpu_clients=lambda _:(),health=lambda *a,**k:self.fail('No hardware')),
                        {'models':models,'manual':None,'health':None,'cdi':None})
                    with patch.object(models,'PrivateJournal',return_value=journal),patch.object(models,'NativeCapController',Controller),redirect_stdout(io.StringIO()):
                        namespace['run'](config,bundle,root,kube,None,iterations=1,interval=0,crictl='unused',cri_socket='unused',approval=runtime)
                    self.assertEqual(len(writes),1);writes.clear()
                    ack=store.backend.private_read(root/'approval-loaded.json',store.uid)
                journal.records=lambda:[SimpleNamespace(intent=SimpleNamespace(pod_uid=TARGET['uid'],to_dict=lambda:{}))]
                with self.assertRaises(ValueError):runtime.publish(kube,config,models,store,journal,{},None,None,declaration,ack)
                self.assertFalse(writes);journal.records=lambda:[]
                agent.abort_current_epoch=lambda *a:models.DriverEpoch(epoch.node_uid,'11111111-1111-4111-8111-111111111111',
                    epoch.driver_generation,epoch.gpu_uuid)
                with self.assertRaises(ValueError):runtime.publish(kube,config,models,store,journal,{},None,None,declaration,ack)
                self.assertFalse(writes);agent.abort_current_epoch=lambda *a:epoch
                changed=copy.deepcopy(ack);changed['process']['uid']=TARGET['uid']
                store.backend.private_write(root/'approval-loaded.json',changed,store.uid,create=False)
                with self.assertRaises(ValueError):runtime.publish(kube,config,models,store,journal,{},None,None,declaration,ack)
                self.assertFalse(writes);store.backend.private_write(root/'approval-loaded.json',ack,store.uid,create=False)
                with self.assertRaises(ValueError):runtime.finish(config,models,store,journal,kube,{},None,None,False)
                self.assertFalse(writes)
                actual['/api/v1/namespaces/'+process['namespace']+'/pods/'+process['name']]['spec']['containers'][0]['args'].append('--foreign')
                with self.assertRaises(ValueError):runtime.finish(config,models,store,journal,kube,{},None,None,True)
                self.assertFalse(writes)


if __name__=='__main__':unittest.main()
