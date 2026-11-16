"""Offline selected-worker guards and real filesystem rollback; no host writes."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'platform-staging/gpu/upstream-sharing/apparmor-compat/install_selected_worker.py'
POLICY = SOURCE.parent


class SelectedAppArmorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.available = SOURCE.exists()
        if cls.available:
            spec = importlib.util.spec_from_file_location('selected_apparmor', SOURCE)
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def setUp(self):
        self.assertTrue(self.available, 'selected-worker AppArmor helper not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.selection = {'node': 'k3s-wk-gpu3', 'node_uid': '00000000-0000-4000-8000-000000000003',
            'ip': '10.21.0.44', 'expected_boot': '00000000-0000-4000-8000-000000000004',
            'expected_kernel': '7.0.0-fixture', 'expected_os_version': '26.04',
            'k3s_version': 'v1.34.9+k3s1', 'containerd_version': 'v2.2.5-k3s2',
            'parent_release': 'offline-preparation-only',
            'profile_sha256': '30e2fc1210fc99c4e7060ea6bf7f931f6d6c03fbdc499f5f0584fb5c01c92875'}
        self.node = {'metadata': {'name': self.selection['node'], 'uid': self.selection['node_uid'], 'labels': {}},
            'spec': {'unschedulable': True, 'taints': [{'key': 'cps.unileoben.ac.at/maintenance',
                'value': 'upstream-pilot', 'effect': 'NoSchedule'}]},
            'status': {'addresses': [{'type': 'InternalIP', 'address': '10.21.0.44'}],
                'nodeInfo': {'bootID': self.selection['expected_boot'], 'kernelVersion': '7.0.0-fixture',
                    'kubeletVersion': 'v1.34.9+k3s1', 'containerRuntimeVersion': 'containerd://2.2.5-k3s2'}}}

    def payload(self):
        return self.module.prepare_payload(self.selection, self.node, 'offline-preparation-only')

    def test_preparation_preserves_exact_historical_policy(self):
        payload = self.payload()
        self.assertEqual(payload['baseline'].encode(), (POLICY/'baseline.profile').read_bytes())
        self.assertEqual(payload['profile'].encode(), (POLICY/'cri-containerd.apparmor.d').read_bytes())
        self.assertEqual(payload['selection'], self.selection)
        compile(self.module.render_remote(), '<reviewed-remote>', 'exec')

    def test_wrong_selected_identity_boot_or_version_rejected(self):
        for path, value in [('metadata.name', 'k3s-wk-gpu4'), ('metadata.uid', 'replaced'),
                            ('status.nodeInfo.bootID', 'new-boot'), ('status.nodeInfo.kernelVersion', 'other'),
                            ('status.nodeInfo.kubeletVersion', 'v1.35.0'),
                            ('status.nodeInfo.containerRuntimeVersion', 'containerd://other')]:
            with self.subTest(path=path):
                node = copy.deepcopy(self.node); obj = node
                parts = path.split('.')
                for part in parts[:-1]:obj = obj[part]
                obj[parts[-1]] = value
                with self.assertRaises(ValueError):self.module.prepare_payload(self.selection, node, 'offline-preparation-only')
        self.node['status']['addresses'][0]['address'] = '10.21.0.99'
        with self.assertRaises(ValueError):self.payload()

    def test_missing_fence_qualified_label_or_wrong_release_rejected(self):
        for change in ['uncordoned', 'taint', 'qualified']:
            node = copy.deepcopy(self.node)
            if change == 'uncordoned':node['spec']['unschedulable'] = False
            if change == 'taint':node['spec']['taints'] = []
            if change == 'qualified':node['metadata']['labels']['cps.unileoben.ac.at/upstream-gpu-sharing'] = 'qualified'
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.module.prepare_payload(self.selection, node, 'offline-preparation-only')
        with self.assertRaises(ValueError):self.module.prepare_payload(self.selection, self.node, 'different-parent-release')

    def test_current_source_profile_and_baseline_are_pinned(self):
        self.selection['profile_sha256'] = '0'*64
        with self.assertRaises(ValueError):self.payload()
        with patch.object(self.module, 'ROOT', self.root):
            (self.root/'baseline.profile').write_text('unknown baseline')
            (self.root/'cri-containerd.apparmor.d').write_bytes((POLICY/'cri-containerd.apparmor.d').read_bytes())
            self.selection['profile_sha256'] = '30e2fc1210fc99c4e7060ea6bf7f931f6d6c03fbdc499f5f0584fb5c01c92875'
            with self.assertRaises(ValueError):self.payload()

    def test_source_byte_hash_does_not_normalize_changed_line_endings(self):
        (self.root/'baseline.profile').write_bytes((POLICY/'baseline.profile').read_bytes())
        (self.root/'cri-containerd.apparmor.d').write_bytes((POLICY/'cri-containerd.apparmor.d').read_bytes().replace(b'\n',b'\r\n'))
        with patch.object(self.module,'ROOT',self.root), self.assertRaises(ValueError):self.payload()

    def host(self):
        payload = self.payload()
        files = {'etc/os-release': 'ID=ubuntu\nVERSION_ID="26.04"\n',
            'proc/sys/kernel/random/boot_id': self.selection['expected_boot'],
            'proc/sys/kernel/apparmor_restrict_unprivileged_unconfined': '1'}
        for name,data in files.items():
            p=self.root/name;p.parent.mkdir(parents=True, exist_ok=True);p.write_text(data)
        raw = self.root/'sys/kernel/security/apparmor/policy/profiles/cri-containerd.apparmor.d.1/raw_data'
        raw.parent.mkdir(parents=True);raw.write_bytes(b'fixture-stock-binary')
        (self.root/'etc/apparmor.d').mkdir(parents=True)
        (self.root/'var/lib').mkdir(parents=True)
        observed={'hostname':'k3s-wk-gpu3','kernel':'7.0.0-fixture'}
        def command(args, **kwargs):
            data=b''
            if args == ['/usr/local/bin/k3s','--version']:data=b'k3s version v1.34.9+k3s1 (fixture)\n'
            elif args == ['/usr/local/bin/k3s','crictl','version']:data=b'RuntimeName: containerd\nRuntimeVersion: v2.2.5-k3s2\n'
            elif args[:2] == ['apparmor_parser','-S']:
                data=b'fixture-stock-binary' if kwargs['input']==payload['baseline'].encode() else b'fixture-candidate-binary'
            elif args[:2] == ['apparmor_parser','-r']:
                data_path=Path(args[-1]);raw.write_bytes(data_path.read_bytes() if '-B' in args else b'fixture-candidate-binary')
            elif args not in (['apparmor_parser','-Q','-K'],['systemctl','daemon-reload']):
                raise AssertionError('unexpected host command '+repr(args))
            return subprocess.CompletedProcess(args,0,stdout=data)
        return payload, observed, raw, command

    def install(self, payload, observed, command):
        with patch.object(self.module,'RAW_SHA256',hashlib.sha256(b'fixture-stock-binary').hexdigest()):
            return self.module.host_install(payload,self.root,observed,command)

    def test_host_and_boot_guard_run_before_any_policy_writes(self):
        payload,observed,raw,command=self.host()
        for host, boot in [('wrong-host',self.selection['expected_boot']),('k3s-wk-gpu3','rebooted')]:
            observed['hostname']=host;(self.root/'proc/sys/kernel/random/boot_id').write_text(boot)
            with self.assertRaises(ValueError):self.install(payload,observed,command)
            self.assertEqual(raw.read_bytes(),b'fixture-stock-binary')
            self.assertFalse((self.root/'var/lib/cps-apparmor-compat').exists())

    def test_unknown_loaded_or_different_compiled_baseline_never_replaced(self):
        payload,observed,raw,command=self.host()
        raw.write_bytes(b'unknown-policy')
        with self.assertRaises(ValueError):self.install(payload,observed,command)
        raw.write_bytes(b'fixture-stock-binary')
        def mismatched(args,**kwargs):
            result=command(args,**kwargs)
            if args[:2]==['apparmor_parser','-S']:result.stdout=b'different-compiled-policy'
            return result
        with self.assertRaises(ValueError):self.install(payload,observed,mismatched)
        self.assertFalse((self.root/'var/lib/cps-apparmor-compat').exists())

    def test_host_kernel_os_runtime_and_sysctl_mismatch_never_write(self):
        payload,observed,raw,command=self.host()
        for field in ['kernel','os','k3s','containerd','sysctl']:
            current=dict(observed)
            (self.root/'etc/os-release').write_text('ID=ubuntu\nVERSION_ID="26.04"\n')
            (self.root/'proc/sys/kernel/apparmor_restrict_unprivileged_unconfined').write_text('1')
            if field=='kernel':current['kernel']='other'
            if field=='os':(self.root/'etc/os-release').write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
            if field=='sysctl':(self.root/'proc/sys/kernel/apparmor_restrict_unprivileged_unconfined').write_text('0')
            def wrong(args,**kwargs):
                result=command(args,**kwargs)
                if field=='k3s' and args==['/usr/local/bin/k3s','--version']:result.stdout=b'k3s version v1.35.0\n'
                if field=='containerd' and args==['/usr/local/bin/k3s','crictl','version']:result.stdout=b'RuntimeVersion: other\n'
                return result
            with self.subTest(field=field), self.assertRaises(ValueError):self.install(payload,current,wrong)
            self.assertFalse((self.root/'var/lib/cps-apparmor-compat').exists())
            self.assertEqual(raw.read_bytes(),b'fixture-stock-binary')

    def test_unauthorized_ssh_key_rejected_without_opening_private_bytes(self):
        with self.assertRaises(ValueError):self.module.checked_key('/tmp/other-key')
        fake=type('Stat',(),{'st_mode':0o100644,'st_uid':os.getuid()})()
        with patch.object(Path,'lstat',return_value=fake), self.assertRaises(ValueError):
            self.module.checked_key('/home/bjoern/.ssh/id_ed25519')

    def test_one_time_install_backup_is_private_and_replay_rejected(self):
        payload,observed,raw,command=self.host()
        self.install(payload,observed,command)
        backup=self.root/'var/lib/cps-apparmor-compat'
        self.assertEqual((backup/'original.raw').read_bytes(),b'fixture-stock-binary')
        self.assertEqual(backup.stat().st_mode & 0o777,0o700)
        self.assertEqual((backup/'original.raw').stat().st_mode & 0o777,0o600)
        self.assertEqual(raw.read_bytes(),b'fixture-candidate-binary')
        with self.assertRaises((ValueError,FileExistsError)):self.install(payload,observed,command)

    def test_failure_after_load_restores_original_and_removes_only_created_files(self):
        payload,observed,raw,command=self.host();failed=False
        def fail_reload(args,**kwargs):
            nonlocal failed
            if args==['systemctl','daemon-reload'] and not failed:
                failed=True;raise subprocess.CalledProcessError(1,args)
            return command(args,**kwargs)
        with self.assertRaises(subprocess.CalledProcessError):self.install(payload,observed,fail_reload)
        self.assertEqual(raw.read_bytes(),b'fixture-stock-binary')
        self.assertFalse((self.root/'etc/apparmor.d/cri-containerd.apparmor.d').exists())
        self.assertFalse((self.root/'etc/systemd/system/k3s-agent.service.d/30-apparmor-compat.conf').exists())
        self.assertEqual((self.root/'var/lib/cps-apparmor-compat/original.raw').read_bytes(),b'fixture-stock-binary')

    def test_partial_file_write_failure_rolls_back_created_target(self):
        payload,observed,raw,command=self.host(); original=os.fsync
        target=self.root/'etc/apparmor.d/cri-containerd.apparmor.d'
        def disk_error(fd):
            if os.readlink('/proc/self/fd/'+str(fd))==str(target):raise OSError('fsync failed')
            return original(fd)
        with patch.object(self.module.os,'fsync',side_effect=disk_error):
            with self.assertRaises(OSError):self.install(payload,observed,command)
        self.assertFalse(target.exists())
        self.assertEqual(raw.read_bytes(),b'fixture-stock-binary')

    def test_protected_parent_symlink_rejected_before_backup(self):
        payload,observed,raw,command=self.host()
        parent=self.root/'etc/apparmor.d';parent.rmdir();elsewhere=self.root/'elsewhere';elsewhere.mkdir();parent.symlink_to(elsewhere)
        with self.assertRaises(ValueError):self.install(payload,observed,command)
        self.assertEqual(list(elsewhere.iterdir()),[])
        self.assertFalse((self.root/'var/lib/cps-apparmor-compat').exists())

    def test_failed_kernel_load_reinstates_original_before_unlink(self):
        payload,observed,raw,command=self.host()
        def failure(args,**kwargs):
            result=command(args,**kwargs)
            if args[:3]==['apparmor_parser','-r','-K']:raise subprocess.CalledProcessError(1,args)
            return result
        with self.assertRaises(subprocess.CalledProcessError):self.install(payload,observed,failure)
        self.assertEqual(raw.read_bytes(),b'fixture-stock-binary')
        self.assertFalse((self.root/'etc/apparmor.d/cri-containerd.apparmor.d').exists())

    def test_rollback_failure_preserves_backup_and_reports_incomplete(self):
        payload,observed,raw,command=self.host()
        def failure(args,**kwargs):
            if args[:3]==['apparmor_parser','-r','-B']:raise OSError('rollback unavailable')
            result=command(args,**kwargs)
            if args==['systemctl','daemon-reload']:raise OSError('daemon reload failed')
            return result
        with self.assertRaises(OSError):self.install(payload,observed,failure)
        self.assertTrue((self.root/'etc/apparmor.d/cri-containerd.apparmor.d').exists())
        backup=self.root/'var/lib/cps-apparmor-compat'
        self.assertEqual((backup/'original.raw').read_bytes(),b'fixture-stock-binary')
        self.assertIn('rollback-incomplete',json.loads((backup/'operation.json').read_text())['status'])

    def test_prepare_default_has_no_transport_or_host_command(self):
        selection=self.root/'selection.json';selection.write_text(json.dumps(self.selection))
        node=self.root/'node.json';node.write_text(json.dumps(self.node));output=self.root/'review.json'
        with patch.object(self.module,'checked_key',return_value=Path('/home/bjoern/.ssh/id_ed25519')), patch.object(self.module.subprocess,'run',side_effect=AssertionError('unexpected external command')), patch('sys.stdout',new_callable=io.StringIO):
            self.module.main(['--selection',str(selection),'--node-json',str(node),'--ssh-key','/home/bjoern/.ssh/id_ed25519','--parent-release','offline-preparation-only','--output',str(output)])
        self.assertFalse(json.loads(output.read_text())['apply'])
        self.assertEqual(output.stat().st_mode & 0o777,0o600)


if __name__=='__main__':unittest.main()
