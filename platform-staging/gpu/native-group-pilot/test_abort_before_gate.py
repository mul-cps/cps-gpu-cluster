"""CPU-only root abort protocol tests; no Kubernetes/NVML/device calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('reviewed_abort', HERE / 'abort_before_gate.py')
abort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abort)

def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
def sha(value): return 'sha256:' + hashlib.sha256(canonical(value).encode()).hexdigest()

def fixtures():
    intent = {'namespace':'jupyterhub','name':'jupyter-owner--rtc',
        'pod_uid':'11111111-1111-4111-8111-111111111111', 'node':'k3s-wk-gpu2',
        'node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41', 'spec_sha256':'b'*64,
        'gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56', 'cap_mib':5120,
        'policy_hash':'sha256:'+'c'*64}
    record = {'version':1,'binding_id':'a'*60,'source':'cps','actor':'cps','workspace':'native-group-b',
        'principal':'workspace:cps:native-group-b','members':['p1','p2'],'attempt':'attempt-1',
        'profile':'native5','policy_hash':intent['policy_hash'],'namespace':intent['namespace'],
        'name':intent['name'],'node':intent['node'],'node_uid':intent['node_uid'],
        'gpu_uuid':intent['gpu_uuid'],'cap_mib':5120,'intent':intent,'state':'releasing'}
    enrollment = {k:v for k,v in record.items() if k != 'state'}
    ledger = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'cps-native-gpu-allocations',
        'namespace':'cps-native-system','uid':'22222222-2222-4222-8222-222222222222','resourceVersion':'10'},
        'data':{'state.json':canonical({'version':1,'allocations':{record['binding_id']:record}})}}
    cm = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'cps-native-enrollment-'+record['binding_id'][:40],
        'namespace':'cps-native-system','uid':'44444444-4444-4444-8444-444444444444',
        'labels':{'cps.compute/native-binding':record['binding_id']}},'immutable':True,
        'data':{'enrollment.json':canonical(enrollment)}}
    proof = {'node_epoch':{'node_uid':intent['node_uid'],
        'boot_id':'55555555-5555-4555-8555-555555555555',
        'driver_generation':'66666666-6666-4666-8666-666666666666','gpu_uuid':intent['gpu_uuid']},
        'journal_device':25,'journal_inode':123,'journal_protected':True,'journal_empty':True,
        'gate_receipts_absent':True,'native_writers_quiesced':True,'exclusive_lock':True,
        'driver_healthy':True,'global_gpu_memory_mib':0,'global_gpu_clients':0,
        'global_compute_apps':0,'pod_runtime_tasks':0}
    evidence = {'version':1,'qualification_only':True,'authority_namespace':'cps-native-system',
        'binding_id':record['binding_id'],'attempt':record['attempt'],'ledger_uid':ledger['metadata']['uid'],
        'allocation_sha256':sha({k:v for k,v in record.items() if k not in ('state','pre_gate_abort')}),
        'enrollment_uid':cm['metadata']['uid'],'enrollment_sha256':sha(enrollment),
        'fence_command_sha256':sha(['root-reviewed-fence']), 'proof':proof,
        'review':{'operator':'root','reason':'node-agent-failed-before-native-transaction',
            'gate_only_pod_sha256':'sha256:'+'1'*64,'controller_source_sha256':'sha256:'+'2'*64,
            'node_agent_source_sha256':'sha256:'+'3'*64,'parser_failure_sha256':'sha256:'+'4'*64,
            'native_transaction_never_started':True}}
    return evidence, ledger, cm

class Fence:
    def __init__(self, backend): self.backend = backend
    def __enter__(self): self.backend.locked=True; return self
    def verify(self):
        self.backend.verifies += 1
        if self.backend.verify_change: self.backend.verify_change(self.backend)
        return copy.deepcopy(self.backend.proof)
    def __exit__(self,*args): self.backend.locked=False

class Backend:
    def __init__(self):
        self.evidence,self.ledger,self.enrollment=fixtures()
        self.proof=copy.deepcopy(self.evidence['proof']); self.locked=False
        self.abort_cm=None; self.pod=None; self.writes=[]; self.verifies=0
        self.verify_change=None; self.before_cas=None; self.fail_readback=False
    def fence(self,evidence): return Fence(self)
    def get_ledger(self): return copy.deepcopy(self.ledger)
    def get_enrollment(self,bid): return copy.deepcopy(self.enrollment)
    def get_node(self,name): return {'metadata':{'name':name,'uid':self.proof['node_epoch']['node_uid']}}
    def get_pod(self,namespace,name): return copy.deepcopy(self.pod)
    def get_abort(self,bid):
        if self.fail_readback: raise abort.AbortError('Readback unavailable')
        return copy.deepcopy(self.abort_cm)
    def create_abort(self,body):
        assert self.locked
        self.writes.append('create'); self.abort_cm=copy.deepcopy(body)
        self.abort_cm['metadata']['uid']='77777777-7777-4777-8777-777777777777'
        return copy.deepcopy(self.abort_cm)
    def compare_and_swap(self,snapshot,state):
        assert self.locked
        if self.before_cas: self.before_cas(self)
        if snapshot['metadata']['resourceVersion'] != self.ledger['metadata']['resourceVersion']:
            raise abort.AbortError('CAS conflict')
        self.writes.append('cas'); self.ledger['data']['state.json']=canonical(state)
        self.ledger['metadata']['resourceVersion']='11'; return copy.deepcopy(self.ledger)

class Tests(unittest.TestCase):
    def run_abort(self,b,evidence=None):
        e=evidence if evidence is not None else b.evidence
        return abort.execute_abort(b,e,expected_evidence_sha256=sha(e))
    def test_default_cli_is_inert_without_optional_inputs_or_api(self):
        result=subprocess.run([sys.executable,str(HERE/'abort_before_gate.py')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'state':'inert','api_calls':False,'device_calls':False})
    def test_approved_abort_preserves_intent_and_other_rows_and_records_real_cm_uid(self):
        b=Backend(); original=json.loads(b.ledger['data']['state.json'])['allocations']['a'*60]
        result=self.run_abort(b)
        saved=json.loads(b.ledger['data']['state.json'])['allocations']['a'*60]
        self.assertEqual(saved['state'],'released'); self.assertEqual(saved['intent'],original['intent'])
        self.assertEqual({k:v for k,v in saved.items() if k not in ('state','pre_gate_abort')},
                         {k:v for k,v in original.items() if k != 'state'})
        self.assertEqual(saved['pre_gate_abort'],{'configmap':'cps-native-abort-'+'a'*40,
            'configmap_uid':'77777777-7777-4777-8777-777777777777',
            'sha256':sha(json.loads(b.abort_cm['data']['abort.json']))})
        self.assertEqual(b.writes,['create','cas']); self.assertGreaterEqual(b.verifies,3)
        self.assertEqual(result['state'],'released'); self.assertFalse(b.locked)
    def test_incorrect_review_hash_never_opens_backend(self):
        b=Backend()
        with self.assertRaises(abort.AbortError): abort.execute_abort(b,b.evidence,expected_evidence_sha256='sha256:'+'0'*64)
        self.assertEqual(b.verifies,0); self.assertEqual(b.writes,[])
    def test_every_uncertain_proof_blocks_before_publication(self):
        for key in ('journal_protected','journal_empty','gate_receipts_absent','native_writers_quiesced','exclusive_lock','driver_healthy'):
            with self.subTest(key=key):
                b=Backend(); b.proof[key]=False
                with self.assertRaises(abort.AbortError): self.run_abort(b)
                self.assertEqual(b.writes,[])
        for key in ('global_gpu_memory_mib','global_gpu_clients','global_compute_apps','pod_runtime_tasks'):
            with self.subTest(key=key):
                b=Backend(); b.proof[key]=1
                with self.assertRaises(abort.AbortError): self.run_abort(b)
                self.assertEqual(b.writes,[])
    def test_changed_node_epoch_journal_identity_enrollment_or_live_pod_blocks(self):
        for change in ('epoch','journal','enrollment','pod','ledger_uid'):
            with self.subTest(change=change):
                b=Backend()
                if change=='epoch': b.proof['node_epoch']['driver_generation']='88888888-8888-4888-8888-888888888888'
                if change=='journal': b.proof['journal_inode']+=1
                if change=='enrollment': b.enrollment['metadata']['uid']='88888888-8888-4888-8888-888888888888'
                if change=='pod': b.pod={'metadata':{'uid':'foreign'}}
                if change=='ledger_uid': b.ledger['metadata']['uid']='88888888-8888-4888-8888-888888888888'
                with self.assertRaises(abort.AbortError): self.run_abort(b)
                self.assertEqual(b.writes,[])
    def test_readback_failure_leaves_allocation_held(self):
        b=Backend()
        def fail_after_create(body):
            result=Backend.create_abort(b,body); b.fail_readback=True; return result
        b.create_abort=fail_after_create
        with self.assertRaises(abort.AbortError): self.run_abort(b)
        self.assertEqual(b.writes,['create'])
        self.assertEqual(json.loads(b.ledger['data']['state.json'])['allocations']['a'*60]['state'],'releasing')
    def test_live_pod_appearing_after_publication_and_cas_race_preserve_hold(self):
        for race in ('pod','cas'):
            with self.subTest(race=race):
                b=Backend()
                if race=='pod':
                    def appear(backend):
                        if backend.verifies>=3: backend.pod={'metadata':{'uid':'replacement'}}
                    b.verify_change=appear
                else: b.before_cas=lambda backend:backend.ledger['metadata'].update(resourceVersion='newer')
                with self.assertRaises(abort.AbortError): self.run_abort(b)
                self.assertNotIn('cas',b.writes)
                self.assertEqual(json.loads(b.ledger['data']['state.json'])['allocations']['a'*60]['state'],'releasing')
    def test_retry_after_cas_conflict_and_completed_retry_are_idempotent(self):
        b=Backend(); b.before_cas=lambda backend:backend.ledger['metadata'].update(resourceVersion='newer')
        with self.assertRaises(abort.AbortError): self.run_abort(b)
        b.before_cas=None
        self.run_abort(b); self.run_abort(b)
        self.assertEqual(b.writes,['create','cas'])
    def test_forged_or_replaced_abort_map_is_rejected(self):
        b=Backend(); self.run_abort(b)
        b.abort_cm['metadata']['uid']='88888888-8888-4888-8888-888888888888'
        with self.assertRaises(abort.AbortError): self.run_abort(b)

class StrictAndTransportTests(unittest.TestCase):
    def test_closed_evidence_and_exact_integer_counts(self):
        for kind in ('extra', 'boolean_count', 'false_review', 'intent_change', 'wrong_members'):
            with self.subTest(kind=kind):
                b=Backend()
                if kind=='extra': b.evidence['override']=True
                if kind=='boolean_count': b.evidence['proof']['global_gpu_clients']=False; b.proof=copy.deepcopy(b.evidence['proof'])
                if kind=='false_review': b.evidence['review']['native_transaction_never_started']=False
                if kind in ('intent_change','wrong_members'):
                    state=json.loads(b.ledger['data']['state.json'])
                    if kind=='intent_change': state['allocations']['a'*60]['intent']['spec_sha256']='d'*64
                    else: state['allocations']['a'*60]['members']=['foreign']
                    b.ledger['data']['state.json']=canonical(state)
                with self.assertRaises(abort.AbortError): abort.execute_abort(b,b.evidence,expected_evidence_sha256=sha(b.evidence))
                self.assertEqual(b.writes,[])
    def test_other_rows_and_gateway_private_allocation_fields_preserved(self):
        b=Backend(); state=json.loads(b.ledger['data']['state.json'])
        state['allocations']['a'*60].update(ceiling={'cpu':4},group_id='original-group')
        state['allocations']['b'*60]={'state':'released','untouched':['old','proof']}
        b.evidence['allocation_sha256']=sha({k:v for k,v in state['allocations']['a'*60].items() if k!='state'})
        b.ledger['data']['state.json']=canonical(state)
        abort.execute_abort(b,b.evidence,expected_evidence_sha256=sha(b.evidence))
        saved=json.loads(b.ledger['data']['state.json'])
        self.assertEqual(saved['allocations']['b'*60],state['allocations']['b'*60])
        self.assertEqual(saved['allocations']['a'*60]['group_id'],'original-group')
    def test_duplicate_json_keys_and_extra_enrollment_data_rejected(self):
        with self.assertRaises(abort.AbortError): abort.parse('{"proof":1,"proof":2}')
        b=Backend(); b.enrollment['data']['extra']='forged'
        with self.assertRaises(abort.AbortError): abort.execute_abort(b,b.evidence,expected_evidence_sha256=sha(b.evidence))
        self.assertEqual(b.writes,[])
    def test_unavailable_actual_reads_and_deleting_authority_never_publish(self):
        for operation in ('get_ledger','get_enrollment','get_node','get_pod','deleting'):
            with self.subTest(operation=operation):
                b=Backend()
                if operation=='deleting': b.enrollment['metadata']['deletionTimestamp']='2026-10-09T00:00:00Z'
                else:
                    def unavailable(*args): raise abort.AbortError('API unavailable')
                    setattr(b,operation,unavailable)
                with self.assertRaises(abort.AbortError): abort.execute_abort(b,b.evidence,expected_evidence_sha256=sha(b.evidence))
                self.assertEqual(b.writes,[])
    def test_null_or_list_api_reply_is_not_pod_absence(self):
        backend=abort.KubernetesBackend(['root-reviewed-fence'])
        for body in ('null','[]'):
            with mock.patch.object(abort.subprocess,'run',return_value=subprocess.CompletedProcess([],0,body,'')):
                with self.assertRaises(abort.AbortError): backend.get_pod('jupyterhub','jupyter-owner--rtc')
        with mock.patch.object(abort.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
            self.assertIsNone(backend.get_pod('jupyterhub','jupyter-owner--rtc'))
    def test_root_rpc_holds_live_process_and_rechecks_fresh_proof(self):
        b=Backend()
        code="""import json,sys,datetime
proof=json.loads(sys.argv[1])
def emit(event):
 print(json.dumps({'event':event,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'proof':proof}),flush=True)
emit('fence-acquired')
for line in sys.stdin:
 op=json.loads(line)['op']
 if op=='release':break
 if op=='verify':emit('fence-verified')
"""
        command=[sys.executable,'-u','-c',code,canonical(b.proof)]
        b.evidence['fence_command_sha256']=sha(command)
        fence=abort.RootFence(command,b.evidence,timeout=2)
        with fence:
            self.assertIsNone(fence.process.poll())
            self.assertEqual(fence.verify(),b.proof)
            self.assertEqual(fence.verify(),b.proof)
        self.assertEqual(fence.process.returncode,0)
    def test_bad_pinned_command_never_launches(self):
        b=Backend()
        with mock.patch.object(abort.subprocess,'Popen') as launch:
            with self.assertRaises(abort.AbortError): abort.RootFence(['unreviewed-command'],b.evidence)
            launch.assert_not_called()
    def test_stale_or_missing_rpc_proof_rejects_and_closes(self):
        b=Backend()
        for stale in (True,False):
            code="import json,sys,time; "+("print(json.dumps({'event':'fence-acquired','observed_at':'2020-01-01T00:00:00Z','proof':json.loads(sys.argv[1])}),flush=True); " if stale else '')+"time.sleep(.2)"
            command=[sys.executable,'-u','-c',code,canonical(b.proof)]
            b.evidence['fence_command_sha256']=sha(command)
            fence=abort.RootFence(command,b.evidence,timeout=.5)
            with self.assertRaises(abort.AbortError):
                with fence: pass
            self.assertIsNotNone(fence.process.returncode)
    def test_execute_without_evidence_remains_inert(self):
        result=subprocess.run([sys.executable,str(HERE/'abort_before_gate.py'),'--execute'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn('evidence/hash/output required',result.stderr)
    def test_offline_proposal_contains_api_body_but_not_manufactured_uid(self):
        b=Backend()
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            for name,value in [('evidence',b.evidence),('ledger',b.ledger),('enrollment',b.enrollment)]:
                (p/name).write_text(canonical(value))
            with mock.patch.object(abort.subprocess,'Popen') as launch, mock.patch.object(abort.subprocess,'run') as api:
                with mock.patch('sys.stdout'):
                    abort.main(['--propose','--qualification-only','--evidence',str(p/'evidence'),'--evidence-sha256',sha(b.evidence),'--ledger',str(p/'ledger'),'--enrollment',str(p/'enrollment'),'--output',str(p/'proposal')])
                launch.assert_not_called(); api.assert_not_called()
            result=json.loads((p/'proposal').read_text())
            self.assertNotIn('uid',result['abort_configmap']['metadata'])
            self.assertEqual(result['ledger_cas']['pre_gate_abort']['configmap_uid'],'<ACTUAL_ABORT_CONFIGMAP_UID_FROM_CREATE_READBACK>')
            self.assertEqual((p/'proposal').stat().st_mode & 0o777,0o600)
    def test_kubectl_cas_tests_actual_uid_and_rv_and_hides_patch_from_argv(self):
        b=Backend(); backend=abort.KubernetesBackend(['root-reviewed-fence'])
        state=json.loads(b.ledger['data']['state.json'])
        def call(argv,**kwargs):
            path=Path(argv[argv.index('--patch-file')+1])
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            patch=json.loads(path.read_text())
            self.assertEqual(patch[:2],[{'op':'test','path':'/metadata/uid','value':b.ledger['metadata']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':'10'}])
            self.assertEqual(patch[2]['value'],canonical(state))
            return subprocess.CompletedProcess(argv,0,canonical(b.ledger),'')
        with mock.patch.object(abort.subprocess,'run',side_effect=call):
            self.assertEqual(backend.compare_and_swap(b.ledger,state),b.ledger)

if __name__=='__main__': unittest.main()
