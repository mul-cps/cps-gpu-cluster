#!/usr/bin/env python3
"""One 15-second SIGSTOP; independent systemd timer restores exact fractiond PID."""
import json
from pathlib import Path
import shlex
import subprocess
import time

OUT=Path('docs/operations/evidence/upstream-sharing-20261116/managed-policy-load/nri-candidate')
SSH=['ssh','-i','/home/bjoern/.ssh/id_ed25519','-o','IdentitiesOnly=yes','-o','BatchMode=yes','ubuntu@10.21.0.43']
NS='gpu-operator'
GUARD='''import os,signal,sys,time,json,pathlib
pid=int(sys.argv[1]);expected=sys.argv[2]
fd=os.pidfd_open(pid)
actual=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
assert actual==expected,(actual,expected)
signal.pidfd_send_signal(fd,signal.SIGCONT)
os.close(fd)
print(json.dumps({'action':'CONT','pid':pid,'starttime':actual,'time':time.time()}),flush=True)
'''

def run(args, **kw):
    return subprocess.check_output(args,text=True,timeout=30,**kw)

def main():
    pod=json.loads(run(['kubectl','get','pod','-n','gpu-fractioning','gpu-fractioning-fractiond-d7j6f','-o','json']))
    cid=next(x['containerID'] for x in pod['status']['containerStatuses'] if x['name']=='fractiond').removeprefix('containerd://')
    info=json.loads(run(SSH+['sudo k3s crictl inspect '+cid]));pid=info['info']['pid']
    start=run(SSH+['sudo python3 -c '+shlex.quote("from pathlib import Path; print(Path('/proc/"+str(pid)+"/stat').read_text().rsplit(')',1)[1].split()[19])")]).strip()
    unit='cps-nri-candidate-cont-'+str(pid)
    restore=['sudo','/usr/bin/python3','-c',GUARD,str(pid),start]
    timer=['sudo','systemd-run','--unit='+unit,'--on-active=15s','--timer-property=AccuracySec=1us','--collect','/usr/bin/python3','-c',GUARD,str(pid),start]
    (OUT/'resume-guard.py').write_text(GUARD)
    record={'pid':pid,'starttime':start,'container_id':cid,'pod_uid':pod['metadata']['uid'],'unit':unit}
    (OUT/'fractiond-hang-identity.json').write_text(json.dumps(record,indent=2))
    armed=False
    try:
        run(SSH+[shlex.join(timer)])
        assert run(SSH+['sudo systemctl is-active '+unit+'.timer']).strip()=='active'
        armed=True
        stop="import os,signal,pathlib;pid="+str(pid)+";fd=os.pidfd_open(pid);assert pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]=="+repr(start)+";signal.pidfd_send_signal(fd,signal.SIGSTOP);os.close(fd)"
        run(SSH+['sudo python3 -c '+shlex.quote(stop)])
        record['stopped_at']=time.time()
        for suffix in ['hung','hung-cpu']:
            created=run(['kubectl','create','-f',str(OUT/(suffix+'-pod.json')),'-o','json'])
            (OUT/(suffix+'-created.json')).write_text(created)
        snapshots=[]
        deadline=time.monotonic()+22
        while time.monotonic()<deadline:
            pods=json.loads(run(['kubectl','get','pods','-n',NS,'nri-candidate-hung','nri-candidate-hung-cpu','-o','json']))
            state=run(SSH+['sudo python3 -c '+shlex.quote("from pathlib import Path;print(Path('/proc/"+str(pid)+"/stat').read_text().rsplit(')',1)[1].split()[0])")]).strip()
            row={'time':time.time(),'fractiond_state':state,'pods':pods['items']};snapshots.append(row)
            (OUT/'hung-snapshots.json').write_text(json.dumps(snapshots,indent=2))
            if state=='T':
                gpu=next(x for x in row['pods'] if x['metadata']['name']=='nri-candidate-hung')
                assert all(not x.get('containerID') and not x.get('state',{}).get('running') and not x.get('state',{}).get('terminated') for x in gpu['status'].get('containerStatuses',[])), 'GPU started while plugin stopped'
            time.sleep(.5)
        (OUT/'timer-journal.txt').write_text(run(SSH+['sudo journalctl -u '+unit+'.service --no-pager']))
        rejected=[r for r in snapshots if r['fractiond_state']=='T' and 'required plugin \\"gpu-fractioning\\" not present' in json.dumps(r)]
        # Avoid escaping assumptions when inspecting the validator's string.
        rejected=[r for r in snapshots if r['fractiond_state']=='T' and any(
            'required plugin "gpu-fractioning" not present' in c.get('state',{}).get('waiting',{}).get('message','')
            for p in r['pods'] for c in p['status'].get('containerStatuses',[]))]
        assert rejected, 'No default-validator rejection observed during STOP'
        cpu_during=[r for r in snapshots if r['fractiond_state']=='T' and any(p['metadata']['name']=='nri-candidate-hung-cpu' and p['status']['phase']=='Succeeded' for p in r['pods'])]
        assert cpu_during, 'CPU success while plugin stopped not observed'
        record.update(status='PASS',validator_rejection_during_stop=True,cpu_success_during_stop=True)
    finally:
        if armed:
            # Timer normally already fired; exact-identity CONT is also safe here.
            result=subprocess.run(SSH+[shlex.join(restore)],text=True,capture_output=True,timeout=15)
            (OUT/'final-resume.txt').write_text(result.stdout+result.stderr)
            assert result.returncode==0
            subprocess.run(SSH+['sudo systemctl stop '+unit+'.timer'],capture_output=True,text=True,timeout=15)
            (OUT/'timers-final.txt').write_text(run(SSH+['sudo systemctl list-timers --all --no-pager']))
        (OUT/'hung-summary.json').write_text(json.dumps(record,indent=2))

if __name__=='__main__':main()
