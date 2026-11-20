import hashlib
import tempfile
import unittest
from pathlib import Path
import build_candidate as build


class BuildSafetyTests(unittest.TestCase):
    def test_crc_digest_ignores_readelf_ascii_and_offsets(self):
        raw='\n  0x00000000 01020304 aabbccdd 11223344 55667788 ....test\n  0x00000010 ffffffff 00000000 ........\n  0x00000018 00                                  .\n'
        wanted=hashlib.sha256(b'01020304aabbccdd1122334455667788ffffffff0000000000').hexdigest()
        self.assertEqual(build.versions_digest(raw),wanted)
        with self.assertRaises(ValueError):build.versions_digest('No such section')

    def test_copy_refuses_external_symlink_and_size_excess(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'source';root.mkdir();(root/'file').write_bytes(b'ab')
            self.assertEqual(build.source_inventory(root,max_bytes=2)['bytes'],2)
            with self.assertRaises(ValueError):build.source_inventory(root,max_bytes=1)
            (root/'escape').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):build.source_inventory(root)

    def test_command_is_modules_only_with_cpu_bound(self):
        command=build.make_command(Path('/headers'),2)
        self.assertIn('NV_KERNEL_MODULES=nvidia nvidia-uvm',command)
        self.assertEqual(command[-1],'modules')
        self.assertNotIn('modules_install',command)
        with self.assertRaises(ValueError):build.make_command(Path('/headers'),3)

    def test_fresh_owned_output_cannot_overlap_installed_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'source';root.mkdir()
            with self.assertRaises(ValueError):build.validate_output(root/'child',root)
            with self.assertRaises(ValueError):build.validate_output(root,root)
            with self.assertRaises(ValueError):build.validate_output(root.parent,root)
            build.validate_output(root.parent/'cps-r615-uvm-guard-copy',root)


if __name__=='__main__':unittest.main()
