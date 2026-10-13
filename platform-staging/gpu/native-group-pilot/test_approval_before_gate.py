"""Offline actual-schema counterexamples; no Kubernetes/NVML/device access."""
import base64
import copy
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

import abort_before_gate as old
import native_approval_revision as approval
import node_agent as agent
import test_native_approval_revision as fixtures

HERE = Path(__file__).parent
TARGET = 'e9780ea8-400f-4c1b-9c3e-df20f2f91b42'


def fixture():
    f = fixtures.ApprovalNodeTest(); f.setUp()
    f.config['authority_namespace'] = old.NAMESPACE
    f.template['authorityNamespace'] = old.NAMESPACE
    row = copy.deepcopy(f.approval); row['principal'] = 'workspace:cps:native-group-b'
    f.cm, f.ref = f.document({'cps:native-group-b': row})
    f.cm['metadata']['namespace'] = old.NAMESPACE
    f.ref['namespace'] = old.NAMESPACE
    body = copy.deepcopy(f.fixture.enrollment)
    body.update(workspace='native-group-b', principal=row['principal'], profile='interactive-shared-5',
        name=row['pod'], members=sorted(row['members']), approval_ref=f.ref)
    body['intent'].update(name=row['pod'], pod_uid=TARGET)
    record = dict(body, ceiling=row['ceiling'], group_id=row['group_id'])
    identity = {k:v for k,v in record.items() if k not in ('version','binding_id','intent')}
    record['binding_id'] = hashlib.sha256(old.canonical(identity).encode()).hexdigest()[:60]
    body['binding_id'] = record['binding_id']; record['state'] = 'enrolling'
    enrollment = copy.deepcopy(f.fixture.cm)
    enrollment['metadata'].update(namespace=old.NAMESPACE,
        name='cps-native-enrollment-'+body['binding_id'][:40],
        labels={old.LABEL:body['binding_id']})
    enrollment['data']['enrollment.json'] = approval.canonical(body)
    ledger = dict(apiVersion='v1',kind='ConfigMap',metadata=dict(namespace=old.NAMESPACE,
        name=old.LEDGER,uid='33ab24b0-8e9a-4bee-b308-12a19c076924',resourceVersion='14'),
        data={'state.json':old.canonical({'version':1,'allocations':{
            body['binding_id']:record,'b'*60:{'state':'released','preserved':'old immutable custody'}}})})
    raw = (old.canonical(f.record.to_dict())+'\n').encode()
    journals = [{'pod_uid':f.record.intent.pod_uid,'raw_base64':base64.b64encode(raw).decode(),
        'raw_sha256':'sha256:'+hashlib.sha256(raw).hexdigest()}]
    physical = [asdict(f.record.retirement.entry)]
    proof = dict(node_epoch=asdict(f.record.identity.epoch),journal_device=29,journal_inode=123,
        journal_protected=True,target_journal_absent=True,gate_receipts_absent=True,
        native_writers_quiesced=True,exclusive_lock=True,driver_healthy=True,approval_current=True,
        approval_ref=f.ref,retired_history_sha256=old.sha256(journals),physical_rows_sha256=old.sha256(physical),
        global_gpu_memory_mib=0,global_gpu_clients=0,global_compute_apps=0,pod_runtime_tasks=0)
    normalized = copy.deepcopy(json.loads(ledger['data']['state.json']))
    normalized['allocations'][body['binding_id']].pop('state')
    evidence = dict(version=2,qualification_only=True,authority_namespace=old.NAMESPACE,
        binding_id=body['binding_id'],attempt=body['attempt'],ledger_uid=ledger['metadata']['uid'],
        allocation_sha256=old.sha256({k:v for k,v in record.items() if k!='state'}),
        ledger_custody_sha256=old.sha256(normalized),enrollment_uid=enrollment['metadata']['uid'],
        enrollment_sha256=approval.digest(body),approval_ref=f.ref,
        fence_command_sha256=old.sha256(['reviewed-live-root-fence']),proof=proof,
        retired_journals=journals,physical_rows=physical,
        review=dict(operator='root',reason='approved-pod-failed-before-native-transaction',
            gate_only_pod_sha256='sha256:'+'1'*64,controller_source_sha256='sha256:'+'2'*64,
            node_agent_source_sha256='sha256:'+'3'*64,registration_failure_sha256='sha256:'+'4'*64,
            native_transaction_never_started=True))
    return f,body,enrollment,ledger,evidence


class Backend:
    def __init__(self):
        self.f,self.body,self.enrollment,self.ledger,self.evidence = fixture()
        self.maps = {self.f.cm['metadata']['name']:self.f.cm}
        self.consumer = approval.ApprovalConsumer(agent,self.f.config,self.f.template,self.f.ref,
            lambda ns,name:copy.deepcopy(self.maps.get(name)))
        self.proof=copy.deepcopy(self.evidence['proof']);self.pod=None;self.abort=None
        self.locked=False;self.writes=[];self.verify_hook=None;self.verifications=0
    def fence(self,evidence):
        b=self
        class Fence:
            def __enter__(self):b.locked=True;return self
            def verify(self):
                b.verifications+=1
                if b.verify_hook:b.verify_hook(b)
                return copy.deepcopy(b.proof)
            def __exit__(self,*args):b.locked=False
        return Fence()
    def get_ledger(self):return copy.deepcopy(self.ledger)
    def get_enrollment(self,bid):return copy.deepcopy(self.enrollment)
    def get_node(self,name):return {'metadata':{'name':old.NODE,'uid':old.NODE_UID}}
    def get_pod(self,namespace,name):return copy.deepcopy(self.pod)
    def get_abort(self,bid):return copy.deepcopy(self.abort)
    def create_abort(self,body):
        assert self.locked;self.writes.append('abort');self.abort=copy.deepcopy(body)
        self.abort['metadata']['uid']='77777777-7777-4777-8777-777777777777'
    def compare_and_swap(self,snapshot,state):
        assert self.locked
        if snapshot['metadata']!=self.ledger['metadata']:raise old.AbortError('CAS conflict')
        self.writes.append('cas');self.ledger['data']['state.json']=old.canonical(state)
        self.ledger['metadata']['resourceVersion']='15';return copy.deepcopy(self.ledger)


class ApprovedAbortTest(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.find_spec('approval_before_gate')
        self.assertIsNotNone(spec,'The approval-aware never-gated publisher is missing')
        self.mod=__import__('approval_before_gate')
    def run_abort(self,b):
        return self.mod.execute_abort(b,b.evidence,consumer=b.consumer,models=b.f.models,
            expected_evidence_sha256=old.sha256(b.evidence))
    def test_actual_enrolling_shape_preserves_reference_full_other_custody_and_retries(self):
        b=Backend();original=json.loads(b.ledger['data']['state.json'])
        result=self.run_abort(b);self.run_abort(b)
        actual=json.loads(b.ledger['data']['state.json'])
        self.assertEqual(result['state'],'released');self.assertEqual(b.writes,['abort','cas'])
        row=actual['allocations'][b.body['binding_id']]
        self.assertEqual(row['approval_ref'],b.f.ref)
        self.assertEqual({k:v for k,v in row.items() if k not in ('state','pre_gate_abort')},
            {k:v for k,v in original['allocations'][b.body['binding_id']].items() if k!='state'})
        self.assertEqual(actual['allocations']['b'*60],original['allocations']['b'*60])
        self.assertEqual(json.loads(b.abort['data']['abort.json'])['enrollment_sha256'],approval.digest(b.body))
    def test_absent_registration_or_reserved_only_never_synthesizes_custody(self):
        for fault in ('missing_enrollment','no_intent','reserved'):
            with self.subTest(fault=fault):
                b=Backend()
                if fault=='missing_enrollment':b.enrollment=None
                else:
                    state=json.loads(b.ledger['data']['state.json']);row=state['allocations'][b.body['binding_id']]
                    if fault=='no_intent':row['intent']=None
                    else:row['state']='reserved'
                    b.ledger['data']['state.json']=old.canonical(state)
                with self.assertRaises(ValueError):self.run_abort(b)
                self.assertEqual(b.writes,[])
    def test_ref_epoch_writer_zero_proof_and_replacement_pod_fail_closed(self):
        for fault in ('swapped_ref','replaced_document','not_current','writers','memory','clients','tasks','pod','epoch'):
            with self.subTest(fault=fault):
                b=Backend()
                if fault=='swapped_ref':b.proof['approval_ref']['uid']=old.NODE_UID
                elif fault=='replaced_document':b.maps[b.f.ref['name']]['metadata']['uid']=old.NODE_UID
                elif fault=='not_current':b.proof['approval_current']=False
                elif fault=='writers':b.proof['native_writers_quiesced']=False
                elif fault in ('memory','clients','tasks'):
                    b.proof[{'memory':'global_gpu_memory_mib','clients':'global_gpu_clients','tasks':'pod_runtime_tasks'}[fault]]=1
                elif fault=='pod':b.pod={'metadata':{'uid':'88888888-8888-4888-8888-888888888888'}}
                else:b.proof['node_epoch']['driver_generation']=old.NODE_UID
                with self.assertRaises(ValueError):self.run_abort(b)
                self.assertEqual(b.writes,[])
    def test_charged_active_unknown_or_omitted_physical_history_is_rejected(self):
        for fault in ('charge','active','unknown','omitted','raw'):
            with self.subTest(fault=fault):
                b=Backend()
                if fault=='charge':b.evidence['physical_rows'][0]['used']=1
                elif fault=='active':b.evidence['physical_rows'][0]['offline']=False
                elif fault=='unknown':b.evidence['physical_rows'][0]['extra']=True
                elif fault=='omitted':b.evidence['physical_rows']=[]
                else:b.evidence['retired_journals'][0]['raw_base64']=base64.b64encode(b'{}').decode()
                b.evidence['proof']['physical_rows_sha256']=old.sha256(b.evidence['physical_rows'])
                b.evidence['proof']['retired_history_sha256']=old.sha256(b.evidence['retired_journals'])
                b.proof=copy.deepcopy(b.evidence['proof'])
                with self.assertRaises(ValueError):self.run_abort(b)
                self.assertEqual(b.writes,[])
    def test_custody_or_fence_changes_after_abort_never_release_capacity(self):
        b=Backend()
        def drift(value):
            if value.verifications==3:
                state=json.loads(value.ledger['data']['state.json'])
                state['allocations']['b'*60]['preserved']='changed'
                value.ledger['data']['state.json']=old.canonical(state)
        b.verify_hook=drift
        with self.assertRaises(ValueError):self.run_abort(b)
        self.assertNotIn('cas',b.writes)
    def test_abort_authority_replacement_between_publication_and_cas_retains_hold(self):
        b=Backend()
        def replace(value):
            if value.verifications==3:
                value.abort['metadata']['uid']='88888888-8888-4888-8888-888888888888'
        b.verify_hook=replace
        with self.assertRaises(ValueError):self.run_abort(b)
        self.assertNotIn('cas',b.writes)
    def test_real_transport_jsonpatch_tests_complete_ledger_data(self):
        b=Backend();backend=self.mod.KubernetesBackend(['reviewed-live-root-fence'])
        calls=[]
        def call(args,*,body=None,absent=False):
            raw=Path(args[args.index('--patch-file')+1]).read_text()
            calls.append((args,json.loads(raw)))
            return b.ledger
        backend.call=call
        backend.compare_and_swap(b.ledger,json.loads(b.ledger['data']['state.json']))
        args,patch=calls[0]
        self.assertEqual([(p['op'],p['path']) for p in patch],
            [('test','/metadata/uid'),('test','/metadata/resourceVersion'),('test','/data'),('replace','/data')])
        self.assertEqual(patch[2]['value'],b.ledger['data'])
        self.assertNotIn(b.body['members'][0],' '.join(args))
    def test_default_cli_is_inert(self):
        result=subprocess.run([os.sys.executable,str(HERE/'approval_before_gate.py')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout)
        self.assertEqual(value['state'],'inert');self.assertFalse(value['api_calls']);self.assertFalse(value['device_calls'])
    def test_first_approved_abort_consumes_real_proof_without_cap_journal_or_cleanup(self):
        b=Backend();self.run_abort(b)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700)
            store=agent.EnrollmentStore(root,b.f.models,trusted_uid=os.getuid())
            envelope=b.consumer.validate_enrollment(b.enrollment,b.f.models)
            store.synchronize([envelope]);b.consumer.remember(envelope,store)
            maps={b.enrollment['metadata']['name']:b.enrollment,old.LEDGER:b.ledger,
                b.abort['metadata']['name']:b.abort,b.f.ref['name']:b.f.cm}
            kube=SimpleNamespace(configmap=lambda ns,name:copy.deepcopy(maps.get(name)),pod=lambda intent:None)
            consumer=approval.ApprovalConsumer(agent,b.f.config,b.f.template,b.f.ref,kube.configmap)
            consumer.abort_epoch_reader=lambda:b.f.models.DriverEpoch(**b.proof['node_epoch'])
            journal=SimpleNamespace(read=lambda uid:None)
            rows,historical=consumer.validate_enrollments([b.enrollment],b.f.models,store,journal,kube)
            self.assertEqual(historical,{TARGET});self.assertEqual(rows[0]['enrollment'],b.body)
            self.assertIsNotNone(store.abort_record(TARGET));self.assertIsNone(journal.read(TARGET))
            self.assertFalse((root/'cleanup-publications').exists())


if __name__=='__main__':unittest.main()
