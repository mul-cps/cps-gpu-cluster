#!/usr/bin/env python3
"""Post-hang recovery and final-binary restart continuity; no repeat STOP."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import nri_candidate_hotfix as q

def create(body,suffix):
    body=copy.deepcopy(body);name='nri-hotfix-'+suffix
    body['metadata']['name']=name
    body['metadata']['labels']={'cps.unileoben.ac.at/extended-probe':'nri-hotfix-qualified'}
    q.write(suffix+'-pod.json',body)
    result=json.loads(q.run(['kubectl','create','-f','-','-o','json'],json.dumps(body)))
    q.OWNED[name]=result['metadata']['uid'];q.write(suffix+'-created.json',result)
    return name

def identity(pod):
    return {'uid':pod['metadata']['uid'],'containers':[{k:c.get(k) for k in ['name','containerID','restartCount']} for c in pod['status'].get('containerStatuses',[])]}

def recovery():
    assert json.loads((q.OUT/'hung-summary.json').read_text())['status']=='PASS'
    q.host_snapshot('recovery-before')
    summary={'status':'RUNNING'}
    try:
        missing=json.loads((q.OLD/'hung-pod.json').read_text())
        missing['metadata']['annotations']['required-plugins.noderesource.dev/container.main']='["gpu-fractioning","cps-required-missing-final"]'
        name=create(missing,'missing')
        def reject(pod):
            q.no_exec(pod)
            return any('required plugin "cps-required-missing-final" not present' in c.get('state',{}).get('waiting',{}).get('message','') for c in pod['status'].get('containerStatuses',[]))
        result=q.wait(name,reject,30);q.write('missing-rejection.json',result)
        cpu=q.create('missing-cpu','hung-cpu-pod.json')
        q.wait(cpu,lambda p:p['status'].get('phase')=='Succeeded',30)
        q.write('missing-cpu.log',q.run(['kubectl','logs','-n',q.NS,cpu]))
        q.delete(name);q.delete(cpu)
        summary['missing_required_rejected_cpu_pass']=True
        for number,gpu in enumerate(q.GPUS):
            name=q.create('recovery-'+str(number),'recovery-pod.json',gpu)
            q.wait(name,lambda p:p['status'].get('phase')=='Succeeded',60)
            logs=q.run(['kubectl','logs','-n',q.NS,name]);q.write('recovery-'+str(number)+'.log',logs)
            assert 'RAW_DRIVER_LIMIT_AND_RECOVERY_PASSED' in logs
            q.delete(name)
        summary.update(status='PASS',recovery_cards=2)
        q.host_snapshot('recovery-after')
    except BaseException as exc:
        summary.update(status='FAIL',error=repr(exc));raise
    finally:
        for name in list(q.OWNED):q.delete(name)
        q.write('recovery-summary.json',summary)

def restart():
    assert json.loads((q.OUT/'recovery-summary.json').read_text())['status']=='PASS'
    q.host_snapshot('restart-before')
    summary={'status':'RUNNING'};submitted=False
    try:
        body=json.loads((q.OLD/'hung-pod.json').read_text())
        body['spec']['activeDeadlineSeconds']=240
        body['spec']['containers'][0]['command']=['python3','-u','-c',Path('tests/upstream-sharing/hardware/nri_candidate_probe.py').read_text()]
        gpu=create(body,'survivor')
        body=json.loads((q.OLD/'hung-cpu-pod.json').read_text())
        body['spec']['activeDeadlineSeconds']=240
        body['spec']['containers'][0]['command']=['python3','-u','-c','import time,json,pathlib\nend=time.monotonic()+180\nwhile time.monotonic()<end and not pathlib.Path("/tmp/release").exists():\n print(json.dumps({"cpu_progress":time.time()}),flush=True);time.sleep(1)\nprint("CPU_CONTINUITY_PASSED",flush=True)']
        cpu=create(body,'cpu-survivor')
        for name in [gpu,cpu]:q.wait(name,lambda p:p['status'].get('phase')=='Running',45)
        q.run(['kubectl','exec','-n',q.NS,gpu,'--','touch','/tmp/start'])
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            logs=q.run(['kubectl','logs','-n',q.NS,gpu])
            if 'progress-and-quota-pass' in logs:break
            time.sleep(.5)
        assert 'progress-and-quota-pass' in logs
        before={name:identity(q.get(name)) for name in [gpu,cpu]}
        q.write('restart-owned-before.json',before)
        before_all=json.loads(q.run(['kubectl','get','pods','-A','--field-selector=spec.nodeName=k3s-wk-gpu2','-o','json']))
        artifact_before={p['metadata']['namespace']+'/'+p['metadata']['name']:identity(p) for p in before_all['items'] if 'artifact-downloads' in p['metadata']['name']}
        q.write('artifact-downloads-before.json',artifact_before)
        q.write('survivor-before.log',logs)
        q.write('cpu-before.log',q.run(['kubectl','logs','-n',q.NS,cpu]))
        observer=Path('tests/upstream-sharing/hardware/extended_host_observer.py').read_text()
        cid=before[gpu]['containers'][0]['containerID'].removeprefix('containerd://')
        accounting=json.loads(q.remote(observer,'--node','k3s-wk-gpu2','--gpu-uuid',q.GPUS[0],'--container-id',cid))
        q.write('survivor-accounting-before.json',accounting)
        start=time.time();unit='cps-nri-hotfix-runtime-continuity'
        # Persist submission identity before calling host systemd. Lost replies
        # require reconciliation of this unit, never resubmission.
        q.write('restart-submission.json',{'unit':unit,'started_at':start,'status':'about to submit once'})
        result=subprocess.run(q.SSH+['sudo systemd-run --unit='+unit+' --property=Type=oneshot --property=RemainAfterExit=yes /bin/systemctl restart k3s-agent'],text=True,capture_output=True,timeout=30)
        q.write('restart-command.txt',result.stdout+result.stderr)
        submitted=True
        # Submission errors/unknown reply must be reconciled, not retried.
        assert result.returncode==0,result.stderr
        deadline=time.monotonic()+70
        while time.monotonic()<deadline:
            status=q.run(q.SSH+['sudo systemctl show '+unit+'.service -p ActiveState -p SubState -p ExecMainStatus'])
            q.write('restart-unit.txt',status)
            if 'SubState=exited' in status and 'ExecMainStatus=0' in status:break
            time.sleep(1)
        assert 'SubState=exited' in status and 'ExecMainStatus=0' in status,status
        time.sleep(12)
        after={name:identity(q.get(name)) for name in [gpu,cpu]}
        q.write('restart-owned-after.json',after);assert after==before,(before,after)
        after_logs=q.run(['kubectl','logs','-n',q.NS,gpu]);q.write('survivor-after.log',after_logs)
        progress=[json.loads(line) for line in after_logs.splitlines() if 'progress-and-quota-pass' in line]
        assert any(row['time']>start+4 for row in progress),'No post-restart CUDA progress'
        cpu_logs=q.run(['kubectl','logs','-n',q.NS,cpu]);q.write('cpu-after.log',cpu_logs)
        assert any(json.loads(line).get('cpu_progress',0)>start+4 for line in cpu_logs.splitlines()),'No post-restart CPU progress'
        accounting_after=json.loads(q.remote(observer,'--node','k3s-wk-gpu2','--gpu-uuid',q.GPUS[0],'--container-id',cid))
        q.write('survivor-accounting-after.json',accounting_after)
        for key in ['container_id','init_pid','cgroup','cgroup_inode']:assert accounting[key]==accounting_after[key],key
        assert accounting['accounting']['misc.max']==accounting_after['accounting']['misc.max']
        after_all=json.loads(q.run(['kubectl','get','pods','-A','--field-selector=spec.nodeName=k3s-wk-gpu2','-o','json']))
        artifact_after={p['metadata']['namespace']+'/'+p['metadata']['name']:identity(p) for p in after_all['items'] if 'artifact-downloads' in p['metadata']['name']}
        q.write('artifact-downloads-after.json',artifact_after);assert artifact_after==artifact_before
        q.write('fractiond-after-restart.log',q.run(['kubectl','logs','-n','gpu-fractioning','gpu-fractioning-fractiond-d7j6f','-c','fractiond','--since=3m']))
        q.write('agent-restart-journal.txt',q.run(q.SSH+['sudo journalctl -u k3s-agent --since=@'+str(int(start))+' --no-pager']))
        for name in [gpu,cpu]:
            q.run(['kubectl','exec','-n',q.NS,name,'--','touch','/tmp/release'])
            q.wait(name,lambda p:p['status'].get('phase')=='Succeeded',30)
            q.write(name+'-complete.log',q.run(['kubectl','logs','-n',q.NS,name]));q.delete(name)
        summary.update(status='PASS',same_pod_uid_cid_cgroup=True,cuda_quota_progress_after_restart=True,cpu_progress_after_restart=True,artifact_downloads_identity_unchanged=True,restart_unit=unit)
        q.host_snapshot('restart-after')
    except BaseException as exc:
        summary.update(status='FAIL',error=repr(exc),restart_submission_attempted=submitted);raise
    finally:
        for name in list(q.OWNED):q.delete(name)
        q.write('restart-summary.json',summary)

if __name__=='__main__':
    {'recovery':recovery,'restart':restart}[sys.argv[1]]()
