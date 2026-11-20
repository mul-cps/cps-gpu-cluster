#!/usr/bin/env python3
"""Create a new owned TrueNAS SeaweedFS app/dataset. Never overwrite existing storage."""
import argparse
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess

APP='cps-compute-artifacts'
DATASET='persistent1/cps_compute_artifacts'
MOUNT='/mnt/'+DATASET
IMAGE='chrislusf/seaweedfs:4.48@sha256:aba492e2a4e4c90bff795745e8e660affa1f09e7650f5981bd7bccd1a06cd931'
REMOTE=r'''
import base64,json,os,pathlib,subprocess,sys
request=json.load(sys.stdin)
if request['operation']=='rpc':
 allowed={'app.query','app.create','app.stop','app.start','app.redeploy','app.update','pool.dataset.query','pool.dataset.create','filesystem.mkdir','filesystem.setperm'}
 if request['method'] not in allowed:raise ValueError('Method not permitted')
 args=['midclt','call']+(['-j'] if request.get('job') else [])+[request['method']]+[json.dumps(a) for a in request['args']]
 proc=subprocess.run(args,capture_output=True,text=True)
 if proc.returncode:
  sys.stderr.write(proc.stderr);sys.exit(proc.returncode)
 print(proc.stdout)
elif request['operation']=='files':
 root=pathlib.Path('/mnt/persistent1/cps_compute_artifacts/config')
 for name,data in request['files'].items():
  if name not in ('s3.json','tls.crt','tls.key','ca.crt','filer.toml'):raise ValueError('Invalid config file')
  path=root/name
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(base64.b64decode(data,validate=True))
 print(json.dumps({'files_written':len(request['files'])}))
else:raise ValueError('Invalid operation')
'''

def remote(host,request):
    r=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -c '+shlex.quote(REMOTE)],input=json.dumps(request),capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)

def rpc(host,method,*args,job=False):return remote(host,{'operation':'rpc','method':method,'args':args,'job':job})

def compose():
    return {'services':{'seaweed':{
        'image':IMAGE,'entrypoint':['/usr/bin/weed'],
        'command':['server','-ip=127.0.0.1','-ip.bind=0.0.0.0','-dir=/data','-master.dir=/data/master','-volume.max=64','-master.volumeSizeLimitMB=1024','-filer=true','-filer.disableDirListing=true','-s3=true','-s3.port=8333','-s3.config=/run/cps/s3.json','-s3.cert.file=/run/cps/tls.crt','-s3.key.file=/run/cps/tls.key'],
        'user':'568:568','ports':['8333:8333'],'restart':'unless-stopped',
        'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'read_only':True,
        'tmpfs':['/tmp:rw,noexec,nosuid,size=64m'],
        'mem_limit':'2g','cpus':2.0,'pids_limit':256,
        'volumes':[MOUNT+'/data:/data',MOUNT+'/config:/run/cps:ro',MOUNT+'/config/filer.toml:/etc/seaweedfs/filer.toml:ro'],
        'healthcheck':{'test':['CMD','curl','--cacert','/run/cps/ca.crt','--silent','--output','/dev/null','https://127.0.0.1:8333/'], 'interval':'30s','timeout':'10s','retries':3}
    }}}

def ensure_new(datasets,apps):
    if datasets:raise ValueError('Dataset already exists; refusing overwrite')
    if apps:raise ValueError('Application already exists; use reviewed update procedure')

def deploy(host,private):
    ensure_new(rpc(host,'pool.dataset.query',[['id','=',DATASET]]),rpc(host,'app.query',[['id','=',APP]]))
    rpc(host,'pool.dataset.create',{'name':DATASET,'type':'FILESYSTEM','comments':'CPS compute SeaweedFS artifact store; owned dedicated dataset','compression':'LZ4','atime':'OFF','exec':'OFF','acltype':'POSIX','aclmode':'DISCARD','quota':256*1024**3})
    return finish_deploy(host,private)

def finish_deploy(host,private):
    rpc(host,'filesystem.setperm',{'path':MOUNT,'uid':950,'gid':950,'mode':'700','options':{'stripacl':True}},job=True)
    for name in ('data','config'):
        rpc(host,'filesystem.mkdir',{'path':MOUNT+'/'+name,'options':{'mode':'700'}})
        rpc(host,'filesystem.setperm',{'path':MOUNT+'/'+name,'uid':950,'gid':950,'mode':'700','options':{'stripacl':True}},job=True)
    files={name:base64.b64encode((private/name).read_bytes()).decode() for name in ('s3.json','tls.crt','tls.key','ca.crt','filer.toml')}
    remote(host,{'operation':'files','files':files})
    rpc(host,'filesystem.mkdir',{'path':MOUNT+'/data/master','options':{'mode':'700'}})
    rpc(host,'filesystem.setperm',{'path':MOUNT,'uid':568,'gid':568,'mode':'750','options':{'recursive':True,'stripacl':True}},job=True)
    for name in ('s3.json','tls.key'):
        rpc(host,'filesystem.setperm',{'path':MOUNT+'/config/'+name,'uid':568,'gid':568,'mode':'600'},job=True)
    result=rpc(host,'app.create',{'app_name':APP,'custom_app':True,'custom_compose_config':compose()},job=True)
    return {'app':result['id'],'state':result['state'],'dataset':DATASET,'image':IMAGE}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',default='truenas_admin@truenas.local');p.add_argument('--private',type=Path,required=True);p.add_argument('--deploy',action='store_true');args=p.parse_args()
    if args.deploy:print(json.dumps(deploy(args.host,args.private),indent=2))
    else:print(json.dumps(compose(),indent=2))
if __name__=='__main__':main()
