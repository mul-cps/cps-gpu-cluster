"""CPU-only inventory contracts; these tests never build or load a driver."""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).parent
SOURCE = pathlib.Path('/tmp/cps-r615-import-primary/tree')


class ReadonlyCapTest(unittest.TestCase):
    def test_map_snapshot_control_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / 'readonly-cap-test'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I' + str(HERE), str(HERE / 'readonly_cap_test.c'), '-o', str(binary)],
                check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)

    def test_proc_credentials_and_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / 'readonly-cap-proc-test'
            subprocess.run(['cc', '-std=c11', '-D_DEFAULT_SOURCE', '-Wall', '-Wextra', '-Werror',
                '-I' + str(HERE), str(HERE / 'readonly_cap_proc_test.c'), '-o', str(binary)],
                check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)

    def test_optional_pinned_render_and_apply(self):
        if not SOURCE.exists():
            self.skipTest('Pristine NVIDIA615.71.09 CPU source unavailable')
        spec = importlib.util.spec_from_file_location('readonly_render', HERE / 'render_patch.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        old_original, old_changed = module.render(SOURCE)
        original, changed = module.render(SOURCE, readonly_cap_inventory=True)
        self.assertEqual(len(old_changed), 12)
        self.assertEqual(len(changed), 15)
        self.assertNotIn('kernel-open/nvidia/nv-procfs.c', old_original)
        proc = changed['kernel-open/nvidia/nv-procfs.c']
        self.assertIn('"cps_native_caps", S_IFREG | S_IRUSR', proc)
        self.assertIn('ns_capable(&init_user_ns, CAP_SYS_ADMIN)', proc)
        self.assertIn('uid_eq(current_euid(), GLOBAL_ROOT_UID)', proc)
        self.assertNotIn('.NV_PROC_OPS_WRITE', (HERE / 'readonly_cap_proc.c').read_text())
        self.assertNotIn('.NV_PROC_OPS_LSEEK', (HERE / 'readonly_cap_proc.c').read_text())
        self.assertIn('--undefined=rm_cps_get_readonly_caps\n', changed['src/nvidia/exports_link_command.txt'])
        self.assertIn('os_cps_native_import_guard_enabled()', proc)
        self.assertIn('nv_down_read_interruptible(&nv_system_pm_lock)', proc)
        self.assertIn('NV_ERR_BUFFER_TOO_SMALL', changed['src/nvidia/src/kernel/mem_mgr/memacct.c'])
        os_code = changed['kernel-open/nvidia/os-interface.c']
        self.assertIn('cgroup_id(group)', os_code)
        self.assertIn('READ_ONCE(group->self.flags)', os_code)
        self.assertIn('CSS_ONLINE', os_code)
        self.assertIn('group->root != &cgrp_dfl_root', os_code)
        self.assertNotIn('cgroup_on_dfl(group)', os_code)
        self.assertIn('sizeof(ino_t) < sizeof(NvU64)', os_code)
        for name in ('kernel-open/common/inc/os-interface.h',
                     'src/nvidia/arch/nvalloc/unix/include/os-interface.h'):
            self.assertIn('CpsNativeCapRow', changed[name])
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp)
            for name, data in original.items():
                (target / name).parent.mkdir(parents=True, exist_ok=True)
                (target / name).write_text(data)
            patch = module.patch(original, changed)
            subprocess.run(['git', 'apply', '--check', '-'], input=patch,
                text=True, cwd=target, check=True, timeout=10)
            subprocess.run(['git', 'apply', '-'], input=patch,
                text=True, cwd=target, check=True, timeout=10)
            for name, data in changed.items():
                self.assertEqual((target / name).read_text(), data)

    def test_inert_cli(self):
        result = subprocess.run(['python3', str(HERE / 'render_patch.py'),
            '--readonly-cap-inventory'], capture_output=True, text=True,
            check=True, timeout=10)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['state'], 'inert')
        self.assertIs(receipt['gpuCalls'], False)
        self.assertIs(receipt['coreBuilt'], False)
        self.assertIs(receipt['readonlyCapInventory'], True)


if __name__ == '__main__':
    unittest.main()
