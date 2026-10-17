"""CPU only: synthetic kmsg records; never opens kernel devices."""
import base64,copy,hashlib,importlib.util,json
from pathlib import Path
import unittest

PATH=Path(__file__).with_name('kernel_witness_validator.py')
v=None
if PATH.exists():
    spec=importlib.util.spec_from_file_location('witness_validator',PATH)
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

TRIAL='11111111-2222-4333-8444-555555555555'
NONCE='22222222-2222-4333-8444-555555555555'
COLLECTOR='a'*64;VALIDATOR='b'*64
def digest(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def clocks(n):return {key:n for key in ('monotonic_ns','monotonic_raw_ns','boottime_ns','realtime_ns')}
def fixture():
    attribution={'kind':'root-read-only-importer-attribution','trial_id':TRIAL,'host_pid':123,'host_tgid':123,
      'namespace_pid':7,'pid_start_ticks':900,'gpu_id':1552,'gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56',
      'pod_uid':'33333333-2222-4333-8444-555555555555','boot_id':'209f8bc9-a478-48e4-925a-6e07ffa56f7a',
      'driver_generation':'b10498fc-9153-4394-875a-ea7cfb498625'}
    api={'phase':'import-result','trial_id':TRIAL,'namespace_pid':7,'api':'cuMemImportFromShareableHandle','expect':'deny',
      'cuda_result':800,'cuda_name':'CUDA_ERROR_NOT_PERMITTED','expected_kernel_reason':6,'expected_kernel_status':27,
      'call_started_monotonic_ns':120,'call_ended_monotonic_ns':130,'production_qualified':False}
    # Deliberately unrelated kernel timestamps, reproducing the live clock discrepancy.
    begin=f'CPS_VMM_IMPORT_WITNESS trial={TRIAL} nonce={NONCE} phase=begin tgid=123 start=900 gpu=1552'
    end=begin.replace('phase=begin','phase=end')
    rows=[f'14,50,9000000000,-;{begin}\n',
          '4,51,9000000030,-;NVRM: CPS native import denied gpu=1552 reason=6 clientKind=4 status=0x1b tgid=123\n',
          f'14,52,9000000040,-;{end}\n']
    c={'version':1,'kind':'root-kernel-vmm-sequence-witness','trial_id':TRIAL,'nonce':NONCE,
      'node':'k3s-wk-gpu2','node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41',
      'boot_id':attribution['boot_id'],'driver_generation':attribution['driver_generation'],
      'collector_sha256':COLLECTOR,'validator_sha256':VALIDATOR,'attribution_sha256':digest(attribution),
      'api_result_sha256':digest(api),'overruns':0,'truncated':False,'same_time_namespace':True,
      'identity_verified':True,'markers':{'begin':{'clock_before':clocks(100),'clock_after':clocks(110)},
                                      'end':{'clock_before':clocks(140),'clock_after':clocks(150)}},
      'records_b64':[base64.b64encode(row.encode()).decode()for row in rows]}
    return c,attribution,api

class WitnessTests(unittest.TestCase):
    def validate(self,c,a,event):
        self.assertIsNotNone(v,'Sequence-based witness validator is required')
        return v.validate_capture(c,a,event,collector_sha256=COLLECTOR,validator_sha256=VALIDATOR)
    def test_kernel_sequence_proves_branch_with_unrelated_clock_epochs(self):
        result=self.validate(*fixture())
        self.assertTrue(result['kernel_witness_correlated'])
        self.assertFalse(result['production_qualified'])
        self.assertEqual(result['kernel_sequence'],51)
    def test_lost_or_truncated_kernel_records_fail(self):
        for fault in ('gap','duplicate','reorder','overflow','truncated','badbase64','fragment','duplicate-witness'):
            c,a,e=fixture()
            if fault=='gap':c['records_b64'][1]=base64.b64encode(base64.b64decode(c['records_b64'][1]).replace(b',51,',b',49,')).decode()
            elif fault=='duplicate':c['records_b64'].insert(1,c['records_b64'][0])
            elif fault=='reorder':c['records_b64'].reverse()
            elif fault=='overflow':c['overruns']=1
            elif fault=='truncated':c['truncated']=True
            elif fault=='badbase64':c['records_b64'][1]='not base64!'
            elif fault=='fragment':c['records_b64'][1]=base64.b64encode(base64.b64decode(c['records_b64'][1]).replace(b',-;',b',c;')).decode()
            else:
                c['records_b64'].insert(2,base64.b64encode(base64.b64decode(c['records_b64'][1]).replace(b',51,',b',52,')).decode())
                c['records_b64'][-1]=base64.b64encode(base64.b64decode(c['records_b64'][-1]).replace(b',52,',b',53,')).decode()
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.validate(c,a,e)
    def test_user_injected_or_foreign_kernel_denial_cannot_pass(self):
        for old,new in ((b'4,51',b'12,51'),(b'gpu=1552',b'gpu=1553'),(b'reason=6',b'reason=5'),
                        (b'clientKind=4',b'clientKind=3'),(b'status=0x1b',b'status=0x1a'),(b'tgid=123',b'tgid=124')):
            c,a,e=fixture();c['records_b64'][1]=base64.b64encode(base64.b64decode(c['records_b64'][1]).replace(old,new)).decode()
            with self.subTest(new=new),self.assertRaises(ValueError):self.validate(c,a,e)
    def test_missing_markers_wrong_nonce_and_replay_fail(self):
        for fault in ('missing','nonce','trial','identity','generation','source','selfasserted','extra'):
            c,a,e=fixture()
            if fault=='missing':c['records_b64']=c['records_b64'][1:]
            elif fault=='nonce':c['nonce']=TRIAL
            elif fault=='trial':e['trial_id']=NONCE
            elif fault=='identity':a['pid_start_ticks']+=1
            elif fault=='generation':c['driver_generation']='replaced'
            elif fault=='source':c['collector_sha256']='c'*64
            elif fault=='selfasserted':c['identity_verified']=False
            else:c['override']=True
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.validate(c,a,e)
    def test_api_denial_must_occur_inside_actual_root_marker_commands(self):
        for fault in ('before','after','wrongAPI','wrongPID','wrongResult','bool','time-ns'):
            c,a,e=fixture()
            if fault=='before':e['call_started_monotonic_ns']=105
            elif fault=='after':e['call_ended_monotonic_ns']=145
            elif fault=='wrongAPI':e['api']='cuIpcOpenMemHandle_v2'
            elif fault=='wrongPID':e['namespace_pid']=8
            elif fault=='wrongResult':e['cuda_result']=2
            elif fault=='bool':e['call_started_monotonic_ns']=True
            else:c['same_time_namespace']=False
            c['api_result_sha256']=digest(e)
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.validate(c,a,e)

if __name__=='__main__':unittest.main()
