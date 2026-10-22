#!/usr/bin/env python3
"""Offline exact-source adaptation of historical managed/owner-exit/VMM gates."""
import argparse,ast,hashlib,json,os,re,types,uuid
from pathlib import Path
OLD=Path('/home/bjoern/.local/state/cps-group-native-20261009/group-probes')
COHORT='3b217fe8-5750-4ead-954a-09286afd7d3f'
BOOT='a464df41-e391-4443-b8e8-ad7ecd052318'
GEN='4ebffc96-e25e-4583-a3b8-0d853fd90efd'
PREFLIGHT_SHA='5ce86051f1a9bd435abc14a8633f273e03e1af086658de7fad8b8d5dcceb3cc0'
POLICY='sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281'
ROOT='/var/lib/cps-native-gpu/qualification/1f7d941a-872d-4453-a1ba-fd489d8aff14/cohorts/'+COHORT
HOST_ARGV=['ssh','-o','BatchMode=yes','ubuntu@10.21.0.43','sudo','-n','env','LD_LIBRARY_PATH=/run/nvidia/driver/usr/lib/x86_64-linux-gnu','python3','-I','-B','-']
PINS={
 'managed/run_managed.py':'2d013735da034b437837fbb3335ae6d188774df3942c4d9363167c8894373862',
 'managed/managed_probe.py':'a2ffe7b02ed783ec9247e5f9bd2b8f6472806cd7daaf82d530d219cf9dd2a2a9',
 'vmm-owner-exit/run_owner_exit.py':'2ad7751b0c282bb6033e226ed199f24a57d2d7a5971e8f3cc0796ac7ca465d80',
 'vmm-owner-exit/owner_exit_probe.py':'622649c757afd433d4c8f48513eb923f33cf1fd3d08acf7c749137c246c1d6ff',
 'vmm-owner-exit/host_owner_observer.py':'3881ca93b3b5d321dbd07e42b2e4bd9e0c9cbd6bc1454ccc7bc57fc81b259a81',
 'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py':'1f3ea6e31e876d088114859589cce5ce3f7d60834842b246ea55c1ae9fdef521',
 'vmm-cross-parent-sgid-fix/vmm_endpoint.py':'596d50a2083efc9442ce5f72e905fa19956f69a7b6a18f01f6904ca0a7eba4ad',
 'vmm-cross-parent-sgid-fix/vmm_bridge.py':'6e9b02c5ddfefac9b49330ab3423f07050d13252e7b0167f5e8c8da9d603f8aa',
 'vmm-cross-parent-sgid-fix/kernel_witness_collector.py':'beab9579a163397089489bf974cd75cdd11a5f2d06c93aa26e9f7a9ae5d6cf64',
 'vmm-cross-parent-sgid-fix/kernel_witness_transport.py':'3d6b0a7b383d5cb05f20ca76479e78eff1ce9c1964441718138596dcbc6caaea',
 'vmm-cross-parent-sgid-fix/kernel_witness_validator.py':'c54badfd88f0e30f8b8948aa48e3c24f59027779cd59bcfb9413e032d417096e'}

def require(ok,message):
 if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def replace(text,old,new,count=1):
 require(text.count(old)==count,'Exact historical adaptation span changed: '+old[:70]);return text.replace(old,new)
def load(name,raw):
 m=types.ModuleType(name);m.__file__=name;exec(compile(raw,name,'exec'),m.__dict__);return m

FACADE=r'''"""Fresh actual API/host brackets, no outcome cache or old observer authority."""
import hashlib,importlib.util,json,os,subprocess,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
HOST_SHA=__PREFLIGHT_SHA__
HOST_SOURCE=(HERE/'fresh_preflight.py').read_text()
if hashlib.sha256(HOST_SOURCE.encode()).hexdigest()!=HOST_SHA:raise ValueError('Fresh preflight source drift')
raw=(HERE/'manifest.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!=__MANIFEST_SHA__:raise ValueError('Actual manifest drift')
MANIFEST=json.loads(raw)
s=importlib.util.spec_from_file_location('current_fresh_preflight',HERE/'fresh_preflight.py')
current=importlib.util.module_from_spec(s);s.loader.exec_module(current);current.validate_targets(MANIFEST)
GPU=current.GPU
OBSERVER_ARGV=__HOST_ARGV__
def require(ok,msg):
 if not ok:raise ValueError(msg)
def canonical_uuid(v):require(type(v)is str and str(uuid.UUID(v))==v and uuid.UUID(v).int>0,'Canonical actual UUID required')
def write_json(path,value):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w')as f:json.dump(value,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def checked_run(argv,*,source=None,timeout=25,allow_empty=False):
 result=subprocess.run(argv,input=source,capture_output=True,timeout=timeout)
 require(result.returncode==0 and len(result.stdout)<=2*1024*1024,'Bounded reviewed transport failed')
 if allow_empty and not result.stdout.strip():return None
 return json.loads(result.stdout)
def python_stdin_source(source,request):
 raw=json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False)
 require(len(raw.encode())<=2*1024*1024,'Bounded original host request required')
 return ('import sys\nsys.argv=["-",'+repr(raw)+']\n'+source).encode()
def preflight(config):
 expected=[{'namespace':MANIFEST['pods'][k]['namespace'],'name':MANIFEST['pods'][k]['name'],'pod_uid':MANIFEST['pods'][k]['uid']}for k in ('a','b')]
 require(config=={'driver_generation':__GEN__,'targets':expected},'Exact prepared actual cohort required')
 observed=current.preflight({'manifest':MANIFEST})
 host=observed['host'];require(len(host['targets'])==2 and all(t['intent']['policy_hash']==__POLICY__ for t in host['targets']),'Actual sealed Source332 required')
 active={t['identity']['cgroup_inode']for t in host['targets']}
 for target in host['targets']:
  rows=[r for r in host['inventory']['entries']if r['inode']==target['identity']['cgroup_inode']]
  require(len(rows)==1 and rows[0]['soft']==rows[0]['hard']==target['intent']['cap_mib']*1048576,'Exact current parent accounting required')
  target['inventory_row']=rows[0]
 host['retired_caps']=[r for r in host['inventory']['entries']if r['inode']not in active]
 require(len(host['processes'])==len(observed['pods'])==2,'Complete actual notebook process bracket required')
 for pod,process in zip(observed['pods'],host['processes']):
  pod.update(pod_uid=pod['uid'],imageID=pod['status']['imageID'],containerID=pod['status']['containerID'],root_process=process)
 return observed
'''

def build(manifest,manifest_sha,preflight,preflight_sha):
 require(re.fullmatch('[a-f0-9]{64}',manifest_sha or '') and sha(preflight)==preflight_sha==PREFLIGHT_SHA,'Independent exact manifest/preflight pins required')
 raw={n:(OLD/n).read_bytes()for n in PINS}
 require(all(sha(raw[n])==pin for n,pin in PINS.items()),'Every historical engine must authenticate before execution')
 current=load('fresh_preflight.py',preflight);current.validate_targets(manifest)
 require(manifest['cohort_uid']==COHORT and manifest['pods']['a']['cap_mib']==5120 and manifest['pods']['b']['cap_mib']==10240,'Exact current5/10 cohort required')
 caps={manifest['pods'][k]['uid']:manifest['pods'][k]['cap_mib']*1048576 for k in ('a','b')}
 facade=FACADE.replace('__PREFLIGHT_SHA__',repr(preflight_sha)).replace('__MANIFEST_SHA__',repr(manifest_sha)).replace('__HOST_ARGV__',repr(HOST_ARGV)).replace('__GEN__',repr(GEN)).replace('__POLICY__',repr(POLICY))
 out={'run_group_acceptance.py':facade.encode(),'fresh_preflight.py':preflight,'manifest.json':json.dumps(manifest).encode()}
 # Caller replaces manifest.json with the exact original raw bytes after validation.
 text={n.replace('vmm-cross-parent-sgid-fix/','vmm-cross-parent/'):v.decode()for n,v in raw.items()}
 for name,s in text.items():
  s=s.replace('209f8bc9-a478-48e4-925a-6e07ffa56f7a',BOOT).replace('b10498fc-9153-4394-875a-ea7cfb498625',GEN)
  s=s.replace('9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0','5427088986bc06ad0713875d1aa2f31439f0bd1fbe6099d4669570fcf3e85be4')
  s=s.replace('/run/cps-native-gpu/operator/vmm-cross-parent-sgid-fix',ROOT+'/vmm-bridge').replace('/run/cps-native-gpu/operator/vmm-kmsg-witness',ROOT+'/vmm-kmsg-witness')
  for old,key in [('4010edf4-f407-409b-aa4c-de0615e8c05c','a'),('879a4589-faee-4569-bdb8-f2e7c154ef19','b')]:s=s.replace(old,manifest['pods'][key]['uid'])
  text[name]=s
 for name in ('vmm-owner-exit/owner_exit_probe.py','vmm-cross-parent/vmm_endpoint.py'):
  s=text[name];s=replace(s,'CAP=5368709120','CAP=5368709120\nCAPS='+repr(caps))
  if 'owner_exit' in name:
   s=replace(s,'    global TRIAL,ROLE','    global TRIAL,ROLE,CAP')
   s=replace(s,'    preflight(args);TRIAL,ROLE=args.trial_id,args.role',"    preflight(args)\n    require(args.expected_pod_uid in CAPS,'Only exact enrolled parent permitted')\n    CAP=CAPS[args.expected_pod_uid];TRIAL,ROLE=args.trial_id,args.role")
  else:
   s=replace(s,'    global TRIAL,ROLE;TRIAL=args.trial_id;ROLE=args.role',"    global TRIAL,ROLE,CAP;TRIAL=args.trial_id;ROLE=args.role\n    require(args.expected_pod_uid in CAPS,'Only exact enrolled parent permitted')\n    CAP=CAPS[args.expected_pod_uid]")
  text[name]=s
 name='vmm-owner-exit/host_owner_observer.py';s=text[name]
 s=replace(s,'CAP=5368709120','CAP=5368709120\nCAPS='+repr(caps))
 s=replace(s,"    identity=request['identity'];path=identity['cgroup_relative']\n    require(path.startswith", "    identity=request['identity']\n    global CAP\n    require(identity.get('pod_uid') in CAPS,'Exact enrolled parent required')\n    CAP=CAPS[identity['pod_uid']];path=identity['cgroup_relative']\n    require(path.startswith")
 text[name]=s
 name='vmm-cross-parent/vmm_bridge.py';s=text[name]
 s=replace(s,"    relative = identity['cgroup_relative']", "    require(identity.get('pod_uid') in CAPS,'Only exact enrolled parent permitted')\n    relative = identity['cgroup_relative']")
 s=s.replace('5368709120',"CAPS[identity['pod_uid']]")
 s='CAPS='+repr(caps)+'\n'+s
 text[name]=s
 for name in ('managed/run_managed.py','vmm-owner-exit/run_owner_exit.py','vmm-cross-parent/run_vmm_cross_parent.py'):
  s=text[name].replace('91da523bc0a99cbb78f42f28dcc738d80710c03daed5b00ad1202c4196cd6d8c',sha(facade.encode())).replace('463a9d907a5c33877c100dc79a25d4f6d7ed9d607c806b5742bfce0a51972ccd',preflight_sha)
  s=s.replace("'observer_uid':args.observer_pod_uid,",'')
  s=s.replace("'namespace':'jupyterhub','name':'jupyter-cpsnativegroupb--rtc'", "'namespace':"+repr(manifest['pods']['a']['namespace'])+",'name':"+repr(manifest['pods']['a']['name']))
  s=s.replace("'namespace':'cit-jhub','name':'jupyter-citnativegroupa--rtc'", "'namespace':"+repr(manifest['pods']['b']['namespace'])+",'name':"+repr(manifest['pods']['b']['name']))
  s=s.replace("'cps-pod-uid','cit-pod-uid','observer-pod-uid','driver-generation'","'cps-pod-uid','cit-pod-uid','driver-generation'")
  s=s.replace('(args.cps_pod_uid,args.cit_pod_uid,args.observer_pod_uid)','(args.cps_pod_uid,args.cit_pod_uid)')
  s=s.replace("h.canonical_uuid(args.observer_pod_uid)","pass  # Root transport is fixed; no retired observer Pod authority")
  if 'owner_exit' in name:
   s=replace(s,"cohort=load_singleuser_cohort(args.singleuser_baseline,args.singleuser_baseline_sha256,native,before['pods'][index])",'cohort=None  # Existing strict participant-only/empty baseline branch for idle QA')
   s=s.replace('5368709120',"CAPS[post_release['pod_uid']]");s='CAPS='+repr(caps)+'\n'+s
  for oldname,oldpin in PINS.items():
   leaf=oldname.split('/')[-1];key=oldname.replace('vmm-cross-parent-sgid-fix/','vmm-cross-parent/')
   if leaf not in ('run_managed.py','run_owner_exit.py','run_vmm_cross_parent.py') and oldpin in s:s=s.replace(oldpin,sha(text[key].encode()))
  text[name]=s
 out.update({n:s.encode()for n,s in text.items()})
 for name,data in out.items():
  if name.endswith('.py'):compile(data,name,'exec')
 return out

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--manifest',type=Path);p.add_argument('--manifest-sha256');p.add_argument('--preflight',type=Path);p.add_argument('--preflight-sha256');p.add_argument('--output',type=Path);a=p.parse_args(argv)
 if not a.prepare:print(json.dumps({'inert':True,'api_calls':False,'gpu_calls':False}));return
 require(all((a.manifest,a.manifest_sha256,a.preflight,a.preflight_sha256,a.output)),'Actual reviewed manifest/preflight and new private output required')
 raw=a.manifest.read_bytes();require(len(raw)<=65536 and sha(raw)==a.manifest_sha256,'Actual manifest raw bytes changed')
 sources=build(json.loads(raw),a.manifest_sha256,a.preflight.read_bytes(),a.preflight_sha256);sources['manifest.json']=raw;a.output.mkdir(mode=0o700)
 for name,data in sources.items():
  path=a.output/name;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb')as f:f.write(data)
 print(json.dumps({'state':'prepared','sources':{n:sha(v)for n,v in sources.items()},'hardware_qualified':False,'production_qualified':False},sort_keys=True))
if __name__=='__main__':main()
