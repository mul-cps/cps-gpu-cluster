import copy
import ctypes as C
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch


UID = 'e2714d97-1b73-4ba2-aa15-9ad276379a05'
GPU = 'GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
CID = 'a' * 64
CG = '/kubepods.slice/kubepods-besteffort.slice/kubepods-besteffort-pod' + UID.replace('-', '_') + '.slice'


class Driver:
    version = '615.71.09'
    def __init__(self):
        self.limits = {}; self.on_set = None
    def get(self, gpu, path):
        assert gpu == GPU
        return self.limits.get(path)
    def set(self, gpu, path, soft, hard):
        assert gpu == GPU
        self.limits[path] = {'soft': soft, 'hard': hard, 'used': 0}
        if self.on_set: self.on_set()


class PodCapTests(unittest.TestCase):
    def setUp(self):
        try: self.cap = importlib.import_module('pod_cap')
        except ModuleNotFoundError: self.fail('The inert Pod cap helper is not implemented')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.proc = self.root/'proc'; self.cg = self.root/'cgroup'
        (self.proc/'123').mkdir(parents=True); (self.proc/'sys/kernel/random').mkdir(parents=True)
        (self.proc/'sys/kernel/random/boot_id').write_text('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n')
        (self.proc/'123/stat').write_text('123 (gate with ) spaces) ' + ' '.join(['S'] + ['0']*18 + ['12345']))
        (self.proc/'123/cgroup').write_text('0::' + CG + '/cri-containerd-' + CID + '.scope\n')
        self.parent = self.cg/CG.lstrip('/'); self.leaf = self.parent/('cri-containerd-' + CID + '.scope')
        self.leaf.mkdir(parents=True); (self.cg/'cgroup.controllers').write_text('cpu memory misc\n')
        (self.parent/'cgroup.events').write_text('populated 1\n')
        self.pod = {'metadata': {'uid': UID, 'name': 'canary', 'namespace': 'qualification', 'resourceVersion': '7'},
                    'spec': {'nodeName': 'k3s-wk-gpu2', 'initContainers': [{'name': 'cps-driver-cap-gate',
                        'image': 'example.invalid/gate@sha256:' + 'b'*64}], 'containers': [{'name': 'main'}]},
                    'status': {'containerStatuses': []}}
        spec_hash = hashlib.sha256(json.dumps(self.pod['spec'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.intent = {'pod_uid': UID, 'namespace': 'qualification', 'name': 'canary', 'node': 'k3s-wk-gpu2',
                       'gpu_uuid': GPU, 'cap_mib': 64, 'spec_sha256': spec_hash}
        self.cri = {'status': {'id': CID, 'state': 'CONTAINER_RUNNING', 'labels': {
            'io.kubernetes.pod.uid': UID, 'io.kubernetes.pod.namespace': 'qualification',
            'io.kubernetes.pod.name': 'canary', 'io.kubernetes.container.name': 'cps-driver-cap-gate'}},
            'info': {'pid': 123, 'runtimeSpec': {'linux': {'cgroupsPath': 'slice:cri-containerd:' + CID}}}}
        self.driver = Driver(); self.receipt = self.root/'receipt.json'

    def discover(self):
        return self.cap.discover(self.intent, self.pod, self.cri, self.proc, self.cg)

    def apply(self, pod=None):
        return self.cap.apply(self.intent, lambda: self.pod if pod is None else pod(),
                              lambda: self.cri, self.proc, self.cg, self.driver, self.receipt)

    def test_aggregate_limit_is_on_real_pod_parent_and_in_bytes(self):
        proof = self.apply()
        self.assertEqual(list(self.driver.limits), [str(self.parent)])
        self.assertEqual(self.driver.limits[str(self.parent)]['hard'], 67108864)
        self.assertEqual(proof['pid_start_ticks'], 12345)
        self.assertEqual(proof['state'], 'applied-before-main')
        self.assertFalse(proof['hostile_isolation_qualified'])
        self.assertEqual(self.receipt.stat().st_mode & 0o777, 0o600)

    def test_ambiguous_virgin_get_requires_successful_set_and_exact_readback(self):
        original = self.driver.get
        self.driver.get = lambda gpu, path: original(gpu, path) or {'nvml_result': 3, 'state': 'unset-or-unsupported'}
        proof = self.apply()
        self.assertEqual(proof['state'], 'applied-before-main')
        self.assertEqual(proof['readback']['hard'], 67108864)
        self.assertFalse(proof['hostile_isolation_qualified'])

    def test_ambiguous_virgin_get_and_unsupported_set_never_release_gate(self):
        self.driver.get = lambda *args: {'nvml_result': 3, 'state': 'unset-or-unsupported'}
        def unsupported(*args): raise ValueError('NVML operation failed with code 3')
        self.driver.set = unsupported
        with self.assertRaisesRegex(ValueError, 'code 3'): self.apply()
        self.assertEqual(json.loads(self.receipt.read_text())['state'], 'failed-cap-retained')
        self.assertEqual(self.driver.limits, {})

    def test_ambiguous_get_after_set_is_not_a_readback_or_cleanup_proof(self):
        self.driver.get = lambda *args: {'nvml_result': 3, 'state': 'unset-or-unsupported'}
        with self.assertRaisesRegex(ValueError, 'readback'): self.apply()
        proof = json.loads(self.receipt.read_text())
        self.assertEqual(proof['state'], 'failed-cap-retained')
        (self.parent/'cgroup.events').write_text('populated 0\n')
        with self.assertRaises(ValueError): self.cap.cleanup(proof, lambda: None, self.cg, self.driver, self.proc)
        self.assertEqual(self.driver.limits[str(self.parent)]['hard'], 67108864)

    def test_foreign_cri_pod_or_container_is_denied_before_setting(self):
        for key, value in [('io.kubernetes.pod.uid', 'foreign'), ('io.kubernetes.container.name', 'main')]:
            with self.subTest(key=key):
                self.cri['status']['labels'][key] = value
                with self.assertRaises(ValueError): self.apply()
                self.assertEqual(self.driver.limits, {})
                self.cri['status']['labels'][key] = UID if key.endswith('uid') else 'cps-driver-cap-gate'

    def test_already_started_main_and_changed_spec_deny(self):
        self.pod['status']['containerStatuses'] = [{'name': 'main', 'state': {'running': {}}, 'restartCount': 0}]
        with self.assertRaises(ValueError): self.apply()
        self.pod['status']['containerStatuses'] = []; self.pod['spec']['containers'][0]['name'] = 'changed'
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(self.driver.limits, {})

    def test_foreign_uid_cgroup_or_symlink_is_denied(self):
        path = self.proc/'123/cgroup'
        path.write_text('0::/kubepods.slice/other.slice/cri-containerd-' + CID + '.scope\n')
        with self.assertRaises(ValueError): self.discover()
        path.write_text('0::' + CG + '/cri-containerd-' + CID + '.scope\n')
        self.leaf.rmdir(); self.leaf.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): self.discover()

    def test_old_driver_or_dmem_backend_cannot_apply_misc_prototype(self):
        self.driver.version = '580.95.05'
        with self.assertRaises(ValueError): self.apply()
        self.driver.version = '615.71.09'; (self.parent/'dmem.max').write_text('max\n')
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(self.driver.limits, {})

    def test_unreviewed_or_noninteger_cap_denies(self):
        for value in (0, True, 65, '64'):
            self.intent['cap_mib'] = value
            with self.assertRaises(ValueError): self.apply()
        self.assertEqual(self.driver.limits, {})

    def test_existing_child_override_denies_aggregate_claim(self):
        self.driver.limits[str(self.leaf)] = {'soft': 0, 'hard': 134217728, 'used': 0}
        with self.assertRaises(ValueError): self.apply()
        self.assertNotIn(str(self.parent), self.driver.limits)

    def test_nested_descendant_override_is_not_hidden_by_unlimited_container_scope(self):
        nested = self.leaf/'delegated'; nested.mkdir()
        self.driver.limits[str(nested)] = {'soft': 0, 'hard': 134217728, 'used': 0}
        with self.assertRaises(ValueError): self.apply()
        self.assertNotIn(str(self.parent), self.driver.limits)

    def test_pid_reuse_after_set_fails_and_retains_restrictive_limit(self):
        self.driver.on_set = lambda: (self.proc/'123/stat').write_text('123 (gate) ' + ' '.join(['S'] + ['0']*18 + ['99999']))
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(self.driver.limits[str(self.parent)]['hard'], 67108864)
        self.assertEqual(json.loads(self.receipt.read_text())['state'], 'failed-cap-retained')

    def test_pod_uid_or_resource_version_change_blocks_gate_release(self):
        old = copy.deepcopy(self.pod)
        calls = [old, dict(old, metadata=dict(old['metadata'], resourceVersion='8'))]
        with self.assertRaises(ValueError): self.apply(lambda: calls.pop(0))
        self.assertEqual(self.driver.limits[str(self.parent)]['hard'], 67108864)

    def test_readback_mismatch_never_clears_cap_or_releases_gate(self):
        self.driver.on_set = lambda: self.driver.limits[str(self.parent)].update(hard=1)
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(self.driver.limits[str(self.parent)]['hard'], 1)
        self.assertEqual(json.loads(self.receipt.read_text())['state'], 'failed-cap-retained')

    def test_exact_cleanup_requires_no_live_tasks_and_preserves_foreign_limit(self):
        proof = self.apply()
        with self.assertRaises(ValueError): self.cap.cleanup(proof, lambda: None, self.cg, self.driver, self.proc)
        (self.parent/'cgroup.events').write_text('populated 0\n')
        self.driver.limits[str(self.parent)]['hard'] = 134217728
        with self.assertRaises(ValueError): self.cap.cleanup(proof, lambda: None, self.cg, self.driver, self.proc)
        self.driver.limits[str(self.parent)]['hard'] = 67108864
        result = self.cap.cleanup(proof, lambda: None, self.cg, self.driver, self.proc)
        self.assertEqual(result['state'], 'cleared')
        self.assertEqual(self.driver.limits[str(self.parent)], {'soft': 0, 'hard': 18446744073709551615, 'used': 0})

    def test_cleanup_replaced_cgroup_inode_denies(self):
        proof = self.apply(); proof['cgroup_inode'] += 1
        (self.parent/'cgroup.events').write_text('populated 0\n')
        with self.assertRaises(ValueError): self.cap.cleanup(proof, lambda: None, self.cg, self.driver, self.proc)
        self.assertEqual(self.driver.limits[str(self.parent)]['hard'], 67108864)

    def test_cleanup_old_boot_receipt_cannot_clear_new_driver_generation(self):
        proof = self.apply(); (self.parent/'cgroup.events').write_text('populated 0\n')
        (self.proc/'sys/kernel/random/boot_id').write_text('new-boot\n')
        with self.assertRaises(ValueError): self.cap.cleanup(proof, lambda: None, self.cg, self.driver, self.proc)
        self.assertEqual(self.driver.limits[str(self.parent)]['hard'], 67108864)

    def test_nvml_abi_transmits_exact_64bit_bytes_and_reads_current_used(self):
        class Function:
            def __init__(self, body): self.body = body
            def __call__(self, *args): return self.body(*args)
        values = {}
        missing = [6]
        def setter(handle, pointer):
            address, soft, hard = struct.unpack('=QQQ', C.string_at(pointer, 24))
            self.assertEqual(handle.value, 0x123456789)
            values[C.string_at(address).decode()] = (soft, hard)
            return 0
        def getter(handle, pointer):
            address = struct.unpack('=Q', C.string_at(pointer, 8))[0]
            path = C.string_at(address).decode()
            if path not in values: return missing[0]
            soft, hard = values[path]
            C.memmove(pointer, struct.pack('=QQQQ', address, soft, hard, 4096), 32)
            return 0
        class Library: pass
        library = Library()
        library.nvmlInit_v2 = Function(lambda: 0); library.nvmlShutdown = Function(lambda: 0)
        library.nvmlSystemGetDriverVersion = Function(lambda buf, count: (C.memmove(buf, b'615.71.09\0', 10), 0)[1])
        library.nvmlDeviceGetHandleByUUID = Function(lambda name, pointer: (setattr(C.cast(pointer, C.POINTER(C.c_void_p)).contents, 'value', 0x123456789), 0)[1])
        library.nvmlDeviceGetMigMode = Function(lambda *args: 3)
        library.nvmlDeviceSetMemoryLimits_v1 = Function(setter); library.nvmlDeviceGetMemoryLimits_v1 = Function(getter)
        with patch('pod_cap.C.CDLL', return_value=library):
            driver = self.cap.Nvml()
            self.assertIsNone(driver.get(GPU, str(self.parent)))
            missing[0] = 3
            self.assertEqual(driver.get(GPU, str(self.parent)), {'nvml_result': 3, 'state': 'unset-or-unsupported'})
            driver.set(GPU, str(self.parent), 67108864, 134217728)
            self.assertEqual(driver.get(GPU, str(self.parent)), {'soft': 67108864, 'hard': 134217728, 'used': 4096})
            driver.set(GPU, str(self.parent), 0, 18446744073709551615)
            self.assertEqual(driver.get(GPU, str(self.parent))['hard'], 18446744073709551615)
            driver.close()


if __name__ == '__main__': unittest.main()
