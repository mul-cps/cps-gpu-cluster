#!/usr/bin/env python3
"""GPU2-only bounded admin fixture. Run only in the root-released idle window."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent
IMAGE = 'ghcr.io/mul-cps/cps-ubuntu-release-upgrade@sha256:5030556ecf8cd38fc9acc4676316bd0a3217d1ab10930b75b9dba7106e8f4004'
GPUS = ['GPU-16128952-b438-556a-00bb-93039ee24e56', 'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6']
SSH = ['ssh', '-i', '/home/bjoern/.ssh/id_ed25519', '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', 'ubuntu@10.21.0.43']

def output(args, **kw):
    return subprocess.check_output(args, text=True, timeout=30, **kw)

def observe(gpu, container=None):
    cmd = 'sudo python3 - --node k3s-wk-gpu2 --gpu-uuid ' + gpu
    if container:
        cmd += ' --container-id ' + container
    data = json.loads(output(SSH + [cmd], input=(HERE/'extended_host_observer.py').read_text()))
    assert data['boot_id'] == 'a39cdade-f00d-4cd1-9a81-c290d668194f'
    assert data['uvm']['srcversion'] == '10301D70B8ED1758BC717E9'
    assert data['uvm']['parameters/uvm_reject_managed_memory'] == 'Y'
    assert data['uvm']['parameters/uvm_disable_hmm'] == 'Y'
    assert data['uvm_source_sha256'] == '5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18'
    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    def save(name, data):
        (args.output/name).write_text(json.dumps(data, indent=2))
    probe = (HERE/'kernel_peer_probe.py').read_text()
    name = 'kernel-peer-' + uuid.uuid4().hex[:10]
    pod = {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'gpu-operator'},
           'spec':{'nodeName':'k3s-wk-gpu2','runtimeClassName':'nvidia','restartPolicy':'Never',
            'activeDeadlineSeconds':240,'terminationGracePeriodSeconds':5,'automountServiceAccountToken':False,
            'imagePullSecrets':[{'name':'cps-native-image-pull'}],
            'securityContext':{'runAsUser':1000,'runAsGroup':1000,'runAsNonRoot':True,
              'seccompProfile':{'type':'RuntimeDefault'},'appArmorProfile':{'type':'RuntimeDefault'}},
            'containers':[{'name':'main','image':IMAGE,'command':['python3','-c','import time;time.sleep(220)'],
              'env':[{'name':'NVIDIA_DRIVER_CAPABILITIES','value':'compute,utility'}],
              'resources':{'requests':{'cpu':'100m','memory':'128Mi','nvidia.com/gpu':2},
                'limits':{'cpu':'2','memory':'1Gi','nvidia.com/gpu':2}},
              'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}
    save('pod.json', pod)
    (args.output/'probe.py').write_text(probe)
    save('source-sha256.json', {f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                              for f in [HERE/'kernel_peer_probe.py', HERE/'kernel_peer_run.py', HERE/'extended_host_observer.py']})
    if not args.execute:
        return
    before = [observe(g) for g in GPUS]
    assert all(not x['compute_processes'] and int(x['gpu'].split(',')[2]) <= 64 for x in before)
    save('host-before.json', before)
    pods = json.loads(output(['kubectl','get','pods','-n','gpu-operator','--field-selector=spec.nodeName=k3s-wk-gpu2','-o','json']))
    driver = next(x for x in pods['items'] if x['metadata']['name'].startswith('nvidia-gpu-driver-'))
    assert driver['metadata']['uid'] == 'dfd0cc7a-1e57-476f-a90c-50b4f09b70c4'
    assert driver['spec']['containers'][0]['image'].endswith('@sha256:c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73')
    save('driver.json', {'name':driver['metadata']['name'],'uid':driver['metadata']['uid'],
                        'containers':driver['status']['containerStatuses']})
    owned = json.loads(output(['kubectl','create','-f',str(args.output/'pod.json'),'-o','json']))
    uid = owned['metadata']['uid']
    summary = {'status':'running','pod_uid':uid,'driver_uid':driver['metadata']['uid']}
    try:
        output(['kubectl','wait','--for=condition=Ready','pod/'+name,'-n','gpu-operator','--timeout=60s'])
        live = json.loads(output(['kubectl','get','pod',name,'-n','gpu-operator','-o','json']))
        assert live['metadata']['uid'] == uid and live['spec']['nodeName'] == 'k3s-wk-gpu2'
        save('pod-live.json', live)
        container = live['status']['containerStatuses'][0]['containerID'].removeprefix('containerd://')
        save('host-container.json', observe(GPUS[0], container))
        result = subprocess.run(['kubectl','exec','-i','-n','gpu-operator',name,'--','python3','-u','-'],
                                input=probe,text=True,capture_output=True,timeout=90)
        (args.output/'probe.jsonl').write_text(result.stdout)
        (args.output/'stderr.txt').write_text(result.stderr)
        assert result.returncode == 0, result.stderr + result.stdout[-2000:]
        events = [json.loads(x) for x in result.stdout.splitlines()]
        assert events[-1]['step'] == 'all-passed'
        summary.update(status='PASS',results=[x for x in events if x['step'] in
             ('kernel-reference-pass','peer-capability','direct-peer-copy-and-kernel-mapping-pass',
              'direct-peer-UNSUPPORTED','host-staged-copy-pass')])
    except BaseException as error:
        summary.update(status='FAIL',error=str(error))
        raise
    finally:
        save('summary.json', summary)
        live = json.loads(output(['kubectl','get','pod',name,'-n','gpu-operator','-o','json']))
        assert live['metadata']['uid'] == uid
        options = {'apiVersion':'v1','kind':'DeleteOptions','gracePeriodSeconds':5,
                   'preconditions':{'uid':uid,'resourceVersion':live['metadata']['resourceVersion']}}
        save('delete.json', options)
        output(['kubectl','delete','--raw','/api/v1/namespaces/gpu-operator/pods/'+name,
                '-f',str(args.output/'delete.json')])
        output(['kubectl','wait','--for=delete','pod/'+name,'-n','gpu-operator','--timeout=25s'])
        deadline = time.monotonic()+20
        while True:
            after = [observe(g) for g in GPUS]
            if all(not x['compute_processes'] and int(x['gpu'].split(',')[2]) <= 64 for x in after):
                break
            if time.monotonic() > deadline:
                raise RuntimeError('GPU cleanup did not converge')
            time.sleep(1)
        save('host-after.json', after)
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
