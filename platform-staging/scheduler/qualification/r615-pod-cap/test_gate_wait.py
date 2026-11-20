import copy
import importlib
import unittest
from unittest.mock import patch


class GateTests(unittest.TestCase):
    def setUp(self):
        try: self.gate = importlib.import_module('gate_wait')
        except ModuleNotFoundError: self.fail('Trusted first-init waiter is not implemented')
        self.proof = {'state':'applied-before-main','pod_uid':'e2714d97-1b73-4ba2-aa15-9ad276379a05',
            'gpu_uuid':'GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee','cap_bytes':67108864,
            'boot_id':'same-boot','pid_start_ticks':12345,'readback':{'soft':67108864,'hard':67108864}}

    def verify(self, proof):
        return self.gate.verify(proof, self.proof['pod_uid'], self.proof['gpu_uuid'], 64, 'same-boot', 12345)

    def test_current_exact_applied_receipt_is_required_to_exit_first_init(self):
        self.assertTrue(self.verify(self.proof))
        for key, value in [('state','prepared-before-set'),('pod_uid','foreign'),('gpu_uuid','foreign'),
                           ('cap_bytes',134217728),('boot_id','old-boot'),('pid_start_ticks',1)]:
            proof=copy.deepcopy(self.proof);proof[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):self.verify(proof)

    def test_failed_or_mismatched_driver_readback_never_releases_main(self):
        for readback in (None, {'soft':0,'hard':67108864}, {'soft':67108864,'hard':134217728}):
            proof=copy.deepcopy(self.proof);proof['readback']=readback
            with self.assertRaises(ValueError):self.verify(proof)

    def test_manual_setup_wait_is_bounded_at_600_seconds_without_release(self):
        args=['gate_wait.py','--execute','--receipt','/nonexistent-r615-test/ready.json',
              '--pod-uid',self.proof['pod_uid'],'--gpu-uuid',self.proof['gpu_uuid'],'--cap-mib','64']
        with patch('sys.argv',args):
            with patch('gate_wait.time.monotonic',side_effect=[0,599.9,600.1]), patch('gate_wait.time.sleep') as sleep:
                with self.assertRaises(TimeoutError):self.gate.main()
                sleep.assert_called_once_with(0.2)


if __name__=='__main__':unittest.main()
