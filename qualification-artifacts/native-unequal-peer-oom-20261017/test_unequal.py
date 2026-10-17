"""CPU checks for the bounded cross-Hub 5/10 GiB qualification harness."""
import copy
import contextlib
import io
import json
import unittest
import sys
import types
from types import SimpleNamespace as Obj
from unittest.mock import patch
import peer_probe as probe
import current_preflight as current
import run_peer_oom as runner


def targets():
    return {'pods':{
        'a':{'namespace':'jupyterhub','name':'jupyter-cps-fixture','uid':'11111111-1111-4111-8111-111111111111','cap_mib':5120},
        'b':{'namespace':'cit-jhub','name':'jupyter-cit-fixture','uid':'22222222-2222-4222-8222-222222222222','cap_mib':10240}},
        'node':{'namespace':'cps-native-system','name':'node-fixture','uid':'33333333-3333-4333-8333-333333333333'},
        'observer':{'namespace':'gpu-operator','name':'cps-native-driver-control','uid':'44444444-4444-4444-8444-444444444444'}}


class TargetTests(unittest.TestCase):
    def test_cross_hub_caps_fit_existing_pilot(self):
        try:
            actual=current.validate_targets(targets())
        except ValueError as e:
            self.fail('Existing approved cross-Hub 5/10 pair must be supported: '+str(e))
        self.assertEqual(actual['pods']['b']['cap_mib'],10240)

    def test_foreign_namespace_swapped_caps_and_20_gib_refused(self):
        for key,field,value in [('a','namespace','cit-jhub'),('b','namespace','jupyterhub'),('a','cap_mib',10240),('b','cap_mib',5120),('b','cap_mib',20480),('a','cap_mib',True)]:
            with self.subTest(key=key,field=field,value=value):
                x=targets();x['pods'][key][field]=value
                with self.assertRaises(ValueError):current.validate_targets(x)

    def test_default_inert_without_external_operations(self):
        with patch('subprocess.run',side_effect=AssertionError('No external operations')),patch('subprocess.Popen',side_effect=AssertionError('No external operations')),contextlib.redirect_stdout(io.StringIO()) as out:
            runner.main([])
        self.assertEqual(json.loads(out.getvalue()),{'inert':True,'gpu_calls':False,'api_calls':False,'production_qualified':False})

class OOM(Exception):pass
class Tensor:
    def __init__(self,torch,size):self.torch=torch;self.size=size;self.value=0;torch.held+=size
    def __del__(self):self.torch.held-=self.size
    def fill_(self,value):self.value=value;return self
    def __getitem__(self,i):return self
    def item(self):return self.value
class Torch:
    OutOfMemoryError=OOM;uint8='uint8'
    def __init__(self,limit):self.cuda=self;self.limit=limit*1048576;self.held=0
    def empty(self,size,**kw):
        if self.held+size>self.limit:raise OOM()
        return Tensor(self,size)
    def synchronize(self):pass
    def empty_cache(self):pass

class PressureTests(unittest.TestCase):
    def test_ten_gib_case_reaches_nine_gib_before_oom_and_recovers(self):
        torch=Torch(9728);holds=[]
        with patch.object(probe,'CAP_MIB',10240),patch.object(probe.time,'sleep',side_effect=lambda seconds:holds.append((seconds,torch.held))):
            result=probe.run_steps(torch,lambda *a:None)
        self.assertTrue(result['bounded_step_sequence_passed'])
        self.assertEqual(result['held_before_oom_mib'],9728)
        self.assertEqual(holds,[(8,10200547328)])
        self.assertEqual(torch.held,0)

    def test_five_gib_oom_cannot_qualify_as_ten_gib(self):
        with patch.object(probe,'CAP_MIB',10240),patch.object(probe.time,'sleep'):
            result=probe.run_steps(Torch(4608),lambda *a:None)
        self.assertFalse(result['bounded_step_sequence_passed'])

def events(pressure_cap,peer_cap,held):
    peer=[{'phase':'peer_tick','tick':i+1,'monotonic_ns':n}for i,n in enumerate(range(1_000_000_000,13_000_000_000,1_000_000_000))]
    common={'state':'measurement-completed','hardware':{'gpu_uuid':runner.GPU,'torch_version':'2.11.0'},'production_qualified':False}
    peer.append({**common,'phase':'receipt','case':'peer','peer_loop_passed':True,'cap_mib':peer_cap})
    oom=[{'phase':'over-allocation-error','monotonic_ns':2_000_000_000,'typed_oom':True},
        {'phase':'oom-held-start','monotonic_ns':2_100_000_000,'held_tensor_mib':held},
        {'phase':'oom-held-end','monotonic_ns':10_100_000_000,'held_tensor_mib':held},
        {'phase':'after-recovery-free64','monotonic_ns':10_500_000_000},
        {**common,'phase':'receipt','case':'oom','cap_mib':pressure_cap,'bounded_step_sequence_passed':True,'over_denied':True,'ordinary_byte':19,'recovery_byte':37,'held_before_oom_mib':held,'over_error':{'kind':'torch.OutOfMemoryError','cuda_error_code':None}}]
    physical=[{'observed_monotonic_ns':n,'physical_free_bytes':16*1024**3,'physical_total_bytes':40*1024**3,'gpu_uuid':runner.GPU}for n in (3_000_000_000,5_000_000_000,7_000_000_000)]
    return peer,oom,physical

class AssessmentTests(unittest.TestCase):
    def test_valid_pressure_and_peer_caps_in_both_directions(self):
        for cap,peer_cap,held in [(5120,10240,4608),(10240,5120,9728)]:
            with self.subTest(cap=cap):
                result=runner.assess(*events(cap,peer_cap,held),pressure_cap_mib=cap)
                self.assertTrue(result['measurement_passed'])
                self.assertEqual(result['pressure_cap_mib'],cap)
                self.assertFalse(result['production_qualified'])

    def test_low_held_pressure_cannot_qualify_ten_gib(self):
        with self.assertRaises(ValueError):runner.assess(*events(10240,5120,4608),pressure_cap_mib=10240)

    def test_swapped_receipt_caps_cannot_qualify(self):
        peer,oom,samples=events(5120,10240,4608)
        peer[-1]['cap_mib']=5120
        with self.assertRaises(ValueError):runner.assess(peer,oom,samples,pressure_cap_mib=5120)

class NodeReadTests(unittest.TestCase):
    def run_node_read(self, observed_caps):
        records={};pods=[]
        for key,cap in [('a',5120),('b',10240)]:
            row=targets()['pods'][key];uid=row['uid'];pod={'metadata':{'uid':uid,'name':row['name'],'namespace':row['namespace']}}
            identity=Obj(boot_id=current.BOOT,driver_generation=current.GENERATION,gpu_uuid=current.GPU,cgroup_relative='/'+uid,cgroup_inode=17,cgroup_device=1,to_dict=lambda:{'kind':'test'})
            intent=Obj(pod_uid=uid,cap_mib=cap,namespace=row['namespace'],name=row['name'],spec_sha256='spec',policy_hash='sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0',to_dict=lambda:{'kind':'test'})
            records[uid]=Obj(state='sealed',intent=intent,limit=cap,readback=cap,identity=identity,seal_id='test',receipt=lambda:{'gate':'test'})
            pods.append(pod)
        class FakePath:
            def __init__(self,value):self.value=str(value)
            def __truediv__(self,value):return FakePath(self.value+'/'+str(value))
            def stat(self):return Obj(st_ino=17,st_dev=1)
            def read_bytes(self):return b'test'
        def read(path):
            return {'gate':'test'} if '/receipts/' in path.value else records[next(uid for uid in records if uid in path.value)]
        class Nvml:
            def get(self,gpu,parent):
                uid=next(uid for uid in records if uid in parent.value)
                cap=observed_caps[uid]
                return {'soft':cap*1048576,'hard':cap*1048576,'used':0}
            def close(self):pass
        modules={}
        for name,values in {
            'cps_compute.native_gpu_controller':{'CapRecord':Obj(from_dict=lambda x:x)},
            'cps_compute.native_node.backend':{'private_read':read},
            'cps_compute.native_node.nvml':{'Nvml':Nvml},
            'cps_compute.native_gpu_runtime':{'native_spec_sha256':lambda pod:'spec'}}.items():
            module=types.ModuleType(name);module.__dict__.update(values);modules[name]=module
        payload={'pods':pods,'caps_mib':[5120,10240]}
        with patch.dict(sys.modules,modules),patch('pathlib.Path',FakePath),patch.object(sys,'stdin',io.StringIO(json.dumps(payload))),contextlib.redirect_stdout(io.StringIO()) as output:
            exec(compile(current.NODE_READ,'<node-read>','exec'),{})
        return json.loads(output.getvalue())

    def test_sealed_limits_match_each_distinct_parent_cap(self):
        caps={v['uid']:v['cap_mib']for v in targets()['pods'].values()}
        try:rows=self.run_node_read(caps)
        except Exception as error:self.fail('Node reader must attest the exact unequal pair: '+type(error).__name__)
        self.assertEqual([r['inventory_row']['hard']for r in rows],[5368709120,10737418240])

    def test_cit_five_gib_readback_cannot_be_accepted_as_ten_gib(self):
        caps={v['uid']:5120 for v in targets()['pods'].values()}
        with self.assertRaises(AssertionError):self.run_node_read(caps)

class InvocationTests(unittest.TestCase):
    def test_remote_transport_carries_manifest_cap_and_isolated_python(self):
        class Captured(Exception):pass
        for key,want in [('a','5120'),('b','10240')]:
            seen=[]
            def launch(argv,**kw):seen.append(argv);raise Captured()
            with patch.object(runner,'private_file',return_value=io.BytesIO()),patch.object(runner.subprocess,'Popen',side_effect=launch),self.assertRaises(Captured):
                runner.ProbeRun(targets()['pods'][key],'oom',45,b'source',__import__('pathlib').Path('/unused'))
            argv=seen[0]
            self.assertEqual(argv[argv.index('--cap-mib')+1],want)
            self.assertEqual(argv[argv.index('--duration')+1],'45')
            self.assertIn('-I',argv)

    def test_execute_without_cap_or_with_20_gib_refuses_before_gpu_or_api(self):
        for extra in [[],['--cap-mib','20480']]:
            with self.subTest(extra=extra),patch.object(sys,'argv',['probe','--execute',*extra]),patch('subprocess.run',side_effect=AssertionError('No API')),patch('ctypes.CDLL',side_effect=AssertionError('No GPU')),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
                probe.main()
            self.assertEqual(error.exception.code,2)

    def test_changed_source_refused_before_target_read_or_output_creation(self):
        args=['--execute','--manifest','/absent','--manifest-sha256','0'*64,'--runner-sha256','0'*64,'--probe-sha256','0'*64,'--preflight-sha256','0'*64,'--output','/must-not-exist']
        with patch.object(current,'read_targets',side_effect=AssertionError('No target read')),self.assertRaises(ValueError):runner.main(args)

if __name__=='__main__':unittest.main()
