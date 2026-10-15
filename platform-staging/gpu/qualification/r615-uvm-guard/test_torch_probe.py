import unittest
import torch_probe as probe


class Oom(RuntimeError):pass
class Accelerator(RuntimeError):
    def __init__(self,code):self.error_code=code
class Torch:
    OutOfMemoryError=Oom
    AcceleratorError=Accelerator
    class cuda:OutOfMemoryError=Oom


class Tensor:
    def __init__(self,size,owner):self.size=size;self.owner=owner;self.byte=0
    def fill_(self,value):self.owner.touched.append(self.size);self.byte=value
    def __getitem__(self,key):return self
    def item(self):return self.byte


class Backend(Torch):
    uint8='uint8'
    def __init__(self,error=None):self.error=error;self.attempts=[];self.touched=[]
    def empty(self,size,**kwargs):
        self.attempts.append(size)
        if size==5120*1048576 and self.error is not None:raise self.error
        return Tensor(size,self)
    class cuda(Torch.cuda):
        @staticmethod
        def synchronize():pass
        @staticmethod
        def empty_cache():pass


class TorchProbeTests(unittest.TestCase):
    def test_phase_markers_cover_real_sequence_and_over_success_is_never_touched(self):
        for error,passed in ((Accelerator(2),True),(None,False)):
            backend=Backend(error);marks=[]
            result=probe.run_sequence(backend,5120,lambda:{'limits':{'soft':5120*1048576,'hard':5120*1048576,'used':436289216}},
                lambda phase,extra=None:marks.append(phase))
            self.assertEqual(result['bounded_torch_sequence_passed'],passed)
            self.assertEqual(backend.attempts,[64*1048576,5120*1048576,64*1048576])
            self.assertEqual(backend.touched,[64*1048576,64*1048576])
            self.assertIn('before-touch64',marks);self.assertIn('after-touch64',marks)
            self.assertIn('before-over-allocation',marks);self.assertIn('after-recovery-free64',marks)
        with self.assertRaises(RuntimeError):
            probe.run_sequence(Backend(RuntimeError('out of memory')),5120,
                lambda:{'limits':{'soft':5120*1048576,'hard':5120*1048576,'used':436289216}},lambda *args:None)

    def test_fixture_uses_new_pods_and_existing_gate_bytes(self):
        import render_torch_fixture
        result=render_torch_fixture.render();cm=result['items'][0]
        self.assertEqual(set(cm['data']),{'runtime_probe.py','cuda_probe.py','pod_cap.py','gate_wait.py','torch_probe.py'})
        pods=result['items'][1:]
        self.assertEqual({p['metadata']['name'] for p in pods},{'uvm-guard-torch','uvm-guard-torch-peer'})
        for pod in pods:
            gate=pod['spec']['initContainers'][0]
            self.assertEqual(gate['command'][-1],'512' if pod['metadata']['name'].endswith('peer') else '5120')
            self.assertFalse(pod['spec']['automountServiceAccountToken'])
            self.assertNotIn('imagePullSecrets',pod['spec'])

    def test_only_typed_oom_or_actual_cuda_memory_error_code_is_accepted(self):
        self.assertEqual(probe.oom_proof(Oom(),Torch),{'kind':'torch.OutOfMemoryError','cuda_error_code':None})
        self.assertEqual(probe.oom_proof(Accelerator(2),Torch),{'kind':'torch.AcceleratorError','cuda_error_code':2})
        for error in (Accelerator(True),Accelerator('2'),Accelerator(3),Accelerator(801),RuntimeError('CUDA out of memory')):
            self.assertIsNone(probe.oom_proof(error,Torch))

    def test_5120_cap_is_torch_only_and_over_attempt_requires_actual_positive_baseline(self):
        self.assertEqual(probe.plan(5120)['over_mib'],5120)
        for cap,mode in ((5120,'raw'),(5120,'heartbeat'),(1024,'torch'),(True,'torch')):
            with self.assertRaises(ValueError):probe.plan(cap,mode)
        probe.require_over_margin({'limits':{'soft':5120*1048576,'hard':5120*1048576,'used':436289216}},5120)
        for used in (0,-1):
            with self.assertRaises(ValueError):probe.require_over_margin({'limits':{'soft':5120*1048576,'hard':5120*1048576,'used':used}},5120)


if __name__=='__main__':unittest.main()
