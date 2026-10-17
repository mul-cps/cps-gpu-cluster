import array,os,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import vmm_bridge as b
import vmm_endpoint as e
class BridgeTests(unittest.TestCase):
 def setUp(self):
  self.pin=patch.object(b,'PODS',frozenset({'4010edf4-f407-409b-aa4c-de0615e8c05c','879a4589-faee-4569-bdb8-f2e7c154ef19'}));self.pin.start();self.addCleanup(self.pin.stop)
 def test_closed_source_scoped_requests(self):
  request={'trial_id':'e9c5edb3-8474-4f7d-8ca2-20a6d7f4d562','transfer':'cross','exporter':{'role':'exporter','expect':'allow','namespace_pid':1,'identity':{'pod_uid':'4010edf4-f407-409b-aa4c-de0615e8c05c','driver_generation':b.GENERATION}},'importer':{'role':'importer','expect':'deny','namespace_pid':2,'identity':{'pod_uid':'879a4589-faee-4569-bdb8-f2e7c154ef19','driver_generation':b.GENERATION}}}
  b.validate_request(request)
  for value in [{**request,'node':'foreign'},{**request,'transfer':'unknown'},{**request,'importer':{**request['importer'],'expect':'allow'}},{**request,'exporter':{**request['exporter'],'identity':{**request['exporter']['identity'],'pod_uid':'other'}}}]:
   with self.subTest(value=value),self.assertRaises(ValueError):b.validate_request(value)
 def test_exact_peer_and_lifetime(self):
  conn=Mock();conn.getsockopt.return_value=array.array('i',[123,1000,100]).tobytes();b.verify_peer(conn,{'host_tgid':123})
  for fields in [[124,1000,100],[123,0,0],[123,1000,1000]]:
   conn.getsockopt.return_value=array.array('i',fields).tobytes()
   with self.assertRaises(ValueError):b.verify_peer(conn,{'host_tgid':123})
 def test_descriptor_identity_mismatch_fails_before_forward(self):
  exporter=Mock();importer=Mock();frame={'phase':'exported-fd','trial_id':'x','transfer':'cross','backing_bytes':67108864,'fd_identity':{'bad':1}}
  with patch.object(e,'receive_frame',return_value=(frame,33)),patch.object(e,'send_frame') as send,patch.object(e,'fd_identity',return_value={'different':2}),patch.object(b.os,'close') as close:
   with self.assertRaises(ValueError):b.forward(e,exporter,importer,'x','cross','source')
   self.assertFalse(any(call.args[0] is importer for call in send.call_args_list));close.assert_called_once_with(33)
 def test_exact_one_right_forward_and_ack(self):
  exporter=Mock();importer=Mock();ident={'device':1,'inode':2,'mode':3,'rdev':0};frame={'phase':'exported-fd','trial_id':'x','transfer':'cross','backing_bytes':67108864,'fd_identity':ident};ack={'phase':'fd-received','trial_id':'x','transfer':'cross','fd_identity':ident}
  with patch.object(e,'receive_frame',side_effect=[(frame,33),(ack,None)]),patch.object(e,'send_frame') as send,patch.object(e,'fd_identity',return_value=ident),patch.object(b.os,'close') as close:
   self.assertEqual(b.forward(e,exporter,importer,'x','cross','source'),ident)
   rights=[c for c in send.call_args_list if len(c.args)==3];self.assertEqual(len(rights),1);self.assertIs(rights[0].args[0],importer);self.assertEqual(rights[0].args[2],33);close.assert_called_once_with(33)
 def test_no_root_cuda_or_namespace_mutation(self):
  source=Path(b.__file__).read_text();self.assertNotIn('setns(',source);self.assertNotIn('nsenter',source);self.assertNotIn('VmmCuda(',source)
  with patch('builtins.print') as out:b.main([])
  self.assertIn('inert',out.call_args.args[0])
if __name__=='__main__':unittest.main()

class ActualMappingTests(unittest.TestCase):
 def fixture(self,directory):
  import hashlib,json,uuid
  root=Path(directory);proc=root/'proc';cg=root/'cg';proc.mkdir();cg.mkdir();trial='e9c5edb3-8474-4f7d-8ca2-20a6d7f4d562'
  relative='/kubepods.slice/kubepods-podtest.slice';parent=cg/relative.lstrip('/');parent.mkdir(parents=True);info=parent.stat()
  ident={'cgroup_relative':relative,'cgroup_path':'/sys/fs/cgroup'+relative,'cgroup_device':info.st_dev,'cgroup_inode':info.st_ino,'boot_id':b.BOOT,'gpu_uuid':b.GPU,'pod_uid':'879a4589-faee-4569-bdb8-f2e7c154ef19','driver_generation':b.GENERATION}
  item=proc/'900';item.mkdir();(item/'ns').mkdir();(item/'ns/pid').touch();(item/'ns/net').touch()
  (item/'cgroup').write_text('0::'+relative+'/container.scope\n');(item/'status').write_text('Tgid:\t900\nUid:\t1000\t1000\t1000\t1000\nGid:\t100\t100\t100\t100\nNSpid:\t900\t20\n')
  (item/'stat').write_text('900 (python odd) '+' '.join(['S',*(['0']*18),'123456','0']))
  raw=b'closed CPU source';sha=hashlib.sha256(raw).hexdigest();source=Path('/tmp')/('cpv-'+uuid.UUID(trial).hex[:16]+'-importer-src')/'vmm_endpoint.py'
  actual=item/'root'/str(source).lstrip('/');actual.parent.mkdir(parents=True,mode=0o700);actual.write_bytes(raw);actual.chmod(0o600)
  (item/'cmdline').write_bytes(b'\0'.join([b'python',str(source).encode(),b'--trial-id',trial.encode(),b'--role',b'importer',b'--gpu-uuid',b.GPU.encode(),b'--expect',b'deny',b'--source-sha256',sha.encode(),b'--expected-pod-uid',ident['pod_uid'].encode()])+b'\0')
  row={'cgroup_id':info.st_ino,'kernfs_id':info.st_ino,'inode':info.st_ino,'offline':False,'pinned':True,'default_hierarchy':True,'soft':5368709120,'hard':5368709120,'used':134217728}
  inv=proc/'driver/nvidia/gpus/0000:06:10.0/cps_native_caps';inv.parent.mkdir(parents=True);inv.write_text(json.dumps({'version':1,'backend':'misc-fallback','gpu_uuid':b.GPU,'gpu_id':1552,'entries':[row]}))
  req={'trial_id':trial,'namespace_pid':20,'identity':ident,'role':'importer','expect':'deny','source_sha256':sha};return proc,cg,req,item,actual,inv
 def test_actual_pid_cgroup_source_and_gpu_mapping(self):
  with tempfile.TemporaryDirectory()as tmp:
   proc,cg,req,item,source,inv=self.fixture(tmp);result=b.observe(req,proc,cg)
   self.assertEqual(result['host_tgid'],900);self.assertEqual(result['pid_start_ticks'],123456);self.assertEqual(result['gpu_id'],1552);self.assertEqual(result['source_sha256'],req['source_sha256']);self.assertEqual(result['network_namespace_inode'],(item/'ns/net').stat().st_ino)
 def test_source_pid_parent_role_and_cap_forgery_rejected(self):
  import json
  for fault in ['source','path','trial','uid','thread','parent','role','expectedpod','namespace','finite','pinned','duplicate']:
   with self.subTest(fault=fault),tempfile.TemporaryDirectory()as tmp:
    proc,cg,req,item,source,inv=self.fixture(tmp)
    if fault=='source':source.write_bytes(b'changed')
    elif fault=='path':(item/'cmdline').write_bytes((item/'cmdline').read_bytes().replace(str(e.source_path(req['trial_id'],'importer')).encode(),b'/tmp/other.py'))
    elif fault=='trial':(item/'cmdline').write_bytes((item/'cmdline').read_bytes().replace(req['trial_id'].encode(),b'foreign'))
    elif fault=='uid':(item/'status').write_text((item/'status').read_text().replace('1000','0'))
    elif fault=='thread':(item/'status').write_text((item/'status').read_text().replace('Tgid:\t900','Tgid:\t899'))
    elif fault=='parent':req['identity']['cgroup_inode']+=1
    elif fault=='role':req['role']='positive'
    elif fault=='expectedpod':req['identity']['pod_uid']='4010edf4-f407-409b-aa4c-de0615e8c05c'
    elif fault=='namespace':req['namespace_pid']=21
    else:
     value=json.loads(inv.read_text())
     if fault=='finite':value['entries'][0]['soft']=2**64-1
     elif fault=='pinned':value['entries'][0]['pinned']=False
     else:value['entries'].append(value['entries'][0].copy())
     inv.write_text(json.dumps(value))
    with self.assertRaises(ValueError):b.observe(req,proc,cg)
 def test_real_local_rights_bridge_uses_exact_one_fd(self):
  import threading
  a,x=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET);y,d=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
  for sock in [a,x,y,d]:sock.settimeout(2)
  errors=[];seen=[]
  with a,x,y,d,tempfile.TemporaryFile()as f:
   ident=e.fd_identity(f.fileno());frame={'phase':'exported-fd','trial_id':'trial','transfer':'cross','backing_bytes':67108864,'fd_identity':ident}
   def export():
    try:request,_=e.receive_frame(a);e.send_frame(a,frame,f.fileno());e.receive_frame(a)
    except BaseException as error:errors.append(error)
   def receive():
    fd=None
    try:
     value,fd=e.receive_frame(d,want_fd=True);seen.append(e.fd_identity(fd));e.send_frame(d,{'phase':'fd-received','trial_id':'trial','transfer':'cross','fd_identity':seen[-1]})
    except BaseException as error:errors.append(error)
    finally:
     if fd is not None:os.close(fd)
   threads=[threading.Thread(target=target)for target in [export,receive]]
   for t in threads:t.start()
   self.assertEqual(b.forward(e,x,y,'trial','cross','source'),ident)
   for t in threads:t.join(3);self.assertFalse(t.is_alive())
   self.assertEqual(errors,[]);self.assertEqual(seen,[ident])
