import importlib.util,pathlib,tempfile,unittest,json
D=pathlib.Path(__file__).parent
sp=importlib.util.spec_from_file_location('runner',D/'regenerate_selected.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Guards(unittest.TestCase):
 def test_space_includes_original_backup_and_new_image(self):
  x=m.space_requirements(100,200);self.assertGreaterEqual(x['boot'],300);self.assertGreaterEqual(x['state'],300)
 def test_insufficient_space_refused(self):
  with self.assertRaises(ValueError):m.check_space(100,200,299,1000000000)
 def test_same_filesystem_must_cover_combined_budget(self):
  need=m.space_requirements(100,200);free=max(need.values())
  with self.assertRaises(ValueError):m.check_space(100,200,free,free,same_fs=True)
  m.check_space(100,200,sum(need.values()),sum(need.values()),same_fs=True)
 def test_exact_shutdown_waiter_is_not_package_operation(self):
  self.assertFalse(m.package_operation(['python3','/usr/share/unattended-upgrades/unattended-upgrade-shutdown','--wait-for-signal']))
  self.assertTrue(m.package_operation(['/usr/bin/unattended-upgrade']))
  self.assertTrue(m.package_operation(['/usr/bin/apt-get','upgrade']))
  self.assertTrue(m.package_operation(['/usr/sbin/update-initramfs','-u']))
 def test_embedded_option_exact(self):
  with tempfile.TemporaryDirectory()as td:
   p=pathlib.Path(td)/'main/etc/modprobe.d/90-cps-nfs-directory-delegations.conf';p.parent.mkdir(parents=True);p.write_bytes(m.LINE)
   self.assertEqual(len(m.verify_embedded(pathlib.Path(td))),1)
   p.write_bytes(b'options nfsv4 directory_delegations=Y\n')
   with self.assertRaises(ValueError):m.verify_embedded(pathlib.Path(td))
 def test_embedded_symlink_or_missing_refused(self):
  with tempfile.TemporaryDirectory()as td:
   root=pathlib.Path(td)
   with self.assertRaises(ValueError):m.verify_embedded(root)
   p=root/'main/etc/modprobe.d/90-cps-nfs-directory-delegations.conf';p.parent.mkdir(parents=True);p.symlink_to('/etc/passwd')
   with self.assertRaises(ValueError):m.verify_embedded(root)
 def test_unarmed_rejected_before_mutation(self):
  with self.assertRaises(ValueError):m.validate_release({'root_release':None})
if __name__=='__main__':unittest.main()
