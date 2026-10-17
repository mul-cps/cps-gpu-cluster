import copy,json,os,stat,tempfile,types,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import vmm_endpoint as endpoint
import run_vmm_cross_parent as wrapper

class DirectoryTests(unittest.TestCase):
 def test_socket_dir_removes_inherited_setgid_only_on_fresh_dir(self):
  with tempfile.TemporaryDirectory() as raw:
   parent=Path(raw);parent.chmod(0o2700);path=parent/'fresh'/'s'
   with patch.object(endpoint,'socket_path',return_value=path):
    server,p=endpoint.listen(types.SimpleNamespace(trial_id=str(uuid.uuid4()),role='positive'))
    try:self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode),0o700)
    finally:server.close();path.unlink()
    path.parent.chmod(0o2700)
    with self.assertRaises(FileExistsError):endpoint.listen(types.SimpleNamespace(trial_id='x',role='positive'))
    self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode),0o2700)
 def test_loader_normalizes_fresh_source_dir(self):
  prefix=wrapper.LOADER.split("path=directory+'/vmm_endpoint.py'")[0]
  with tempfile.TemporaryDirectory() as raw:
   parent=Path(raw);parent.chmod(0o2700)
   prefix=prefix.replace("'/tmp/cpv-'",repr(str(parent)+'/cpv-'))
   source=b'x';trial=str(uuid.uuid4());chunks=[b'1',b'\n',source]
   argv=['loader','--trial-id',trial,'--role','positive','--source-sha256',__import__('hashlib').sha256(source).hexdigest()]
   with patch('os.read',side_effect=chunks),patch('sys.argv',argv):exec(prefix,{})
   self.assertEqual(stat.S_IMODE(next(parent.iterdir()).stat().st_mode),0o700)

class ManifestTests(unittest.TestCase):
 def fixture(self):
  import current_preflight as p
  return {'pods':{k:dict(namespace='jupyterhub',name='jupyter-'+k,uid=str(uuid.uuid4()),cap_mib=5120)for k in ('a','b')},
    'node':dict(namespace='cps-native-system',name='node-agent',uid=str(uuid.uuid4())),
    'observer':dict(namespace='gpu-operator',name='cps-native-driver-control',uid=str(uuid.uuid4()))}
 def test_closed_current_pair_and_duplicate_rejection(self):
  import current_preflight as p
  value=self.fixture();self.assertEqual(p.validate_targets(value),value)
  for change in ('duplicate','foreign','extra','wrongcap'):
   bad=copy.deepcopy(value)
   if change=='duplicate':bad['pods']['b']=dict(bad['pods']['a'])
   if change=='foreign':bad['pods']['a']['namespace']='cit-jhub'
   if change=='extra':bad['pods']['a']['image']='untrusted'
   if change=='wrongcap':bad['pods']['a']['cap_mib']=2048
   with self.subTest(change=change),self.assertRaises(ValueError):p.validate_targets(bad)
 def test_packaged_node_pins_and_no_nvml_setter(self):
  import current_preflight as p
  self.assertIn('CapRecord.from_dict',p.NODE_READ)
  self.assertIn('record.receipt()',p.NODE_READ)
  self.assertNotIn('driver.set(',p.NODE_READ)
  self.assertIn('6083e06a',p.NODE_IMAGE)
 def test_default_inert_no_target_reads(self):
  with patch('pathlib.Path.read_bytes',side_effect=AssertionError('I/O')),patch('builtins.print'):
   wrapper.main([])

class FreshReadTests(unittest.TestCase):
 def test_actual_preflight_reads_all_pods_again_and_rejects_drift(self):
  import current_preflight as p
  manifest=ManifestTests().fixture();actual={}
  for lane,row in [*manifest['pods'].items(),('node',manifest['node']),('observer',manifest['observer'])]:
   container='notebook'if lane in ('a','b')else 'node-agent'if lane=='node'else 'control'
   image=p.NOTEBOOK_IMAGE if container=='notebook'else p.NODE_IMAGE if container=='node-agent'else 'trusted-observer@sha256:'+'a'*64
   actual[row['name']]={'metadata':dict(uid=row['uid'],name=row['name'],namespace=row['namespace']),
    'spec':dict(nodeName='k3s-wk-gpu2',hostPID=lane=='observer',containers=[dict(name=container,image=image)]),
    'status':dict(phase='Running',containerStatuses=[dict(name=container,imageID=image,ready=True,restartCount=0,state={'running':{}})])}
  rows=[dict(pod_uid=manifest['pods'][k]['uid'],identity={'cgroup_inode':i})for i,k in enumerate(('a','b'),1)]
  calls=[]
  def get(row):calls.append(row['name']);return copy.deepcopy(actual[row['name']])
  with patch.object(p,'pod',side_effect=get),patch.object(p,'command',return_value=rows)as observed:
   self.assertEqual(p.preflight({'manifest':manifest})['host']['targets'],rows)
  self.assertEqual(json.loads(observed.call_args.args[1]),[actual[manifest['pods'][k]['name']]for k in ('a','b')])
  self.assertIn(p.NODE_READ,observed.call_args.args[0])
  self.assertLess(len(str(observed.call_args.args[0])),4096)
  self.assertEqual(len(calls),8)
  calls.clear()
  def changed(row):
   result=get(row)
   if len(calls)==5:result['status']['containerStatuses'][0]['restartCount']=1
   return result
  with patch.object(p,'pod',side_effect=changed),patch.object(p,'command',return_value=rows),self.assertRaises(ValueError):p.preflight({'manifest':manifest})
 def test_manifest_file_sha_and_permissions_required(self):
  import current_preflight as p,hashlib
  with tempfile.TemporaryDirectory()as raw:
   path=Path(raw)/'targets.json';path.write_text(json.dumps(ManifestTests().fixture()));path.chmod(0o600)
   sha=hashlib.sha256(path.read_bytes()).hexdigest();self.assertEqual(p.read_targets(path,sha)['pods'].keys(),{'a','b'})
   with self.assertRaises(ValueError):p.read_targets(path,'0'*64)
   path.chmod(0o644)
   with self.assertRaises(ValueError):p.read_targets(path,sha)
