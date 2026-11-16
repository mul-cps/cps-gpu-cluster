#!/usr/bin/env python3
"""Bounded final-binary NRI qualification. Run only for an explicitly released selected worker."""
import argparse
import copy
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import uuid

BASE=Path('docs/operations/evidence/upstream-sharing-20261116/managed-policy-load')
OUT=None
ARGS=None
OLD=BASE/'nri-candidate'
NS='gpu-operator'
KERNEL='7.0.0-43-generic'
DRIVER='ghcr.io/mul-cps/cps-nvidia-driver@sha256:c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73'
OWNED={}
GUARD=(OLD/'resume-guard.py').read_text()

def arguments(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-boot-id',required=True)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--fractiond-pod',required=True)
    p.add_argument('--fractiond-pod-uid',required=True)
    for flag in ('node','node-uid','node-ip','ssh-target','gpu-a','gpu-b','release-reference'):
        p.add_argument('--'+flag,required=True)
    p.add_argument('--ssh-key',required=True,type=Path)
    p.add_argument('--execute',action='store_true',required=True,help='Explicit parent release is also required via --release-reference')
    a=p.parse_args(argv)
    try:
        uuid.UUID(a.expected_boot_id);uuid.UUID(a.fractiond_pod_uid);uuid.UUID(a.node_uid)
        ipaddress.ip_address(a.node_ip)
        for gpu in (a.gpu_a,a.gpu_b):
            if not gpu.startswith('GPU-') or str(uuid.UUID(gpu[4:]))!=gpu[4:]:raise ValueError('GPU UUID')
    except ValueError:p.error('Valid boot/Pod/Node UUIDs, node IP and full GPU UUIDs required')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}',a.fractiond_pod):p.error('Explicit valid fractiond Pod name required')
    if a.node not in {f'k3s-wk-gpu{i}' for i in range(1,5)}:p.error('Select exactly one GPU worker1–4')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*@[A-Za-z0-9][A-Za-z0-9.:-]*',a.ssh_target):p.error('Explicit SSH user@target required')
    if a.gpu_a==a.gpu_b:p.error('Two distinct physical GPU UUIDs required')
    if not a.ssh_key.is_absolute():p.error('Explicit absolute SSH key path required')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}',a.release_reference):p.error('Explicit parent release reference required')
    return a


def fresh_output(path):
    path.mkdir(parents=True,exist_ok=False)


def require_boot(actual,expected):
    if actual!=expected:raise RuntimeError('Actual boot ID differs from explicitly approved cold-boot witness')


def validate_node(node,args):
    if (node['metadata'].get('name')!=args.node or node['metadata'].get('uid')!=args.node_uid
            or node['metadata'].get('deletionTimestamp')
            or not any(c.get('type')=='Ready' and c.get('status')=='True' for c in node.get('status',{}).get('conditions',[]))
            or not any(c.get('type')=='InternalIP' and c.get('address')==args.node_ip for c in node.get('status',{}).get('addresses',[]))
            or node.get('status',{}).get('nodeInfo',{}).get('bootID')!=args.expected_boot_id
            or node.get('status',{}).get('nodeInfo',{}).get('kernelVersion')!=KERNEL
            or not node['spec'].get('unschedulable')
            or 'cps.unileoben.ac.at/upstream-gpu-sharing' in node['metadata'].get('labels',{})
            or not any(t.get('key')=='cps.unileoben.ac.at/maintenance' and t.get('effect')=='NoSchedule'
                for t in node['spec'].get('taints',[]))):
        raise RuntimeError('Exact Ready Node UID/IP/kernel, cordoned, maintenance-tainted and unqualified worker required')


def validate_fractiond(pod,args):
    meta=pod['metadata']
    if (meta.get('name')!=args.fractiond_pod or meta.get('uid')!=args.fractiond_pod_uid
            or meta.get('deletionTimestamp') or pod['spec'].get('nodeName')!=args.node):
        raise RuntimeError('Explicit current fractiond Pod name/UID/node required')
    rows=[c for c in pod['status'].get('containerStatuses',[]) if c['name']=='fractiond']
    if len(rows)!=1 or rows[0].get('ready') is not True or 'running' not in rows[0].get('state',{}):raise RuntimeError('Running fractiond container required')
    cid=rows[0].get('containerID','')
    if not re.fullmatch(r'containerd://[0-9a-f]{64}',cid):raise RuntimeError('Exact CRI fractiond container ID required')
    return cid.removeprefix('containerd://')


def ssh_command(args):
    return ['ssh','-i',str(args.ssh_key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',args.ssh_target]


def validate_driver_pods(pods,args):
    selected=[p for p in pods if p['spec'].get('nodeName')==args.node and not p['metadata'].get('deletionTimestamp')
        and any(c['name']=='nvidia-driver-ctr' for c in p['spec']['containers'])]
    if len(selected)!=1:raise RuntimeError('One current selected-worker driver Pod required')
    pod=selected[0]
    containers=[c for c in pod['spec']['containers'] if c['name']=='nvidia-driver-ctr']
    status=[c for c in pod.get('status',{}).get('containerStatuses',[]) if c['name']=='nvidia-driver-ctr']
    if (len(containers)!=1 or containers[0]['image']!=DRIVER or len(status)!=1
            or status[0].get('ready') is not True or 'running' not in status[0].get('state',{})
            or status[0].get('imageID','').split('@')[-1].removeprefix('containerd://')!=DRIVER.split('@')[1]):
        raise RuntimeError('Exact running Ready c3b driver candidate required')


def reject_gpu_consumers(pods,args):
    # Same annotation/resource predicate as the KAI placement acceptance guard.
    for pod in pods:
        if pod['spec'].get('nodeName')!=args.node or pod.get('status',{}).get('phase') in ('Succeeded','Failed'):continue
        annotations=pod['metadata'].get('annotations',{})
        if any(k.startswith(('nvidia.com/container.','gpu-memory','gpu-fraction','required-plugins.')) for k in annotations) or any(
                k.startswith('nvidia.com/') for c in pod['spec'].get('containers',[]) for tier in ('requests','limits') for k in c.get('resources',{}).get(tier,{})):
            raise RuntimeError('Concurrent GPU consumer: '+pod['metadata']['name'])


def validate_fractiond_process(identity,args,cid):
    if (identity.get('container_id')!=cid or identity.get('pod_uid')!=args.fractiond_pod_uid
            or identity.get('pod_name')!=args.fractiond_pod or identity.get('namespace')!='gpu-fractioning'
            or identity.get('container_name')!='fractiond' or not isinstance(identity.get('pid'),int)
            or identity['pid']<=1 or not str(identity.get('starttime','')).isdigit()
            or not identity.get('cmdline') or identity['cmdline'][0]!='/fractiond'
            or cid not in identity.get('cgroup','')
            or args.fractiond_pod_uid not in identity.get('cgroup','').replace('_','-')):
        raise RuntimeError('Exact selected fractiond Pod/CID/PID/cgroup custody required')


def render_fixture(template,suffix,args,gpu=None):
    body=copy.deepcopy(template)
    body['metadata']['name']='nri-hotfix-'+suffix
    body['metadata']['labels']={'cps.unileoben.ac.at/extended-probe':'nri-hotfix-qualified'}
    body['spec']['nodeName']=args.node
    if 'annotations' in body['metadata']:
        body['metadata']['annotations']['nvidia.com/container.main.gpus.devices']='k8s.device-plugin.nvidia.com/gpu='+(gpu or args.gpu_a)
    return body


def run(args,stdin=None,timeout=30):
    return subprocess.check_output(args,input=stdin,text=True,timeout=timeout)

def write(name,data):
    (OUT/name).write_text(data if isinstance(data,str) else json.dumps(data,indent=2)+'\n')

def remote(code,*args):
    return run(ssh_command(ARGS)+['sudo python3 - '+shlex.join(list(args))],code)

def get(name):
    return json.loads(run(['kubectl','get','pod','-n',NS,name,'-o','json']))

def create(suffix,template='hung-pod.json',gpu=None):
    body=render_fixture(json.loads((OLD/template).read_text()),suffix,ARGS,gpu)
    name=body['metadata']['name']
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
    for gpu in (ARGS.gpu_a,ARGS.gpu_b):
        row=json.loads(remote(observer,'--node',ARGS.node,'--gpu-uuid',gpu))
        require_boot(row['boot_id'],ARGS.expected_boot_id)
        assert row['uvm']=={'srcversion':'10301D70B8ED1758BC717E9','parameters/uvm_reject_managed_memory':'Y','parameters/uvm_disable_hmm':'Y'}
        assert row['uvm_source_sha256']=='5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18'
        if idle:assert not row['compute_processes'],row
        rows.append(row)
    write(label+'-host.json',rows)
    identity=json.loads(remote('''import hashlib,json,pathlib,subprocess,platform
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
print(json.dumps({'kernel':platform.release(),'outer_sha256':sha('/usr/local/bin/k3s'),'data_current':str(pathlib.Path('/var/lib/rancher/k3s/data/current').resolve()),'processes':[{'pid':p,'executable':str(pathlib.Path('/proc/'+str(p)+'/exe').resolve()),'sha256':sha('/proc/'+str(p)+'/exe')} for p in [agent,containerd[0]]]}))
'''))
    assert identity['kernel']==KERNEL
    assert identity['outer_sha256']=='6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c'
    assert identity['data_current'].endswith('/2277a2c458beda093f8367b944c2fbb2e5f53a00f17776759721fb781b3874fa')
    assert all(p['sha256']=='0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a' for p in identity['processes'])
    write(label+'-runtime.json',identity)

def hang():
    pod=json.loads(run(['kubectl','get','pod','-n','gpu-fractioning',ARGS.fractiond_pod,'-o','json']))
    cid=validate_fractiond(pod,ARGS)
    identity=json.loads(remote('''import json,pathlib,subprocess,sys
b=json.loads(subprocess.check_output(['k3s','crictl','inspect',sys.argv[1]],text=True));p=int(b['info']['pid']);root=pathlib.Path('/proc/'+str(p));cmd=(root/'cmdline').read_bytes().split(b'\\0');assert cmd[0]==b'/fractiond',cmd
labels=b['status']['labels']
print(json.dumps({'container_id':b['status']['id'],'pod_uid':labels['io.kubernetes.pod.uid'],'pod_name':labels['io.kubernetes.pod.name'],'namespace':labels['io.kubernetes.pod.namespace'],'container_name':b['status']['metadata']['name'],'pid':p,'starttime':(root/'stat').read_text().rsplit(')',1)[1].split()[19],'cmdline':[x.decode() for x in cmd if x],'cgroup':(root/'cgroup').read_text()}))
''',cid))
    validate_fractiond_process(identity,ARGS,cid)
    pid=identity['pid'];start=identity['starttime'];unit='cps-nri-hotfix-cont-'+str(pid)
    identity.update(pod_uid=pod['metadata']['uid'],container_id=cid,unit=unit)
    write('fractiond-hang-identity.json',identity)
    write('resume-guard.py',GUARD)
    timer=['sudo','systemd-run','--unit='+unit,'--on-active=15s','--timer-property=AccuracySec=1us','--collect','/usr/bin/python3','-c',GUARD,str(pid),start]
    armed=False;snapshots=[];started=time.time()
    try:
        validate_node(json.loads(run(['kubectl','get','node',ARGS.node,'-o','json'])),ARGS)
        reject_gpu_consumers(json.loads(run(['kubectl','get','pods','-A','--field-selector','spec.nodeName='+ARGS.node,'-o','json']))['items'],ARGS)
        current=json.loads(run(['kubectl','get','pod','-n','gpu-fractioning',ARGS.fractiond_pod,'-o','json']))
        if validate_fractiond(current,ARGS)!=cid:raise RuntimeError('Fractiond container changed before STOP')
        run(ssh_command(ARGS)+[shlex.join(timer)])
        assert run(ssh_command(ARGS)+['sudo systemctl is-active '+unit+'.timer']).strip()=='active'
        armed=True
        remote("import os,signal,pathlib;assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()=="+repr(ARGS.expected_boot_id)+";pid="+str(pid)+";fd=os.pidfd_open(pid);assert pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]=="+repr(start)+";signal.pidfd_send_signal(fd,signal.SIGSTOP);os.close(fd)")
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
            result=subprocess.run(ssh_command(ARGS)+[shlex.join(['sudo','python3','-c',GUARD,str(pid),start])],text=True,capture_output=True,timeout=20)
            write('final-resume.txt',result.stdout+result.stderr)
            assert result.returncode==0
            stopped=subprocess.run(ssh_command(ARGS)+['sudo systemctl stop '+unit+'.timer'],capture_output=True,text=True,timeout=20)
            timer_state=run(ssh_command(ARGS)+['sudo systemctl show '+unit+'.timer -p LoadState -p ActiveState'])
            write('timer-final-state.txt',timer_state)
            assert 'ActiveState=inactive' in timer_state,timer_state
            write('timer-journal.txt',run(ssh_command(ARGS)+['sudo journalctl -u '+unit+'.service --no-pager']))
            write('fractiond-journal.txt',run(['kubectl','logs','-n','gpu-fractioning',pod['metadata']['name'],'-c','fractiond','--since=3m']))
            write('agent-hang-journal.txt',run(ssh_command(ARGS)+['sudo journalctl -u k3s-agent --since=@'+str(int(started))+' --no-pager']))
        write('hung-summary.json',identity)
        for name in list(OWNED):delete(name)

def main():
    global OUT,ARGS
    ARGS=arguments()
    if not ARGS.ssh_key.is_file():raise RuntimeError('Explicit SSH key file must exist')
    OUT=ARGS.output
    fresh_output(OUT)
    summary={'status':'RUNNING','started_at':time.time(),'expected_boot_id':ARGS.expected_boot_id,
        'fractiond_pod':ARGS.fractiond_pod,'fractiond_pod_uid':ARGS.fractiond_pod_uid,
        'node':ARGS.node,'node_uid':ARGS.node_uid,'node_ip':ARGS.node_ip,'ssh_target':ARGS.ssh_target,
        'gpu_uuids':[ARGS.gpu_a,ARGS.gpu_b],'release_reference':ARGS.release_reference}
    try:
        node=json.loads(run(['kubectl','get','node',ARGS.node,'-o','json']))
        validate_node(node,ARGS)
        drivers=json.loads(run(['kubectl','get','pods','-n',NS,'--field-selector','spec.nodeName='+ARGS.node,'-o','json']))
        validate_driver_pods(drivers['items'],ARGS)
        write('driver-before.json',drivers)
        write('node-before.json',node)
        consumers=json.loads(run(['kubectl','get','pods','-A','--field-selector','spec.nodeName='+ARGS.node,'-o','json']))
        reject_gpu_consumers(consumers['items'],ARGS)
        write('selected-pods-before.json',consumers)
        host_snapshot('before')
        hang()
        summary['hang']='PASS'
        # Allow the released Fractioning reconnect loop to register before CUDA.
        time.sleep(12)
        for number,gpu in enumerate((ARGS.gpu_a,ARGS.gpu_b)):
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
        try:
            try:
                for name in list(OWNED):delete(name)
            finally:
                final_node=json.loads(run(['kubectl','get','node',ARGS.node,'-o','json']))
                validate_node(final_node,ARGS)
                write('node-after.json',final_node)
                final_boot=remote("from pathlib import Path;print(Path('/proc/sys/kernel/random/boot_id').read_text().strip())").strip()
                summary['final_boot_id']=final_boot
                require_boot(final_boot,ARGS.expected_boot_id)
        except BaseException as exc:
            summary.update(status='FAIL',final_check_error=repr(exc));raise
        finally:
            summary['finished_at']=time.time();write('summary.json',summary)

if __name__=='__main__':main()
