import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import r580_firmware_preload as preload


class FirmwarePreloadSafetyTest(unittest.TestCase):
    def test_only_two_firmwares_cached_image_no_gpu_or_api_credential(self):
        value = preload.proposal()
        spec = value['spec']['template']['spec']
        container = spec['containers'][0]
        self.assertEqual(spec['nodeName'], 'k3s-wk-gpu2')
        self.assertFalse(spec['automountServiceAccountToken'])
        self.assertNotIn('hostPID', spec)
        self.assertNotIn('hostNetwork', spec)
        self.assertEqual(container['imagePullPolicy'], 'Never')
        self.assertEqual(container['image'], preload.IMAGE)
        self.assertIn({'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'void'}, container['env'])
        self.assertFalse(container['securityContext']['privileged'])
        self.assertEqual(container['securityContext']['capabilities'], {'drop': ['ALL']})
        self.assertEqual([v['hostPath']['path'] for v in spec['volumes'] if 'hostPath' in v], [preload.FIRMWARE])
        self.assertTrue(all('gpu' not in key.lower() and 'nvidia' not in key.lower()
                            for values in container['resources'].values() for key in values))
        self.assertIn('set -euo pipefail', container['args'][0])
        self.assertIn('--extract-decompress', container['args'][0])
        self.assertIn('tail -n +1019', container['args'][0])
        self.assertIn('--no-same-owner --no-same-permissions', container['args'][0])
        self.assertIn('firmware/gsp_tu10x.bin firmware/gsp_ga10x.bin', container['args'][0])
        self.assertNotIn('--extract-only --target', container['args'][0])
        self.assertEqual(container['command'], ['/bin/bash', '-ec'])
        self.assertIn('for name in gsp_tu10x.bin gsp_ga10x.bin;', container['args'][0])
        self.assertNotIn('modprobe', container['args'][0])
        self.assertNotIn('systemctl', container['args'][0])
        self.assertNotIn('nvidia-smi', container['args'][0])
        self.assertNotIn('cdi', container['args'][0])


@unittest.skipUnless(shutil.which('zstd'), 'local zstd needed for bounded fake archive')
class FirmwareCopyBehaviorTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.owned = self.root / 'owned'
        self.owned.mkdir()
        tar_bytes = io.BytesIO()
        with tarfile.open(fileobj=tar_bytes, mode='w') as archive:
            for name, data in [('firmware/gsp_tu10x.bin', b'tu10x-firmware'),
                               ('firmware/gsp_ga10x.bin', b'ga10x-firmware'),
                               ('nvidia-installer', b'not-executed'),
                               ('unrelated.bin', b'not-copied')]:
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        compressed = subprocess.check_output(['zstd', '-q', '-c'], input=tar_bytes.getvalue())
        decoder = self.root / 'decoder'
        decoder.write_text('#!/bin/sh\nexec "' + shutil.which('zstd') + '" "$@"\n')
        self.archive = self.root / 'driver.run'
        lines = ['#!/bin/sh', 'if [ "$1" = "--extract-decompress" ]; then cat "' + str(decoder) + '"; exit; fi',
                 'exit 99']
        lines += ['#'] * (1018 - len(lines))
        self.archive.write_bytes(('\n'.join(lines) + '\n').encode() + compressed)
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def run_copy(self, expected_digest=None):
        scratch = self.root / 'scratch'
        if scratch.exists():
            shutil.rmtree(scratch)
        scratch.mkdir()
        script = preload.SCRIPT.replace('/drivers/NVIDIA-Linux-x86_64-580.95.05.run', str(self.archive))
        script = script.replace('/scratch', str(scratch)).replace('/owned-firmware', str(self.owned))
        script = script.replace('849ef0ef8e842b9806b2cde9f11c1303d54f1a9a769467e4e5d961b2fe1182a7',
                                expected_digest or self.digest)
        return subprocess.run(['bash', '-ec', script], env={'PATH': '/usr/bin:/bin', 'POD_UID': 'fake-owned-pod'},
                              text=True, capture_output=True)

    def test_only_selected_files_and_existing_matches(self):
        first = self.run_copy()
        self.assertEqual(first.returncode, 0, first.stderr)
        files = sorted(str(path.relative_to(self.owned)) for path in self.owned.rglob('*') if path.is_file())
        self.assertEqual(files, ['nvidia/580.95.05/gsp_ga10x.bin', 'nvidia/580.95.05/gsp_tu10x.bin'])
        self.assertEqual((self.owned / files[0]).read_bytes(), b'ga10x-firmware')
        second = self.run_copy()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout.count('EXISTING_MATCH'), 2)

    def test_different_existing_bytes_are_not_overwritten(self):
        target = self.owned / 'nvidia/580.95.05/gsp_tu10x.bin'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'protected-different-data')
        failed = self.run_copy()
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(target.read_bytes(), b'protected-different-data')

    def test_archive_mismatch_rejected_before_destination_writes(self):
        failed = self.run_copy('0' * 64)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(list(self.owned.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
