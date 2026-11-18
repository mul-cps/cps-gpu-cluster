import base64,copy,importlib.util,json,os,pathlib,tempfile,unittest,uuid
from unittest.mock import patch

HERE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('nfscompat',HERE/'nfs_client_compat.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Compat(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  for d in ['etc/modprobe.d','var/lib','proc/sys/kernel/random','sys/module/nfsv4/parameters','boot']:(self.root/d).mkdir(parents=True,exist_ok=True)
  (self.root/'proc/sys/kernel/random/boot_id').write_text('11111111-1111-4111-8111-111111111111')
  (self.root/'proc/cmdline').write_text('quiet splash')
  (self.root/'sys/module/nfsv4/parameters/directory_delegations').write_text('N')
  (self.root/'boot/initrd.img-7.0.0-43-generic').write_bytes(b'fixture-not-a-real-initramfs')
  self.observed={'hostname':'k3s-wk-gpu1','kernel':'7.0.0-43-generic'}
  self.node={'metadata':{'name':'k3s-wk-gpu1','uid':'22222222-2222-4222-8222-222222222222'},'status':{'nodeInfo':{'bootID':'11111111-1111-4111-8111-111111111111','kernelVersion':'7.0.0-43-generic','osImage':'Ubuntu 26.04.1 LTS'},'conditions':[{'type':'Ready','status':'True'}]}}
  self.selection={'node':'k3s-wk-gpu1','node_uid':self.node['metadata']['uid'],'boot_id':self.node['status']['nodeInfo']['bootID'],'kernel':'7.0.0-43-generic','root_release':'Root test-only release','operation_id':'33333333-3333-4333-8333-333333333333','canary_sha256':'a'*64,'peer_sha256':'b'*64,'expected_preimage':{'exists':False}}
  self.calls=[];self.extra='';self.initrd='usr/lib/modules/7.0.0-43-generic/kernel/fs/nfs/nfsv4.ko.zst\n';self.fail_after=False
 def tearDown(self):self.tmp.cleanup()
 def command(self,args):
  self.calls.append(args)
  if args[0]=='modprobe':
   p=self.root/'etc/modprobe.d/90-cps-nfs-directory-delegations.conf'
   if self.fail_after and p.exists():return 'options nfsv4 directory_delegations=Y\n'
   return self.extra+(p.read_text()if p.exists()else'')
  if args[0]=='modinfo':return '/lib/modules/7.0.0-43-generic/kernel/fs/nfs/nfsv4.ko.zst\n'
  if args[0]=='lsinitramfs':return self.initrd
  self.fail('Unexpected command '+repr(args))
 def persist(self):return m.persist(self.root,self.selection,lambda:self.node,self.observed,self.command)
 def target(self):return self.root/'etc/modprobe.d/90-cps-nfs-directory-delegations.conf'
 def test_new_backup_directories_durable_before_target_replacement(self):
  events=[];sync=os.fsync;replace=os.replace
  def synced(fd):
   events.append(('fsync',pathlib.Path(os.readlink('/proc/self/fd/'+str(fd)))));return sync(fd)
  def replaced(source,target):
   events.append(('replace',pathlib.Path(target)));return replace(source,target)
  with patch.object(m.os,'fsync',side_effect=synced),patch.object(m.os,'replace',side_effect=replaced):self.persist()
  changed=events.index(('replace',self.target()))
  parent=events.index(('fsync',self.root/'var/lib'))
  state=events.index(('fsync',self.root/m.STATE))
  self.assertLess(parent,state);self.assertLess(state,changed)
 def assert_parent_sync_failure_blocks_target(self,failure):
  sync=os.fsync
  def fail(fd):
   if pathlib.Path(os.readlink('/proc/self/fd/'+str(fd)))==failure:raise OSError('synthetic parent fsync failure')
   return sync(fd)
  with patch.object(m.os,'fsync',side_effect=fail):
   with self.assertRaisesRegex(OSError,'parent fsync'):self.persist()
  self.assertFalse(self.target().exists())
 def test_state_parent_fsync_failure_prevents_target_write(self):
  self.assert_parent_sync_failure_blocks_target(self.root/'var/lib')
 def test_operation_parent_fsync_failure_prevents_target_write(self):
  self.assert_parent_sync_failure_blocks_target(self.root/m.STATE)
 def test_inspection_never_writes_and_reports_initramfs_gate(self):
  before=sorted(str(p.relative_to(self.root))for p in self.root.rglob('*'))
  r=m.inspect_host(self.root,self.observed,self.command)
  self.assertEqual(r['runtime_value'],'N');self.assertTrue(r['initramfs']['nfsv4_module_present']);self.assertFalse(r['initramfs']['config_entry_present'])
  self.assertEqual(before,sorted(str(p.relative_to(self.root))for p in self.root.rglob('*')))
 def test_unarmed_release_fails_before_commands_or_files(self):
  self.selection['root_release']=None
  with self.assertRaises(ValueError):self.persist()
  self.assertEqual(self.calls,[]);self.assertFalse(self.target().exists())
 def test_stale_node_boot_kernel_refused_without_write(self):
  for key,value in [('node_uid',str(uuid.uuid4())),('boot_id',str(uuid.uuid4())),('kernel','7.0.0-other')]:
   old=self.selection[key];self.selection[key]=value
   with self.assertRaises(ValueError):self.persist()
   self.assertFalse(self.target().exists());self.selection[key]=old
 def test_supported_runtime_canary_required_and_conflicts_refused(self):
  p=self.root/'sys/module/nfsv4/parameters/directory_delegations';p.write_text('Y')
  with self.assertRaisesRegex(ValueError,'canary'):self.persist()
  p.write_text('N');self.extra='options nfsv4 directory_delegations=Y\n'
  with self.assertRaisesRegex(ValueError,'conflict'):self.persist()
  self.assertFalse(self.target().exists())
 def test_atomic_config_preimage_exact_and_no_regen_reload(self):
  original=b'# Existing operator notes\noptions nfs nfs4_disable_idmapping=0\n';self.target().write_bytes(original);self.target().chmod(0o640)
  self.selection['expected_preimage']=m.preimage(self.target())
  r=self.persist();self.assertTrue(self.target().read_bytes().startswith(original));self.assertIn(b'options nfsv4 directory_delegations=N',self.target().read_bytes());self.assertEqual(self.target().stat().st_mode&0o777,0o640)
  backup=json.loads((self.root/'var/lib/cps-nfs-client-compat'/self.selection['operation_id']/'preimage.json').read_text());self.assertEqual(base64.b64decode(backup['content_base64']),original)
  self.assertTrue(r['effective_option_verified']);self.assertFalse(r['initramfs_regenerated']);self.assertFalse(r['runtime_parameter_written']);self.assertTrue(r['initramfs']['refresh_required_before_boot_qualification'])
  self.assertFalse(any(a[0]in['update-initramfs','systemctl','reboot','rmmod']or'-r'in a for a in self.calls))
 def test_prior_file_replacement_and_symlink_refused(self):
  self.target().write_text('# other writer\n')
  with self.assertRaisesRegex(ValueError,'preimage'):self.persist()
  self.target().unlink();self.target().symlink_to(self.root/'proc/cmdline')
  with self.assertRaises(ValueError):self.persist()
 def test_existing_operation_prevents_blind_replay(self):
  self.persist();self.selection['expected_preimage']=m.preimage(self.target())
  with self.assertRaisesRegex(ValueError,'reconcile'):self.persist()
 def test_failure_after_replace_retains_backup_and_unknown_not_success(self):
  self.fail_after=True
  with self.assertRaises(ValueError):self.persist()
  state=json.loads((self.root/'var/lib/cps-nfs-client-compat'/self.selection['operation_id']/'operation.json').read_text());self.assertEqual(state['status'],'HOLD-reconcile');self.assertTrue(self.target().exists())
 def test_no_initramfs_module_needs_no_regeneration(self):
  self.initrd='usr/bin/sh\n';r=self.persist();self.assertFalse(r['initramfs']['refresh_required_before_boot_qualification']);self.assertFalse(r['coldboot_qualified'])
 def test_alias_and_hyphen_options_and_kernel_commandline_cannot_override(self):
  for extra in ['options fs-nfs4 directory_delegations=Y\n','options nfsv4 directory-delegations=Y\n']:
   self.extra=extra
   with self.assertRaisesRegex(ValueError,'conflict'):self.persist()
  self.extra='';(self.root/'proc/cmdline').write_text('quiet nfsv4.directory-delegations=Y')
  with self.assertRaisesRegex(ValueError,'conflict'):self.persist()
  self.assertFalse(self.target().exists())
 def test_node_replacement_after_write_holds_without_claimed_acceptance(self):
  calls=[0]
  def reader():
   calls[0]+=1;n=copy.deepcopy(self.node)
   if calls[0]>=3:n['metadata']['uid']=str(uuid.uuid4())
   return n
  with self.assertRaisesRegex(ValueError,'UID'):m.persist(self.root,self.selection,reader,self.observed,self.command)
  state=json.loads((self.root/'var/lib/cps-nfs-client-compat'/self.selection['operation_id']/'operation.json').read_text());self.assertEqual(state['status'],'HOLD-reconcile');self.assertTrue(state['config_file_written']);self.assertFalse(state['coldboot_qualified'])

if __name__=='__main__':unittest.main()
