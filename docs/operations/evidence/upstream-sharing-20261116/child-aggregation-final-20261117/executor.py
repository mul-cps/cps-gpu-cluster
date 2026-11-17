#!/usr/bin/env python3
"""Exact historical child probe; render by default, execute only on root-released GPU2."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from types import SimpleNamespace
import uuid
import yaml

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / 'docs/operations/evidence/upstream-sharing-20261116'
HARDWARE = ROOT / 'tests/upstream-sharing/hardware'
PROBE_SHA = '88c81166cfe2aa44c6a8e932ff81468e9e3f870054b8c9349c3a044b16b72b8f'
IMAGE = 'ghcr.io/mul-cps/cps-ubuntu-release-upgrade@sha256:5030556ecf8cd38fc9acc4676316bd0a3217d1ab10930b75b9dba7106e8f4004'
GPUS = ['GPU-16128952-b438-556a-00bb-93039ee24e56', 'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6']
NS = 'gpu-operator'
KUBE = ['kubectl', '--request-timeout=15s']


def command(args, *, data=None, timeout=30):
    return subprocess.check_output(args, input=data, text=True, stderr=subprocess.STDOUT, timeout=timeout)


def render(name):
    probe = (BASE / 'child-aggregation/probe.py').read_text()
    if hashlib.sha256(probe.encode()).hexdigest() != PROBE_SHA:
        raise RuntimeError('historical payload changed')
    cm = {'apiVersion':'v1', 'kind':'ConfigMap', 'metadata':{'name':name,'namespace':NS},
          'immutable':True, 'data':{'probe.py':probe}}
    pods = []
    for i, gpu in enumerate(GPUS):
        pod = yaml.safe_load((BASE / 'child-aggregation/pod.yaml').read_text())
        pod['metadata']['name'] = name + '-' + str(i)
        pod['metadata']['labels'] = {'cps.unileoben.ac.at/child-final-run':name}
        pod['metadata']['annotations']['nvidia.com/container.main.gpus.devices'] = 'k8s.device-plugin.nvidia.com/gpu=' + gpu
        pod['spec']['activeDeadlineSeconds'] = 240
        pod['spec']['volumes'][0]['configMap']['name'] = name
        pod['spec']['containers'][0]['command'] = ['python3','-c','import time; time.sleep(210)']
        if pod['spec']['containers'][0]['image'] != IMAGE:
            raise RuntimeError('historical image changed')
        pods.append(pod)
    return cm, pods


def validate_limits(text, leaf, gpu):
    if (gpu not in text or not re.search(r'^\s*namespace:\s*'+re.escape('/sys/fs/cgroup'+leaf)+r'\s*$', text, re.M)
            or not all(re.search(r'^\s*'+kind+r' limit:\s*5120 MiB\s*$', text, re.M) for kind in ('soft','hard'))):
        raise RuntimeError('exact selected GPU/cgroup 5120MiB limits not observed')


def delete_owned(kind, name, uid, call=command):
    if not uid:
        raise RuntimeError('unknown CREATE custody; reconcile without adopting')
    current = json.loads(call(KUBE + ['get', kind, name, '-n', NS, '-o', 'json']))
    if current['metadata']['uid'] != uid:
        raise RuntimeError('replacement object retained; refusing delete')
    opts = {'apiVersion':'v1','kind':'DeleteOptions','gracePeriodSeconds':15,
            'preconditions':{'uid':uid,'resourceVersion':current['metadata']['resourceVersion']}}
    call(KUBE + ['delete','--raw',f'/api/v1/namespaces/{NS}/{kind}/{name}','-f','-'], data=json.dumps(opts))
    call(KUBE + ['wait','--for=delete',kind+'/'+name,'-n',NS,'--timeout=45s'], timeout=50)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--run-id', default='child-final-' + uuid.uuid4().hex[:10])
    parser.add_argument('--expected-boot-id', required=True)
    parser.add_argument('--ssh-key', type=Path, default=Path('/home/bjoern/.ssh/id_ed25519'))
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--release-reference')
    args = parser.parse_args()
    uuid.UUID(args.expected_boot_id)
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,42}', args.run_id):
        parser.error('bounded unique run ID required')
    if args.execute and not args.release_reference:
        parser.error('explicit root idle-window release required')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (out/name).write_text(value if isinstance(value, str) else json.dumps(value, indent=2)+'\n')
    cm, pods = render(args.run_id)
    save('configmap.json', cm)
    for i, pod in enumerate(pods): save(f'pod-{i}.json', pod)
    save('probe.py', cm['data']['probe.py'])
    summary = {'status':'prepared-only', 'run_id':args.run_id,'probe_sha256':PROBE_SHA,
               'executor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'image':IMAGE,'gpu_uuids':GPUS,'expected_boot_id':args.expected_boot_id,
               'release_reference':args.release_reference,'cards':[], 'ambiguous_creates':[]}
    save('summary.json', summary)
    if not args.execute:
        print('Prepared only; no kubectl or SSH calls: '+str(out)); return
    os.chdir(ROOT)
    # Import read-only validation helpers only. Never call main/hang/STOP functions.
    spec = importlib.util.spec_from_file_location('nri_identity_only', HARDWARE/'nri_candidate_hotfix.py')
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    guard.ARGS = SimpleNamespace(node='k3s-wk-gpu2',node_uid='3336cdd5-d245-436e-b57c-2f66c6dcaa41',
        node_ip='10.21.0.43',expected_boot_id=args.expected_boot_id,gpu_a=GPUS[0],gpu_b=GPUS[1],
        ssh_target='ubuntu@10.21.0.43',ssh_key=args.ssh_key)
    guard.OUT = out
    def get(*words): return json.loads(command(KUBE+['get',*words,'-o','json']))
    def observer(gpu, cid=None, retired=None):
        words = ['--node','k3s-wk-gpu2','--gpu-uuid',gpu]
        if cid: words += ['--container-id',cid]
        if retired: words += ['--retired-cgroup',retired]
        return json.loads(guard.remote((HARDWARE/'extended_host_observer.py').read_text(),*words))
    def idle(label):
        node = get('node','k3s-wk-gpu2'); guard.validate_node(node,guard.ARGS)
        driver = get('pods','-n',NS,'--field-selector','spec.nodeName=k3s-wk-gpu2')
        guard.validate_driver_pods(driver['items'],guard.ARGS)
        consumers = get('pods','-A','--field-selector','spec.nodeName=k3s-wk-gpu2')
        guard.reject_gpu_consumers(consumers['items'],guard.ARGS)
        guard.host_snapshot(label)
        rows = json.loads((out/(label+'-host.json')).read_text())
        if any(int(row['gpu'].split(',')[2].strip())>1 for row in rows):
            raise RuntimeError('physical baseline exceeds 1MiB')
        save(label+'-node.json',node)
        save(label+'-driver.json',[{'metadata':p['metadata'], 'images':[c['image'] for c in p['spec']['containers']],
             'status':p['status']} for p in driver['items'] if any(c['name']=='nvidia-driver-ctr' for c in p['spec']['containers'])])
    owned = {}; retired_leaves = {}; cm_uid = None
    def create(obj, kind):
        name = obj['metadata']['name']
        try:
            result = json.loads(command(KUBE+['create','-f','-','-o','json'],data=json.dumps(obj)))
            uid = result['metadata']['uid']
        except Exception:
            summary['ambiguous_creates'].append({'kind':kind,'name':name})
            save('summary.json',summary)
            raise
        # Record custody before any evidence I/O that might fail.
        owned[(kind,name)] = uid
        save('created-'+name+'.json',result)
        return uid
    def interrupted(signum, frame): raise RuntimeError('executor interrupted; exact-owned cleanup required')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    summary['status']='RUNNING'; summary['started_at']=time.time()
    try:
        idle('before')
        cm_uid=create(cm,'configmaps')
        for i,pod in enumerate(pods):
            if i: idle('before-card-'+str(i))
            name=pod['metadata']['name']; gpu=GPUS[i]
            uid=create(pod,'pods')
            command(KUBE+['wait','--for=condition=Ready','pod/'+name,'-n',NS,'--timeout=60s'],timeout=65)
            current=get('pod',name,'-n',NS)
            if current['metadata']['uid']!=uid or current['spec']['nodeName']!='k3s-wk-gpu2':
                raise RuntimeError('Pod UID/node changed')
            status=current['status']['containerStatuses'][0]
            if status.get('restartCount')!=0 or 'running' not in status.get('state',{}):
                raise RuntimeError('unexpected container lifecycle')
            cid=status['containerID'].removeprefix('containerd://')
            identity=observer(gpu,cid=cid); save(f'card-{i}-identity.json',identity)
            leaf=identity['cgroup'].strip().split(':',2)[2]
            retired_leaves[gpu]=leaf
            limits=guard.remote('''import os,subprocess,sys
x=dict(os.environ,LD_LIBRARY_PATH='/run/nvidia/driver/usr/lib/x86_64-linux-gnu:/run/nvidia/driver/usr/lib64')
print(subprocess.check_output(['/run/nvidia/driver/usr/bin/nvidia-smi','memory-limits','--get','-n','/sys/fs/cgroup'+sys.argv[1],'-i',sys.argv[2]],env=x,text=True,timeout=12))
''',leaf,gpu)
            save(f'card-{i}-limits.txt',limits)
            validate_limits(limits,leaf,gpu)
            # Preserve the exact tool readback; the probe independently asserts the hard aggregate.
            save(f'card-{i}-pod-before.json',current)
            try:
                output=command(KUBE+['exec','-n',NS,name,'-c','main','--','python3','-u','/probe/probe.py'],timeout=75)
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
                text=e.output or ''; save(f'card-{i}-probe.log',text.decode() if isinstance(text,bytes) else text); raise
            save(f'card-{i}-probe.log',output)
            if 'CHILD_AGGREGATION_AND_ENV_BYPASS_PROBE_PASSED' not in output or 'nested-cgroup-creation-rejected' not in output:
                raise RuntimeError('missing parent completion witness')
            current=get('pod',name,'-n',NS); save(f'card-{i}-pod-after.json',current)
            if current['metadata']['uid']!=uid or current['status']['containerStatuses'][0]['containerID']!='containerd://'+cid:
                raise RuntimeError('post-exec identity changed')
            delete_owned('pods',name,uid); del owned[('pods',name)]
            deadline=time.monotonic()+25
            while True:
                after=observer(gpu,retired=leaf); save(f'card-{i}-after.json',after)
                if not after['retired_cgroup_exists'] and not after['compute_processes'] and int(after['gpu'].split(',')[2].strip())<=1: break
                if time.monotonic()>deadline: raise RuntimeError('retired cgroup/physical charge did not return')
                time.sleep(1)
            summary['cards'].append({'gpu_uuid':gpu,'pod_uid':uid,'container_id':cid,'retired_cgroup':leaf,
                                      'status':'PASS','finished_at':time.time()})
            save('summary.json',summary)
        idle('after')
        summary['status']='PASS'
    except Exception as e:
        summary['status']='FAIL';summary['error']=str(e)
        raise
    finally:
        errors=[]
        for (kind,name),uid in sorted(list(owned.items()), key=lambda item: item[0][0]!='pods'):
            try: delete_owned(kind,name,uid); del owned[(kind,name)]
            except Exception as e: errors.append({'kind':kind,'name':name,'uid':uid,'error':str(e)})
        if not errors and not summary['ambiguous_creates']:
            try:
                for gpu,leaf in retired_leaves.items():
                    row=observer(gpu,retired=leaf)
                    save('final-retired-'+str(GPUS.index(gpu))+'.json',row)
                    if row['retired_cgroup_exists'] or row['compute_processes'] or int(row['gpu'].split(',')[2].strip())>1:
                        raise RuntimeError('final physical/cgroup cleanup not confirmed')
                idle('final-cleanup')
            except Exception as e: errors.append({'verification_error':str(e)})
        summary['cleanup_errors']=errors
        summary['remaining_owned']=[{'kind':k[0],'name':k[1],'uid':v} for k,v in owned.items()]
        summary['finished_at']=time.time()
        if errors or summary['ambiguous_creates']:summary['status']='FAIL'
        save('summary.json',summary)
        if errors: raise RuntimeError('cleanup incomplete: '+str(errors))
    print(json.dumps(summary))

if __name__=='__main__': main()
