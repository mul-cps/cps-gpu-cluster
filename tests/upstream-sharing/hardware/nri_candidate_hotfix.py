#!/usr/bin/env python3
"""Bounded final-binary NRI qualification. Run only in the released GPU2 window."""
import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

BASE=Path('docs/operations/evidence/upstream-sharing-20261116/managed-policy-load')
OUT=BASE/'nri-hotfix-qualified'
OLD=BASE/'nri-candidate'
SSH=['ssh','-i','/home/bjoern/.ssh/id_ed25519','-o','IdentitiesOnly=yes','-o','BatchMode=yes','ubuntu@10.21.0.43']
NS='gpu-operator'
GPUS=['GPU-16128952-b438-556a-00bb-93039ee24e56','GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6']
OWNED={}
GUARD=(OLD/'resume-guard.py').read_text()

def run(args,stdin=None,timeout=30):
    return subprocess.check_output(args,input=stdin,text=True,timeout=timeout)

def write(name,data):
    (OUT/name).write_text(data if isinstance(data,str) else json.dumps(data,indent=2)+'\n')

def remote(code,*args):
    return run(SSH+['sudo python3 - '+shlex.join(list(args))],code)

def get(name):
    return json.loads(run(['kubectl','get','pod','-n',NS,name,'-o','json']))

def create(suffix,template='hung-pod.json',gpu=GPUS[0]):
    body=json.loads((OLD/template).read_text())
    name='nri-hotfix-'+suffix
    body['metadata']['name']=name
    body['metadata']['labels']={'cps.unileoben.ac.at/extended-probe':'nri-hotfix-qualified'}
    if 'annotations' in body['metadata']:
        body['metadata']['annotations']['nvidia.com/container.main.gpus.devices']='k8s.device-plugin.nvidia.com/gpu='+gpu
    write(suffix+'-pod.json',body)
    result=json.loads(run(['kubectl','create','-f','-','-o','json'],json.dumps(body)))
    OWNED[name]=result['metadata']['uid']
    write(suffix+'-created.json',result)
    return name

def delete(name):
    if name not in OWNED:return
    body=json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':OWNED[name]}})
    result=run(['kubectl','delete','--raw','/api/v1/namespaces/'+NS+'/pods/'+name,'-f','-'],body)
    write(name+'-delete.json',result)
    del OWNED[name]

def wait(name,predicate,seconds=60):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        pod=get(name);write(name+'-latest.json',pod)
        if predicate(pod):return pod
        if pod['status'].get('phase')=='Failed':raise RuntimeError('Pod failed: '+name)
        time.sleep(.4)
    raise TimeoutError(name)

def no_exec(pod):
    assert all(not c.get('containerID') and not c.get('state',{}).get('running') and not c.get('state',{}).get('terminated') for c in pod['status'].get('containerStatuses',[])), 'GPU container executed before required plugin returned'

def rejected(pod):
    no_exec(pod)
    return any('required plugin "gpu-fractioning" not present' in c.get('state',{}).get('waiting',{}).get('message','') for c in pod['status'].get('containerStatuses',[]))

def host_snapshot(label,idle=True):
    observer=Path('tests/upstream-sharing/hardware/extended_host_observer.py').read_text()
    rows=[]
    for gpu in GPUS:
        row=json.loads(remote(observer,'--node','k3s-wk-gpu2','--gpu-uuid',gpu))
        assert row['uvm']=={'srcversion':'10301D70B8ED1758BC717E9','parameters/uvm_reject_managed_memory':'Y','parameters/uvm_disable_hmm':'Y'}
        assert row['uvm_source_sha256']=='5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18'
        if idle:assert not row['compute_processes'],row
        rows.append(row)
    write(label+'-host.json',rows)
    identity=json.loads(remote('''import hashlib,json,pathlib,subprocess
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
agent=int(subprocess.check_output(['systemctl','show','k3s-agent','-p','MainPID','--value'],text=True))
containerd=[]
for entry in pathlib.Path('/proc').iterdir():
 if not entry.name.isdigit():continue
 try:
  fields=(entry/'stat').read_text().rsplit(')',1)[1].split()
  if int(fields[1])==agent and (entry/'comm').read_text().strip()=='containerd':containerd.append(int(entry.name))
 except FileNotFoundError:pass
assert len(containerd)==1,containerd
print(json.dumps({'outer_sha256':sha('/usr/local/bin/k3s'),'data_current':str(pathlib.Path('/var/lib/rancher/k3s/data/current').resolve()),'processes':[{'pid':p,'executable':str(pathlib.Path('/proc/'+str(p)+'/exe').resolve()),'sha256':sha('/proc/'+str(p)+'/exe')} for p in [agent,containerd[0]]]}))
'''))
    assert identity['outer_sha256']=='6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c'
    assert identity['data_current'].endswith('/2277a2c458beda093f8367b944c2fbb2e5f53a00f17776759721fb781b3874fa')
    assert all(p['sha256']=='0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a' for p in identity['processes'])
    write(label+'-runtime.json',identity)

def hang():
    pod=json.loads(run(['kubectl','get','pod','-n','gpu-fractioning','gpu-fractioning-fractiond-d7j6f','-o','json']))
    assert pod['spec']['nodeName']=='k3s-wk-gpu2'
    cid=next(c['containerID'] for c in pod['status']['containerStatuses'] if c['name']=='fractiond').removeprefix('containerd://')
    identity=json.loads(remote('''import json,pathlib,subprocess,sys
b=json.loads(subprocess.check_output(['k3s','crictl','inspect',sys.argv[1]],text=True));p=int(b['info']['pid']);root=pathlib.Path('/proc/'+str(p));cmd=(root/'cmdline').read_bytes().split(b'\\0');assert cmd[0]==b'/fractiond',cmd
print(json.dumps({'pid':p,'starttime':(root/'stat').read_text().rsplit(')',1)[1].split()[19],'cmdline':[x.decode() for x in cmd if x],'cgroup':(root/'cgroup').read_text()}))
''',cid))
    pid=identity['pid'];start=identity['starttime'];unit='cps-nri-hotfix-cont-'+str(pid)
    identity.update(pod_uid=pod['metadata']['uid'],container_id=cid,unit=unit)
    write('fractiond-hang-identity.json',identity)
    write('resume-guard.py',GUARD)
    timer=['sudo','systemd-run','--unit='+unit,'--on-active=15s','--timer-property=AccuracySec=1us','--collect','/usr/bin/python3','-c',GUARD,str(pid),start]
    armed=False;snapshots=[];started=time.time()
    try:
        run(SSH+[shlex.join(timer)])
        assert run(SSH+['sudo systemctl is-active '+unit+'.timer']).strip()=='active'
        armed=True
        remote("import os,signal,pathlib;pid="+str(pid)+";fd=os.pidfd_open(pid);assert pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]=="+repr(start)+";signal.pidfd_send_signal(fd,signal.SIGSTOP);os.close(fd)")
        identity['stopped_at']=time.time()
        gpu=create('hung')
        first=wait(gpu,rejected,8);write('first-rejection.json',first)
        cpu=create('hung-cpu','hung-cpu-pod.json')
        cpu_result=wait(cpu,lambda p:p['status'].get('phase')=='Succeeded',6)
        state=remote("from pathlib import Path; print(Path('/proc/"+str(pid)+"/stat').read_text().rsplit(')',1)[1].split()[0])").strip()
        assert state=='T','CPU witness must finish while fractiond remains stopped'
        write('cpu-during-stop.json',cpu_result)
        disconnected=create('disconnected')
        second=wait(disconnected,rejected,5);write('disconnected-rejection.json',second)
        while time.time()-identity['stopped_at']<18:
            state=remote("from pathlib import Path; print(Path('/proc/"+str(pid)+"/stat').read_text().rsplit(')',1)[1].split()[0])").strip()
            pods=[get(gpu),get(disconnected)]
            if state=='T':
                for p in pods:no_exec(p)
            snapshots.append({'time':time.time(),'fractiond_state':state,'pods':pods})
            write('hung-snapshots.json',snapshots)
            time.sleep(.5)
        identity.update(status='PASS',first_required_timeout_rejected=True,disconnected_required_rejected=True,cpu_success_while_stopped=True)
    finally:
        if armed:
            result=subprocess.run(SSH+[shlex.join(['sudo','python3','-c',GUARD,str(pid),start])],text=True,capture_output=True,timeout=20)
            write('final-resume.txt',result.stdout+result.stderr)
            assert result.returncode==0
            stopped=subprocess.run(SSH+['sudo systemctl stop '+unit+'.timer'],capture_output=True,text=True,timeout=20)
            timer_state=run(SSH+['sudo systemctl show '+unit+'.timer -p LoadState -p ActiveState'])
            write('timer-final-state.txt',timer_state)
            assert 'ActiveState=inactive' in timer_state,timer_state
            write('timer-journal.txt',run(SSH+['sudo journalctl -u '+unit+'.service --no-pager']))
            write('fractiond-journal.txt',run(['kubectl','logs','-n','gpu-fractioning',pod['metadata']['name'],'-c','fractiond','--since=3m']))
            write('agent-hang-journal.txt',run(SSH+['sudo journalctl -u k3s-agent --since=@'+str(int(started))+' --no-pager']))
        write('hung-summary.json',identity)
        for name in list(OWNED):delete(name)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    assert not (OUT/'summary.json').exists(),'Never overwrite a completed qualification run'
    summary={'status':'RUNNING','started_at':time.time()}
    try:
        node=json.loads(run(['kubectl','get','node','k3s-wk-gpu2','-o','json']))
        assert node['spec']['unschedulable'] and 'cps.unileoben.ac.at/upstream-sharing-qualified' not in node['metadata']['labels']
        write('node-before.json',node)
        host_snapshot('before')
        hang()
        summary['hang']='PASS'
        # Allow the released Fractioning reconnect loop to register before CUDA.
        time.sleep(12)
        for number,gpu in enumerate(GPUS):
            name=create('recovery-'+str(number),'recovery-pod.json',gpu)
            wait(name,lambda p:p['status'].get('phase')=='Succeeded',60)
            logs=run(['kubectl','logs','-n',NS,name]);write('recovery-'+str(number)+'.log',logs)
            assert 'RAW_DRIVER_LIMIT_AND_RECOVERY_PASSED' in logs
            delete(name)
        summary['recovery_cards']=2
        host_snapshot('after')
        summary['status']='PASS'
    except BaseException as exc:
        summary.update(status='FAIL',error=repr(exc));raise
    finally:
        for name in list(OWNED):delete(name)
        summary['finished_at']=time.time();write('summary.json',summary)

if __name__=='__main__':main()
