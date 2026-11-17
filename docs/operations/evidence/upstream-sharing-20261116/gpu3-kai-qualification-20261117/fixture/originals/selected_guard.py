import json,re,uuid,subprocess,shlex
from pathlib import Path
NODE='k3s-wk-gpu3';UID='7b3b5113-158d-4e0d-bd63-898a508fe806';IP='10.21.0.40'
GPUS=('GPU-0a9f2da8-59f5-1cb0-9ead-d9fce56b69e5','GPU-e7a56fad-ce29-f7d7-380a-3b5ae62a0b2a')
KERNEL='7.0.0-43-generic';UVM='10301D70B8ED1758BC717E9';SOURCE='5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18'
DRIVER='ghcr.io/mul-cps/cps-nvidia-driver@sha256:c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73'
FIELDS={'node','node_uid','node_ip','gpu_uuids','expected_boot_id','driver_pod','driver_pod_uid','driver_cid','fractiond_pod','fractiond_pod_uid','fractiond_cid','release_reference','ssh_target','ssh_key'}
def require(value,message):
 if not value:raise ValueError(message)
def validate_selection(s):
 require(set(s)==FIELDS,'closed selection fields required')
 require((s['node'],s['node_uid'],s['node_ip'],s['gpu_uuids'])==(NODE,UID,IP,list(GPUS)),'exact GPU3 identity required')
 for key in ['expected_boot_id','driver_pod_uid','fractiond_pod_uid']:
  require(isinstance(s[key],str),'fresh UUID required');require(str(uuid.UUID(s[key]))==s[key],'canonical UUID required')
 for key in ['driver_cid','fractiond_cid']:require(isinstance(s[key],str) and re.fullmatch('[0-9a-f]{64}',s[key]),'fresh operand CID required')
 for key in ['driver_pod','fractiond_pod']:require(isinstance(s[key],str) and re.fullmatch('[a-z0-9][a-z0-9.-]{0,252}',s[key]),'fresh operand name required')
 require(s['ssh_target']=='ubuntu@'+IP and s['ssh_key']=='/home/bjoern/.ssh/id_ed25519','exact authorized SSH destination/key required')
 require(isinstance(s['release_reference'],str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}',s['release_reference']),'explicit parent release reference required')
 return s
def validate_node(n,s):
 validate_selection(s);m=n['metadata'];st=n['status'];sp=n['spec'];ni=st.get('nodeInfo',{})
 require(m.get('name')==NODE and m.get('uid')==UID and not m.get('deletionTimestamp'),'Node identity changed')
 require(any(c.get('type')=='Ready' and c.get('status')=='True'for c in st.get('conditions',[])),'Ready required')
 require(any(a.get('type')=='InternalIP' and a.get('address')==IP for a in st.get('addresses',[])),'Node IP changed')
 require(ni.get('bootID')==s['expected_boot_id'] and ni.get('kernelVersion')==KERNEL and ni.get('osImage')=='Ubuntu 26.04.1 LTS','Node boot/kernel/OS mismatch')
 require(sp.get('unschedulable') is True and 'cps.unileoben.ac.at/upstream-gpu-sharing'not in m.get('labels',{}),'cordoned/unqualified worker required')
 require(any(t.get('key')=='cps.unileoben.ac.at/maintenance' and t.get('value')=='upstream-pilot' and t.get('effect')=='NoSchedule'for t in sp.get('taints',[])),'exact maintenance taint required')
def validate_host(h,s,gpu):
 require(gpu in GPUS and h.get('node')==NODE and h.get('boot_id')==s['expected_boot_id'],'host node/boot changed')
 rows=[v.strip()for v in h['gpu'].split(',')];require(rows[0]==gpu and rows[1]=='620.70.06' and int(rows[3])==40960,'host GPU UUID/version/capacity mismatch')
 require(h.get('uvm')=={'srcversion':UVM,'parameters/uvm_reject_managed_memory':'Y','parameters/uvm_disable_hmm':'Y'} and h.get('uvm_source_sha256')==SOURCE,'loaded source/UVM policy mismatch')
def validate_operand(p,s,kind):
 name='nvidia-driver-ctr'if kind=='driver'else'fractiond';ns='gpu-operator'if kind=='driver'else'gpu-fractioning';m=p['metadata']
 require(m.get('name')==s[kind+'_pod'] and m.get('uid')==s[kind+'_pod_uid'] and not m.get('deletionTimestamp') and p['spec'].get('nodeName')==NODE,'operand Pod identity mismatch')
 rows=[v for v in p.get('status',{}).get('containerStatuses',[])if v['name']==name]
 require(len(rows)==1 and rows[0].get('ready') is True and 'running'in rows[0].get('state',{}) and rows[0].get('containerID')=='containerd://'+s[kind+'_cid'],'operand CID/readiness mismatch')
 if kind=='driver':
  require(any(v['name']==name and v['image']==DRIVER for v in p['spec']['containers']) and rows[0].get('imageID','').split('@')[-1]==DRIVER.split('@')[-1],'driver artifact mismatch')
def reject_consumers(pods):
 for p in pods:
  if p['spec'].get('nodeName')!=NODE or p.get('status',{}).get('phase') in ('Succeeded','Failed'):continue
  annotations=p['metadata'].get('annotations',{})
  require(not any(k.startswith(('nvidia.com/container.','gpu-memory','gpu-fraction','required-plugins.'))for k in annotations) and not any(k.startswith('nvidia.com/')for c in p['spec'].get('containers',[])for tier in ('requests','limits')for k in c.get('resources',{}).get(tier,{})),'concurrent GPU consumer or pending work')
def read_selection(path=None):return validate_selection(json.loads(Path(path or Path(__file__).with_name('selection.json')).read_text()))
def kube(*args):return json.loads(subprocess.check_output(['kubectl',*args,'-o','json'],text=True,timeout=20))
def check_node(s):validate_node(kube('get','node',NODE),s)
def preflight(s,observer):
 check_node(s)
 reject_consumers(kube('get','pods','-A','--field-selector','spec.nodeName='+NODE)['items'])
 for kind,ns in [('driver','gpu-operator'),('fractiond','gpu-fractioning')]:validate_operand(kube('get','pod',s[kind+'_pod'],'-n',ns),s,kind)
 ssh=['ssh','-i',s['ssh_key'],'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=8',s['ssh_target']]
 for gpu in GPUS:
  cmd=shlex.join(['sudo','-n','python3','-','--node',NODE,'--gpu-uuid',gpu]);h=json.loads(subprocess.check_output(ssh+[cmd],input=Path(observer).read_text(),text=True,timeout=30));validate_host(h,s,gpu);require(not h['compute_processes'].strip() and int(h['gpu'].split(',')[2])<=64,'idle cards required')
