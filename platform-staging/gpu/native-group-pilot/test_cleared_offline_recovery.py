"""CPU integration of explicit recovery; host/API observations are test doubles."""
import importlib
import base64
from email.message import Message
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import uuid
import urllib.request
import urllib.response
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO, BytesIO
import unittest
from unittest.mock import patch
from test_node_agent import fixtures, NODE, GPU


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.r = importlib.import_module('cleared_offline_recovery')
        self.a = importlib.import_module('node_agent')
        self.m = self.a.load_models_from_snapshot()
        self.uid = os.geteuid()

    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        state = Path(temporary.name); state.chmod(0o700)
        config,e,cm = fixtures()
        config.update(version=2, mode='operator-qualification',
            workspaces={'cps:pilot':{'profile':'interactive-native-qualification-5','cap_mib':5120}})
        config['pool'].update(total_memory_mib=40960,free_memory_mib=32768,headroom_mib=1024,
            memory_budget_mib=15360,boot_id=self.r.BOOT,driver_generation=self.r.GENERATION)
        e.update(binding_id=self.r.BINDING,attempt=self.r.ATTEMPT,profile='interactive-native-qualification-5')
        e['intent'].update(pod_uid=self.r.POD)
        cm['metadata']['name'] = 'cps-native-enrollment-'+self.r.BINDING[:40]
        cm['metadata']['labels'][self.a.LABEL] = self.r.BINDING
        cm['data']['enrollment.json'] = self.a.canonical_json(e)
        envelope = self.a.validate_enrollment(cm,config,self.m)
        intent = self.m.CapIntent(**e['intent'])
        relative = '/kubepods.slice/kubepods-burstable-pod'+self.r.POD.replace('-','_')+'.slice'
        identity = self.m.CapIdentity(self.r.POD,intent.spec_sha256,NODE,GPU,'c'*64,
            211,345,self.r.BOOT,relative,'/sys/fs/cgroup'+relative,29,1390814,self.r.GENERATION)
        original = self.m.CapRecord(intent,identity,'cleanup-prepared',self.r.SEAL,
            self.m.CapLimit(5368709120,5368709120))
        journal = self.m.PrivateJournal(state/'journal'); journal.write(original)
        records = [original]
        for index in range(1,17):
            pid = str(uuid.UUID(int=index+100))
            i = replace(intent,pod_uid=pid,name='peer-'+str(index))
            peer_relative='/kubepods.slice/kubepods-burstable-pod'+pid.replace('-','_')+'.slice'
            ident = replace(identity,pod_uid=pid,host_pid=index+211,cgroup_inode=1390814+index,
                cgroup_relative=peer_relative,cgroup_path='/sys/fs/cgroup'+peer_relative,
                boot_id=self.r.BOOT if index<12 else '11111111-1111-4111-8111-111111111111')
            record = self.m.CapRecord(i,ident,'cleaned',self.r.SEAL,original.readback)
            journal.write(record); records.append(record)
        inventory = {'version':1,'backend':'misc-fallback','gpu_uuid':GPU,'gpu_id':0,'entries':[]}
        for index in range(12):
            inode=1390814+index
            inventory['entries'].append(dict(cgroup_id=inode,kernfs_id=inode,inode=inode,
                offline=True,pinned=True,default_hierarchy=True,soft=0 if index==0 else 5368709120,
                hard=self.m.MAX_LIMIT if index==0 else 5368709120,used=0))
        for index in range(1,12):
            peer=records[index]
            records[index]=replace(peer,state='retired-inert-cap',
                retirement=self.m.validate_retired_inventory(inventory,peer.identity,peer.limit))
            journal.write(records[index])
        ledger = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':config['authority_namespace'],
            'name':'cps-native-gpu-allocations','uid':'77777777-7777-4777-8777-777777777777','resourceVersion':'23'},
            'data':{'state.json':self.a.canonical_json({'version':1,'allocations':{
                **{str(index).zfill(60):{'state':'released'} for index in range(22)},
                self.r.BINDING:{**e,'state':'releasing','ceiling':5120}}})}}
        writers = {name:{'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':'cps-compute',
            'name':name,'uid':str(uuid.UUID(int=900+index)),'generation':3},
            'spec':{'replicas':0,'selector':{'matchLabels':{'app':name}}},'status':{'observedGeneration':3}}
            for index,name in enumerate(self.r.WRITERS)}
        plan = {'version':1,'protocol':'cleared-offline-recovery-plan/v1',
            'operation_id':'e98f0a7e-f2f5-47b5-bd0f-50ef51930163',
            'node_config_sha256':self.a.canonical_sha256(config),'original':original.to_dict(),
            'original_raw_sha256':self.r.digest(journal.path(self.r.POD).read_bytes()),
            'inventory':inventory,'enrollment':cm,'ledger':ledger,
            'journal_sha256s':{v.intent.pod_uid:self.a.canonical_sha256(v.to_dict()) for v in records},
            'physical_pods':[v.intent.pod_uid for v in records[:12]],'writers':writers}
        now = datetime.now(timezone.utc)
        review = {'version':1,'operation_id':plan['operation_id'],'plan_sha256':self.a.canonical_sha256(plan),
            'issued_at':(now-timedelta(seconds=5)).isoformat().replace('+00:00','Z'),
            'expires_at':(now+timedelta(minutes=5)).isoformat().replace('+00:00','Z'),
            'approved':True,'exclusive_operator_custody':True,'no_alternate_writer_or_release':True,
            'normal_stop_passed':False,'production_qualified':False,
            'credential':{'namespace':config['authority_namespace'],'service_account':'cps-native-cleared-offline-recovery',
                'service_account_uid':'99999999-9999-4999-8999-999999999999','pod_name':'recovery-token-custody',
                'pod_uid':'88888888-8888-4888-8888-888888888888',
                'pod_spec_sha256':self.a.canonical_sha256({'serviceAccountName':'cps-native-cleared-offline-recovery'}),
                'api_server':'https://10.43.0.1:443','audience':'https://kubernetes.default.svc.cluster.local',
                'token_sha256':'sha256:'+'a'*64,'ca_sha256':'sha256:'+'b'*64}}
        proof = self.r.make_proof(self.a,self.m,plan,review)
        store = self.a.EnrollmentStore(state,self.m,trusted_uid=self.uid)
        store.synchronize([envelope])
        (state/'operator').mkdir(mode=0o700)
        for path in (state/'authority/.driver-loader.lock',state/'operator/.teardown.lock'):
            path.write_bytes(b''); path.chmod(0o600)
        (state/'authority/driver-generation').write_text(self.r.GENERATION); (state/'authority/driver-generation').chmod(0o600)
        op = self.r.operation_directory(state,proof.operation_id,self.a,self.uid,create=True)
        for name,value in [('plan.json',plan),('review.json',review)]:
            self.r.preserve(op/name,self.a.canonical_json(value).encode(),self.uid)
        proc = state/'proc'; (proc/'sys/kernel/random').mkdir(parents=True)
        (proc/'sys/kernel/random/boot_id').write_text(self.r.BOOT)
        maps = {cm['metadata']['name']:copy.deepcopy(cm),'cps-native-gpu-allocations':copy.deepcopy(ledger)}
        outer=self
        class Kube:
            def __init__(self): self.created=[]; self.writer_drift=None; self.pagination=False; self.fail_cleanup=False
            def call(self,method,path,value=None):
                outer.assertEqual(method,'GET')
                cred=review['credential']
                if '/serviceaccounts/' in path:
                    return {'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':cred['namespace'],
                        'name':cred['service_account'],'uid':cred['service_account_uid']}}
                if '/pods/recovery-token-custody' in path:
                    return {'apiVersion':'v1','kind':'Pod','metadata':{'namespace':cred['namespace'],
                        'name':cred['pod_name'],'uid':cred['pod_uid']},
                        'spec':{'serviceAccountName':cred['service_account']}}
                if '/deployments/' in path:
                    d=copy.deepcopy(writers[path.rsplit('/',1)[1]])
                    if self.writer_drift: self.writer_drift(d)
                    return d
                return {'apiVersion':'v1','kind':'PodList','metadata':{'resourceVersion':'31',
                    'continue':'page' if self.pagination else ''},'items':[]}
            def configmap(self,ns,name): return copy.deepcopy(maps.get(name))
            def pod(self,intent): return None
            def node(self,name): return {'metadata':{'name':name,'uid':NODE}}
            def delete(self,*args): outer.fail('No Pod deletion authorized')
            def create_configmap(self,ns,value):
                if self.fail_cleanup and value['metadata']['name'].startswith('cps-native-cleanup-'):
                    raise ValueError('synthetic publication failure')
                if value['metadata']['name'] in maps: raise outer.a.Conflict()
                outer.assertEqual(journal.read(outer.r.POD).state,outer.r.RECOVERED)
                outer.assertEqual(journal.read_recovery_original(proof),
                    (outer.a.canonical_json(original.to_dict())+'\n').encode())
                for p in (state/'journal/.writer.lock',state/'authority/.driver-loader.lock',state/'operator/.teardown.lock'):
                    fd=os.open(p,os.O_RDWR)
                    try:
                        with outer.assertRaises(BlockingIOError): fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    finally: os.close(fd)
                value=copy.deepcopy(value); value['metadata'].update(uid=str(uuid.uuid4()),resourceVersion='42')
                maps[value['metadata']['name']]=value; self.created.append(value)
                return copy.deepcopy(value)
        kube=Kube()
        base=store.backend
        class Host(self.r.backend_class(base)):
            def _group(self,identity,*,absent=False): return None
            def _retired_mount(self,identity): outer.assertEqual(identity.cgroup_device,29)
            def _inventory(self,identity):
                self.inventory_reads += 1
                result=copy.deepcopy(self.document)
                if self.mutate_inventory: self.mutate_inventory(self,result)
                return result
            def read_gate(self,identity): return self.gate
            def set_limit(self,*args): outer.fail('Recovery must never write native caps')
            def revoke_gate(self,*args): outer.fail('Recovery must never mutate gate')
            def seal_gate(self,*args): outer.fail('Recovery must never reseal')
        backend=Host(self.m,SimpleNamespace(),intents=[v.intent for v in records],driver=SimpleNamespace(version='615.0'),
            get_pod=kube.pod,get_node=kube.node,get_cri=lambda *args:None,delete_pod=kube.delete,
            gpu_clients=lambda gpu:(),health=lambda:True,proc_root=proc,state_root=state,trusted_uid=self.uid)
        backend.configure_recovery(self.a,kube,journal,store,plan,review,proof,config)
        backend.gate=None; backend.document=copy.deepcopy(inventory); backend.inventory_reads=0; backend.mutate_inventory=None
        return SimpleNamespace(state=state,config=config,envelope=envelope,journal=journal,original=original,
            records=records,inventory=inventory,plan=plan,review=review,proof=proof,store=store,kube=kube,maps=maps,backend=backend,
            controller=self.m.NativeCapController(backend,journal,enabled=True))

    def recover(self,f):
        with patch.object(self.a,'load_recovery_module',return_value=self.r):
            return f.controller.recover_cleared_offline(f.original.intent,f.proof,operator_approved=True)

    def test_default_inert_has_no_source_file_host_or_api_reads(self):
        with patch.object(self.r, 'protected', side_effect=AssertionError('read')), redirect_stdout(StringIO()) as output:
            self.r.main([])
        self.assertEqual(json.loads(output.getvalue()), {'state':'inert', 'api_calls':False,
            'gpu_calls':False, 'normal_stop_passed':False, 'production_qualified':False})

    def test_node_loads_exact_pinned_helper_and_frozen_model(self):
        loaded=self.a.load_recovery_module()
        self.assertEqual(loaded.RECOVERED,self.r.RECOVERED)
        self.assertEqual(self.a.RECOVERY_SOURCE_PIN,hashlib.sha256(Path(self.r.__file__).read_bytes()).hexdigest())
        self.assertEqual(self.a.SOURCE_PINS['native_gpu_controller.py'],
            '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880')

    def test_genuine_sdk_recovers_then_publishes_under_all_three_locks(self):
        f=self.fixture(); before=f.journal.path(self.r.POD).read_bytes()
        result=self.recover(f)
        self.assertEqual(result.state,self.r.RECOVERED)
        self.assertEqual(f.journal.read_recovery_original(f.proof),before)
        self.assertEqual(len(f.journal.records()),17)
        self.assertEqual([v['metadata']['name'].split('-')[2] for v in f.kube.created],['recovery','cleanup'])
        self.assertGreaterEqual(f.backend.inventory_reads,6)
        audit=f.maps['cps-native-recovery-'+self.r.BINDING[:40]]
        cleanup=f.maps['cps-native-cleanup-'+self.r.BINDING[:40]]
        with patch.object(self.a,'load_recovery_module',return_value=self.r):
            self.assertTrue(f.store.cleanup_published(self.r.POD,f.envelope,result,cleanup,audit=audit))
            receipt=self.a.parse(cleanup['data']['receipt.json'])
        self.assertEqual(set(receipt['recovery']),{'proof','enrollment_uid','enrollment_sha256','journal_sha256','audit_uid','audit_sha256'})

    def test_normal_finite_retirement_stays_strict(self):
        f=self.fixture()
        with self.assertRaises(self.m.ControllerError):
            self.m.validate_retired_inventory(f.inventory,f.original.identity,f.original.limit)

    def test_full_map_late_drift_leaves_original_journal_and_no_receipts(self):
        for field,value in [('used',1),('soft',64),('inode',999)]:
            with self.subTest(field=field):
                f=self.fixture(); raw=f.journal.path(self.r.POD).read_bytes()
                def mutation(b,d):
                    if b.inventory_reads>=3: d['entries'][-1][field]=value
                f.backend.mutate_inventory=mutation
                with self.assertRaises(ValueError): self.recover(f)
                self.assertEqual(f.journal.path(self.r.POD).read_bytes(),raw)
                self.assertEqual(f.journal.read_recovery_original(f.proof),raw)
                self.assertEqual(f.kube.created,[])

    def test_exact_bound_token_claims_and_no_admin_or_expired_substitution(self):
        f=self.fixture(); c=copy.deepcopy(f.review['credential'])
        now=int(datetime.now(timezone.utc).timestamp())
        payload={'sub':'system:serviceaccount:'+c['namespace']+':'+c['service_account'],'aud':[c['audience']],
            'iat':now-10,'nbf':now-10,'exp':now+600,'kubernetes.io':{'namespace':c['namespace'],
                'serviceaccount':{'name':c['service_account'],'uid':c['service_account_uid']},
                'pod':{'name':c['pod_name'],'uid':c['pod_uid']}}}
        def encode(value): return base64.urlsafe_b64encode(self.a.canonical_json(value).encode()).rstrip(b'=')
        def raw_for(p): return b'.'.join((encode({'alg':'RS256'}),encode(p),b'CPU-signature'))
        raw=raw_for(payload); c['token_sha256']=self.r.digest(raw)
        self.assertEqual(self.r.token_claims(self.a,raw,c,f.review),raw.decode())
        for kind in ('admin','foreign-pod','foreign-sa','expired','unbound','audience'):
            p=copy.deepcopy(payload)
            if kind=='admin': p['sub']='system:admin'
            if kind=='foreign-pod': p['kubernetes.io']['pod']['uid']=str(uuid.uuid4())
            if kind=='foreign-sa': p['kubernetes.io']['serviceaccount']['uid']=str(uuid.uuid4())
            if kind=='expired': p['exp']=now-1
            if kind=='unbound': p['kubernetes.io'].pop('pod')
            if kind=='audience': p['aud']=['foreign']
            changed=raw_for(p); c['token_sha256']=self.r.digest(changed)
            with self.subTest(kind=kind),self.assertRaises(ValueError): self.r.token_claims(self.a,changed,c,f.review)

    def test_live_credential_sa_and_pod_drift_denied(self):
        for kind in ('sa','pod','spec'):
            f=self.fixture(); original_call=f.kube.call
            def call(method,path,value=None):
                actual=original_call(method,path,value)
                if kind=='sa' and actual.get('kind')=='ServiceAccount': actual['metadata']['uid']=str(uuid.uuid4())
                if kind=='pod' and actual.get('kind')=='Pod': actual['metadata']['uid']=str(uuid.uuid4())
                if kind=='spec' and actual.get('kind')=='Pod': actual['spec']['serviceAccountName']='default'
                return actual
            f.kube.call=call
            with self.subTest(kind=kind),self.assertRaises(ValueError): self.recover(f)
            self.assertEqual(f.journal.read(self.r.POD),f.original); self.assertEqual(f.kube.created,[])

    def test_genuine_api_authentication_cannot_accept_decoded_unverified_admin(self):
        f=self.fixture(); raw=b'CPU-token'; ca=b'CPU-CA'; cred=copy.deepcopy(f.review['credential'])
        cred['ca_sha256']=self.r.digest(ca)
        expected='system:serviceaccount:'+cred['namespace']+':'+cred['service_account']
        class API:
            def call(self,method,path,value=None):
                return {'apiVersion':'authentication.k8s.io/v1','kind':'SelfSubjectReview',
                    'status':{'userInfo':{'username':expected if self.accept else 'system:admin',
                        'groups':['system:authenticated','system:serviceaccounts','system:serviceaccounts:'+cred['namespace']]}}}
        for accepted in (True,False):
            API.accept=accepted
            with patch.object(self.r,'protected',side_effect=[raw,ca]), \
                 patch.object(self.r,'token_claims',return_value='CPU-token'), \
                 patch.object(self.a,'api_class',return_value=API), \
                 patch.object(self.r.ssl,'create_default_context',return_value=object()), \
                 patch.object(self.r.urllib.request,'HTTPSHandler',return_value=object()), \
                 patch.object(self.r.urllib.request,'build_opener',return_value=object()), \
                 patch.object(self.r,'credential_fence') as fence:
                if accepted:
                    api=self.r.authority_api(self.a,object(),Path('/unused'),cred,f.review)
                    self.assertEqual(api.base,cred['api_server']); fence.assert_called_once()
                else:
                    with self.assertRaises(ValueError): self.r.authority_api(self.a,object(),Path('/unused'),cred,f.review)
                    fence.assert_not_called()

    def test_real_urllib_redirect_never_sends_bearer_to_second_endpoint(self):
        requests=[]
        class Transport(urllib.request.BaseHandler):
            handler_order=100
            def https_open(self,request):
                requests.append(request)
                headers=Message(); headers['Location']='https://foreign.example/steal'
                response=urllib.response.addinfourl(BytesIO(b''),headers,request.full_url,302)
                response.msg='Found'; return response
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Transport(),self.r.NoRedirect())
        request=urllib.request.Request('https://10.43.0.1:443/read',headers={'Authorization':'Bearer CPU-only'})
        with self.assertRaisesRegex(ValueError,'redirects refused'): opener.open(request,timeout=1)
        self.assertEqual(len(requests),1); self.assertEqual(requests[0].full_url,'https://10.43.0.1:443/read')

    def test_rehashed_initial_map_cannot_clear_or_change_a_finite_peer(self):
        for kind in ('unlimited','changed-finite'):
            f=self.fixture(); row=f.plan['inventory']['entries'][-1]
            row.update(soft=0 if kind=='unlimited' else 64,hard=self.m.MAX_LIMIT if kind=='unlimited' else 64)
            f.review['plan_sha256']=self.a.canonical_sha256(f.plan)
            f.proof=self.r.make_proof(self.a,self.m,f.plan,f.review)
            f.backend.proof=f.proof; f.backend.document=copy.deepcopy(f.plan['inventory'])
            with self.subTest(kind=kind),self.assertRaises(self.m.ControllerError): self.recover(f)
            self.assertEqual(f.journal.read(self.r.POD),f.original); self.assertEqual(f.kube.created,[])

    def test_original_pid_lifetime_rejected_reused_pid_allowed(self):
        for same in (True,False):
            f=self.fixture(); identity=f.original.identity
            p=f.backend.proc/str(identity.host_pid); p.mkdir()
            tail=['S']+['0']*18+[str(identity.pid_start_ticks if same else identity.pid_start_ticks+1)]
            (p/'stat').write_text(str(identity.host_pid)+' (name with spaces) '+' '.join(tail))
            if same:
                with self.assertRaisesRegex(ValueError,'PID lifetime'): self.recover(f)
            else: self.assertEqual(self.recover(f).state,self.r.RECOVERED)

    def test_gate_pod_group_gpu_epoch_fail_closed(self):
        for kind in ('gate','pod','group','clients','epoch'):
            with self.subTest(kind=kind):
                f=self.fixture(); raw=f.journal.path(self.r.POD).read_bytes()
                if kind=='gate': f.backend.gate={'unexpected':'gate'}
                if kind=='pod': f.backend.get_pod=lambda i:{'metadata':{'uid':i.pod_uid}}
                if kind=='group': f.backend._group=lambda *a,**k: object()
                if kind=='clients': f.backend.gpu_clients=lambda gpu:[{'pid':123}]
                if kind=='epoch': (f.state/'authority/driver-generation').write_text(str(uuid.uuid4()))
                with self.assertRaises((ValueError,self.m.ControllerError)): self.recover(f)
                self.assertEqual(f.journal.path(self.r.POD).read_bytes(),raw); self.assertEqual(f.kube.created,[])

    def test_writer_generation_pagination_and_ledger_rv_rejected(self):
        for kind in ('generation','replicas','pagination','ledger'):
            with self.subTest(kind=kind):
                f=self.fixture()
                if kind=='generation': f.kube.writer_drift=lambda d:d['status'].update(observedGeneration=2)
                if kind=='replicas': f.kube.writer_drift=lambda d:d['status'].update(readyReplicas=1)
                if kind=='pagination': f.kube.pagination=True
                if kind=='ledger': f.maps['cps-native-gpu-allocations']['metadata']['resourceVersion']='24'
                with self.assertRaises(ValueError): self.recover(f)
                self.assertEqual(f.journal.read(self.r.POD),f.original); self.assertEqual(f.kube.created,[])

    def test_historical_five_preserved_and_late_peer_body_change_denied(self):
        f=self.fixture(); old=f.records[-1]
        changed=replace(old,seal_id=str(uuid.uuid4())); f.journal.write(changed)
        with self.assertRaisesRegex(ValueError,'peer journal'): self.recover(f)
        self.assertEqual(f.journal.read(self.r.POD),f.original)

    def test_partial_publication_exact_operation_resume_and_no_false_tombstone(self):
        f=self.fixture(); f.kube.fail_cleanup=True
        with self.assertRaisesRegex(ValueError,'publication failure'): self.recover(f)
        terminal=f.journal.read(self.r.POD)
        self.assertEqual(terminal.state,self.r.RECOVERED)
        self.assertFalse((f.state/'published-cleanup'/ (self.r.POD+'.json')).exists())
        self.assertEqual(len(f.kube.created),1)
        f.kube.fail_cleanup=False
        self.assertEqual(self.recover(f),terminal)
        self.assertEqual(len(f.kube.created),2)
        self.assertEqual(f.journal.read_recovery_original(f.proof),
            (self.a.canonical_json(f.original.to_dict())+'\n').encode())

    def test_durable_recognition_does_not_reprove_future_physical_map(self):
        f=self.fixture(); terminal=self.recover(f)
        f.backend.document['entries'].append({'new':'future-life'})
        audit=f.maps['cps-native-recovery-'+self.r.BINDING[:40]]
        cleanup=f.maps['cps-native-cleanup-'+self.r.BINDING[:40]]
        with patch.object(self.a,'load_recovery_module',return_value=self.r):
            self.assertTrue(f.store.cleanup_published(self.r.POD,f.envelope,terminal,cleanup,audit=audit))
            for kind in ('missing-audit','foreign-audit','changed-cleanup','owner-audit','owner-cleanup','archive'):
                a,c=copy.deepcopy(audit),copy.deepcopy(cleanup)
                if kind=='missing-audit': a=None
                if kind=='foreign-audit': a['metadata']['uid']=str(uuid.uuid4())
                if kind=='changed-cleanup': c['data']['receipt.json']='{}'
                if kind=='owner-audit': a['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
                if kind=='owner-cleanup': c['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
                if kind=='archive': f.journal.recovery_original_path(f.proof).write_bytes(b'changed')
                with self.subTest(kind=kind),self.assertRaises((ValueError,self.m.ControllerError)):
                    f.store.cleanup_published(self.r.POD,f.envelope,terminal,c,audit=a)

    def test_lock_contention_and_replaced_path_denied(self):
        f=self.fixture(); p=f.state/'authority/.driver-loader.lock'
        fd=os.open(p,os.O_RDWR); self.addCleanup(os.close,fd); fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with self.assertRaises(self.m.ControllerError): self.recover(f)
        self.assertEqual(f.journal.read(self.r.POD),f.original)

    def test_replaced_lock_inode_fails_before_terminal(self):
        f=self.fixture(); target=f.state/'operator/.teardown.lock'
        def mutation(backend,document):
            if backend.inventory_reads==2:
                target.unlink(); target.write_bytes(b''); target.chmod(0o600)
        f.backend.mutate_inventory=mutation
        with self.assertRaises(ValueError): self.recover(f)
        self.assertEqual(f.journal.read(self.r.POD),f.original); self.assertEqual(f.kube.created,[])

    def test_actual_enrollment_metadata_change_rejected_before_terminal(self):
        for kind in ('namespace','name','label','mutable'):
            f=self.fixture(); cm=f.maps[f.envelope['configmap_name']]
            if kind=='namespace': cm['metadata']['namespace']='foreign'
            if kind=='name': cm['metadata']['name']='foreign'
            if kind=='label': cm['metadata']['labels'][self.a.LABEL]='f'*60
            if kind=='mutable': cm['immutable']=False
            with self.subTest(kind=kind),self.assertRaises(ValueError): self.recover(f)
            self.assertEqual(f.journal.read(self.r.POD),f.original)

    def test_rehashed_selected_ledger_identity_change_denied(self):
        for field in ('principal','profile','actor','members'):
            f=self.fixture(); plan=copy.deepcopy(f.plan)
            state=self.a.parse(plan['ledger']['data']['state.json'])
            state['allocations'][self.r.BINDING][field]=['foreign'] if field=='members' else 'foreign'
            plan['ledger']['data']['state.json']=self.a.canonical_json(state)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'exact original releasing'):
                self.r.validate_plan(self.a,self.m,plan,f.config)
            self.assertEqual(f.journal.read(self.r.POD),f.original); self.assertEqual(f.kube.created,[])

    def test_changed_review_operation_cannot_resume_terminal(self):
        f=self.fixture(); self.recover(f)
        changed=replace(f.proof,operation_id=str(uuid.uuid4()))
        with self.assertRaises((self.m.ControllerError,ValueError)):
            f.controller.recover_cleared_offline(f.original.intent,changed,operator_approved=True)

    def test_unpublished_distinct_terminal_is_never_normal_cleanup_or_auto_published(self):
        f=self.fixture(); f.kube.fail_cleanup=True
        with self.assertRaises(ValueError): self.recover(f)
        f.kube.fail_cleanup=False
        self.run_node(f,expected='retained-explicit-recovery-publication-required')
        self.assertEqual(len(f.kube.created),1)

    def test_published_distinct_terminal_is_recognized_by_genuine_node_poll(self):
        f=self.fixture(); self.recover(f)
        self.run_node(f,expected='cleanup-confirmed')
        self.assertEqual(len(f.kube.created),2)

    def run_node(self,f,expected):
        # Real run/store/proof/tombstone branch; only unrelated host/API plumbing
        # and enumeration of other already-terminal records are bounded doubles.
        forbidden=lambda *a,**kw:self.fail('Distinct recovery cannot call normal cleanup or gate path')
        host=SimpleNamespace(seal_gate=forbidden)
        qualification=SimpleNamespace(cri_reader=lambda *a:None,gpu_clients=forbidden,health=forbidden)
        adapter=SimpleNamespace(QualificationNodeBackend=lambda *a,**kw:host)
        bundle=(adapter,qualification,{'models':self.m,'manual':object(),'health':object(),'cdi':object()})
        f.kube.enrollments=lambda ns:[f.plan['enrollment']]
        terminal=f.journal.read(self.r.POD)
        store_class=self.a.EnrollmentStore
        with patch.object(self.a,'load_recovery_module',return_value=self.r), \
             patch.object(self.a,'EnrollmentStore',lambda state,models:store_class(state,models,trusted_uid=self.uid)), \
             patch.object(self.m.PrivateJournal,'records',lambda j:(j.read(self.r.POD),)), \
             patch.object(self.m.NativeCapController,'cleanup',forbidden), \
             patch.object(self.a,'abort_current_epoch',return_value=terminal.identity.epoch), \
             redirect_stdout(StringIO()) as output:
            self.a.run(f.config,bundle,f.state,f.kube,object(),iterations=1,interval=0,
                crictl=Path('/unused'),cri_socket='unused')
        row=json.loads(output.getvalue()); self.assertEqual(row['state'],expected)

    def test_complete_physical_subset_required_and_historical_five_cannot_be_dropped(self):
        f=self.fixture()
        for mutation in (lambda p:p['journal_sha256s'].pop(f.records[-1].intent.pod_uid),
                         lambda p:p['physical_pods'].__setitem__(-1,f.records[-1].intent.pod_uid),
                         lambda p:p['physical_pods'].append(f.records[-1].intent.pod_uid)):
            plan=copy.deepcopy(f.plan); mutation(plan)
            if len(plan['physical_pods'])==12 and len(plan['journal_sha256s'])==17:
                # A foreign-epoch substitution is detected by fresh physical/map fence.
                f.backend.plan=plan
                with self.assertRaises((ValueError,self.m.ControllerError)): self.recover(f)
                f.backend.plan=f.plan
            else:
                with self.assertRaises(ValueError): self.r.validate_plan(self.a,self.m,plan,f.config)

    def test_no_approved_review_or_expired_review_can_execute(self):
        f=self.fixture()
        for key in ('approved','exclusive_operator_custody','no_alternate_writer_or_release'):
            review=copy.deepcopy(f.review); review[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError): self.r.validate_review(self.a,review,f.plan)
        with self.assertRaises(ValueError):
            self.r.validate_review(self.a,f.review,f.plan,now=datetime.now(timezone.utc)+timedelta(hours=1))

    def test_cli_failure_reports_only_error_type_no_private_input(self):
        with patch.object(self.r,'_main',side_effect=ValueError('CPU-secret-never-output')), \
             redirect_stderr(StringIO()) as output,self.assertRaises(SystemExit): self.r.main(['--execute'])
        self.assertNotIn('CPU-secret',output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error_type'],'ValueError')

    def test_offline_capture_assembly_preserves_all_journals_and_physical_subset(self):
        f=self.fixture()
        host={'bootId':self.r.BOOT,'driverGeneration':self.r.GENERATION,'healthPassed':True,
            'directories':{'journal':{'ownerUid':0,'mode':0o700,'records':{
                r.intent.pod_uid+'.json':{'uid':0,'mode':0o600,'nlink':1,'value':r.to_dict(),
                    'rawSha256':self.r.digest((self.a.canonical_json(r.to_dict())+'\n').encode())} for r in f.records}}}}
        plan=self.r.plan_from_captures(self.a,self.m,f.config,host,f.inventory,f.plan['enrollment'],
            f.plan['ledger'],f.plan['writers'],f.plan['operation_id'])
        self.assertEqual(plan['journal_sha256s'],f.plan['journal_sha256s'])
        self.assertEqual(set(plan['physical_pods']),set(f.plan['physical_pods']))
        self.assertEqual(plan['original_raw_sha256'],f.plan['original_raw_sha256'])

    def test_protected_fifo_symlink_writable_and_hardlink_denied(self):
        f=self.fixture(); root=f.state; raw=b'private'
        regular=root/'regular'; regular.write_bytes(raw); regular.chmod(0o600)
        self.assertEqual(self.r.protected(regular,self.uid),raw)
        link=root/'link'; link.symlink_to(regular)
        fifo=root/'fifo'; os.mkfifo(fifo,0o600)
        for p in (link,fifo):
            with self.subTest(path=p.name),self.assertRaises((OSError,ValueError)): self.r.protected(p,self.uid)
        regular.chmod(0o666)
        with self.assertRaises(ValueError): self.r.protected(regular,self.uid)
        regular.chmod(0o600); os.link(regular,root/'hard')
        with self.assertRaises(ValueError): self.r.protected(regular,self.uid)


if __name__ == '__main__': unittest.main()
