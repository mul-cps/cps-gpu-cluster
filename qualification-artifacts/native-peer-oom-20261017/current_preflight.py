"""Read-only current packaged-node adapter. Import has no API/NVML operations."""
import hashlib,json,os,re,stat,subprocess,uuid
from pathlib import Path
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
BOOT='209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GENERATION='b10498fc-9153-4394-875a-ea7cfb498625'
NODE_IMAGE='ghcr.io/mul-cps/cps-native-node@sha256:47d8e532409337c864d02fc608600b4aecea650075573690b4f17dcb7a670c7f'
NOTEBOOK_IMAGE='ghcr.io/mul-cps/cps-jupyter-notebook:qualification-native-group-980408a@sha256:9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0'
OBSERVER_ARGV=[]
def require(ok,message):
 if not ok:raise ValueError(message)
def canonical_uuid(value):
 require(isinstance(value,str) and str(uuid.UUID(value))==value and uuid.UUID(value).int,'Canonical nonzero UID required');return value
def validate_targets(value):
 require(type(value)is dict and set(value)=={'pods','node','observer'} and type(value['pods'])is dict and set(value['pods'])=={'a','b'},'Closed current target manifest required')
 for key,row in [*value['pods'].items(),('node',value['node']),('observer',value['observer'])]:
  require(type(row)is dict and set(row)==({'namespace','name','uid','cap_mib'} if key in ('a','b') else {'namespace','name','uid'}),'Closed target required')
  canonical_uuid(row['uid']);require(isinstance(row['name'],str) and re.fullmatch('[a-z0-9][a-z0-9.-]{0,252}',row['name']),'Exact Kubernetes target name required')
  if key in ('a','b'):require(row['namespace']=='jupyterhub' and type(row['cap_mib'])is int and row['cap_mib']==5120,'Only approved CPS5GiB pair permitted')
 require(value['node']['namespace']=='cps-native-system' and value['observer']['namespace']=='gpu-operator' and value['observer']['name']=='cps-native-driver-control','Exact current observers required')
 require(len({r['uid'] for r in value['pods'].values()})==2 and len({r['name'] for r in value['pods'].values()})==2,'Distinct actual Pods required');return value

def read_targets(path,digest):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  before=os.fstat(fd);raw=os.read(fd,16385);after=os.fstat(fd)
  require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o600 and 0<len(raw)<=16384 and all(getattr(before,k)==getattr(after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Owned private0600 stable target manifest required')
  require(hashlib.sha256(raw).hexdigest()==digest,'Separately reviewed exact target manifest hash required');return validate_targets(json.loads(raw))
 finally:os.close(fd)

def command(argv,source=None):
 p=subprocess.run(['kubectl',*argv],input=source,text=True,capture_output=True,timeout=30)
 require(p.returncode==0,'Read-only current target observation failed');return json.loads(p.stdout)
def pod(row):return command(['-n',row['namespace'],'get','pod',row['name'],'-o','json'])
def checked_pod(actual,row,container,image=None):
 require(actual['metadata']['uid']==row['uid'] and not actual['metadata'].get('deletionTimestamp') and actual['spec']['nodeName']=='k3s-wk-gpu2' and actual['status']['phase']=='Running','Exact live current Pod required')
 spec=next(c for c in actual['spec']['containers']if c['name']==container);status=next(c for c in actual['status']['containerStatuses']if c['name']==container)
 require(status['ready']is True and status['restartCount']==0 and 'running'in status['state'],'Current ready un-restarted container required')
 if image is not None:require(spec['image']==image and status['imageID'].split('@')[-1]==image.split('@')[-1],'Exact qualified installed runtime image required')
 return {'uid':row['uid'],'spec':actual['spec'],'statuses':actual['status']['containerStatuses']}

NODE_READ="""import sys,json,pathlib,hashlib
from cps_compute.native_gpu_controller import CapRecord
from cps_compute.native_node.backend import private_read
from cps_compute.native_node.nvml import Nvml
from cps_compute.native_gpu_runtime import native_spec_sha256
pods=json.load(sys.stdin);result=[];driver=Nvml()
try:
 for pod in pods:
  uid=pod['metadata']['uid'];base=pathlib.Path('/run/cps-native-gpu')
  journal=base/'journal'/(uid+'.json');gate=base/'receipts'/(uid+'.json')
  record=CapRecord.from_dict(private_read(journal));actual_gate=private_read(gate)
  assert record.state=='sealed' and record.intent.pod_uid==uid and record.intent.cap_mib==5120 and record.limit==record.readback
  assert record.intent.namespace==pod['metadata']['namespace'] and record.intent.name==pod['metadata']['name']
  assert record.intent.spec_sha256==native_spec_sha256(pod) and actual_gate==record.receipt()
  assert record.intent.policy_hash=='sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
  identity=record.identity
  assert identity.boot_id=='209f8bc9-a478-48e4-925a-6e07ffa56f7a' and identity.driver_generation=='b10498fc-9153-4394-875a-ea7cfb498625'
  assert identity.gpu_uuid=='GPU-16128952-b438-556a-00bb-93039ee24e56'
  parent=pathlib.Path('/sys/fs/cgroup')/identity.cgroup_relative.lstrip('/');info=parent.stat()
  assert info.st_ino==identity.cgroup_inode and info.st_dev==identity.cgroup_device
  limits=driver.get(identity.gpu_uuid,parent);assert limits['soft']==limits['hard']==5368709120 and 0<=limits['used']<=5368709120
  result.append(dict(pod_uid=uid,intent=record.intent.to_dict(),identity=identity.to_dict(),seal_id=record.seal_id,
    journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest(),gate_sha256=hashlib.sha256(gate.read_bytes()).hexdigest(),inventory_row=limits))
 print(json.dumps(result))
finally:driver.close()
"""

def configure(targets):
 global OBSERVER_ARGV
 validate_targets(targets);observer=targets['observer']
 OBSERVER_ARGV=['kubectl','-n',observer['namespace'],'exec','-i',observer['name'],'-c','control','--','nsenter','-t','1','-m','-u','-i','-n','-p','--','/usr/bin/python3.12','-']

def preflight(config):
 targets=config['manifest'];validate_targets(targets)
 actual=[pod(targets['pods'][k])for k in ('a','b')]
 stable={k:checked_pod(p,targets['pods'][k],'notebook',NOTEBOOK_IMAGE)for k,p in zip(('a','b'),actual)}
 node=pod(targets['node']);stable['node']=checked_pod(node,targets['node'],'node-agent',NODE_IMAGE)
 observer=pod(targets['observer']);stable['observer']=checked_pod(observer,targets['observer'],'control')
 require(observer['spec'].get('hostPID')is True,'Actual Root observer host PID namespace required')
 rows=command(['-n',targets['node']['namespace'],'exec','-i',targets['node']['name'],'-c','node-agent','--','python','-B','-c',NODE_READ],json.dumps(actual))
 require(type(rows)is list and len(rows)==2 and [r['pod_uid']for r in rows]==[p['metadata']['uid']for p in actual] and len({r['identity']['cgroup_inode']for r in rows})==2,'Exact ordered distinct sealed parents required')
 # Re-read all process authorities after native observations, not only on postflight.
 for key,row,container,image in [(k,targets['pods'][k],'notebook',NOTEBOOK_IMAGE)for k in ('a','b')]+[('node',targets['node'],'node-agent',NODE_IMAGE),('observer',targets['observer'],'control',None)]:
  require(checked_pod(pod(row),row,container,image)==stable[key],'Process authority changed during preflight')
 return {'pods':stable,'host':{'targets':rows}}
