"""Private host preflight/execution/readback for two existing approved CPS groups."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BASE_ROOT = Path('/home/bjoern/.local/state/cps-full-project-20261013')
PRIVATE = Path('/home/bjoern/.local/state/cps-concurrent-source5-20261014')
HOST_SHA = 'b3a08f0ab9ef5ee0d399802f442e30b897bbeaea09ade1d49d91f9054e1de905'

spec = importlib.util.spec_from_file_location('pair', HERE/'pair.py')
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)


def original_host():
    path = BASE_ROOT/'run-normal-source-gpu-acceptance.py'
    pair.require(hashlib.sha256(path.read_bytes()).hexdigest() == HOST_SHA, 'reviewed-host-wrapper-changed')
    spec = importlib.util.spec_from_file_location('original_host', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_root():
    try:
        PRIVATE.mkdir(mode=0o700)
    except FileExistsError:
        pass
    st = PRIVATE.lstat()
    pair.require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid()
                 and stat.S_IMODE(st.st_mode) == 0o700, 'owned-private-output-root-required')


def get(kind, name, namespace=None):
    command = ['kubectl', '--request-timeout=15s', 'get', kind, name, '-o', 'json']
    if namespace:
        command += ['-n', namespace]
    result = subprocess.run(command, capture_output=True, timeout=30)
    pair.require(result.returncode == 0, 'read-only-resource-capture-failed')
    return json.loads(result.stdout)


NATIVE_READER = r'''
import json,os,pathlib,stat,sys
r=json.load(sys.stdin);pool=r['pool'];root=pathlib.Path('/host/proc/driver/nvidia/gpus')
selected=[]
for d in root.iterdir():
 info=(d/'information').read_text()
 if [x.split(':',1)[1].strip() for x in info.splitlines() if x.startswith('GPU UUID:')]==[pool['gpu_uuid']]:selected.append(d)
assert len(selected)==1
fd=os.open(selected[0]/'cps_native_caps',os.O_RDONLY|os.O_NOFOLLOW)
with os.fdopen(fd,'rb') as stream:
 st=os.fstat(stream.fileno());assert st.st_uid==0 and st.st_gid==0 and stat.S_IMODE(st.st_mode)==0o400 and st.st_nlink==1
 raw=stream.read(262145);assert len(raw)<=262144
inventory=json.loads(raw);assert inventory['gpu_uuid']==pool['gpu_uuid']
epoch={'boot_id':pathlib.Path('/host/proc/sys/kernel/random/boot_id').read_text().strip(),
 'driver_generation':pathlib.Path('/run/cps-native-gpu/authority/driver-generation').read_text().strip()}
assert all(epoch[k]==pool[k] for k in epoch)
records={}
for name,uid in r.get('targets',{}).items():
 p=pathlib.Path('/run/cps-native-gpu/journal')/(uid+'.json')
 st=p.lstat();assert stat.S_ISREG(st.st_mode) and st.st_uid==0 and not(st.st_mode&0o077)
 record=json.loads(p.read_bytes());assert record['intent']['pod_uid']==uid and record['identity']['pod_uid']==uid
 assert record['intent']['namespace']=='jupyterhub' and record['intent']['name']=='jupyter-cpsnativegroup'+name[-1]+'--rtc'
 assert all(record['identity'][k]==pool[k] for k in ('node_uid','gpu_uuid','boot_id','driver_generation'))
 records[name]=record
previous={}
for name,uid in r.get('previous',{}).items():
 p=pathlib.Path('/run/cps-native-gpu/journal')/(uid+'.json');record=json.loads(p.read_bytes())
 assert record['intent']['pod_uid']==uid and record['state']=='retired-inert-cap'
 previous[name]=record
print(json.dumps({'inventory':inventory,'epoch':epoch,'records':records,'previous':previous},sort_keys=True))
'''


def native_read(pool, targets=None, previous=None):
    launcher = 'import io,json,sys;v=json.load(sys.stdin);sys.stdin=io.StringIO(json.dumps(v["request"]));exec(compile(v["code"],"readonly-native-pair","exec"),{"__name__":"__main__"})'
    result = subprocess.run(['kubectl','--request-timeout=15s','-n','cps-native-system','exec','-i',
        'deployment/cps-native-node-agent','-c','node-agent','--','python3','-c',launcher],
        input=json.dumps({'code':NATIVE_READER,'request':{'pool':pool,'targets':targets or {},'previous':previous or {}}}).encode(),
        capture_output=True,timeout=30)
    pair.require(result.returncode == 0, 'protected-native-readback-refused')
    return json.loads(result.stdout)


def capacity_snapshot():
    deploy = get('deployment','cps-native-node-agent','cps-native-system')
    config_names = [v['configMap']['name'] for v in deploy['spec']['template']['spec']['volumes']
                    if 'configMap' in v and v['name'] == 'config']
    pair.require(len(config_names) == 1, 'one-native-node-configuration-required')
    cm = get('configmap',config_names[0],'cps-native-system')
    config = json.loads(cm['data']['config.json'])
    pool = config['pool']
    node = get('node',pool['node'])
    pair.require(node['metadata']['uid'] == pool['node_uid'] and node['spec'].get('unschedulable') is True,
                 'unchanged-cordoned-GPU2-required')
    observed = native_read(pool)
    entries = observed['inventory']['entries']
    components={}
    for name,namespace in (('cps-admin','cps-compute'),('compute-gateway','cps-compute'),
                            ('hub','jupyterhub'),('cps-native-node-agent','cps-native-system')):
        d = get('deployment',name,namespace)
        pair.require(d['status'].get('readyReplicas') == 1, 'one-ready-component-required')
        components[namespace+'/'+name]={'uid':d['metadata']['uid'],
            'images':[c['image'] for c in d['spec']['template']['spec']['containers']]}
    return {'pool':pool,'policy_hash':config['policy_hash'],'epoch':observed['epoch'],
        'active_native_entries':sum(not e['offline'] for e in entries),
        'native_used_bytes':sum(e['used'] for e in entries),
        'config_uid':cm['metadata']['uid'],'config_sha256':hashlib.sha256(cm['data']['config.json'].encode()).hexdigest(),
        'inventory_sha256':hashlib.sha256(json.dumps(observed['inventory'],sort_keys=True).encode()).hexdigest(),
        'components':components}


def bundle(capacity):
    baseline=(BASE_ROOT/'normal-source-gpu-acceptance.py').read_text()
    pair.require(hashlib.sha256(baseline.encode()).hexdigest()==pair.BASELINE_SHA256,'reviewed-baseline-source-changed')
    return 'BASELINE_CODE='+repr(baseline)+'\nCAPACITY='+repr(capacity)+'\n'+(HERE/'pair.py').read_text()


def read_private(path):
    st=path.lstat()
    pair.require(path.parent == PRIVATE and stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid()
                 and stat.S_IMODE(st.st_mode)==0o600,'private-evidence-input-required')
    return json.loads(path.read_bytes())


def main(args):
    private_root()
    host=original_host()
    capacity=capacity_snapshot()
    code=bundle(capacity)
    if args.mode=='plan':
        result=subprocess.run(host.command(),input=host.canonical({'code':code,'args':['plan']}),capture_output=True,timeout=120)
        path=PRIVATE/('pair-plan-'+str(time.time_ns())+'.json')
        if result.returncode:
            host.write(path,host.canonical({'returncode':result.returncode,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')}))
            print(json.dumps({'plan_failed':True,'private_diagnostic':str(path)}));return 1
        document=json.loads(result.stdout);plan=document['plan']
        pair.require(hashlib.sha256(host.canonical(plan)).hexdigest()==document['plan_sha256'],'plan-self-hash-differs')
        host.write(path,host.canonical(plan))
        host.write(path.with_suffix('.metadata.json'),host.canonical({'plan_sha256':document['plan_sha256'],
                    'script_sha256':hashlib.sha256(code.encode()).hexdigest()}))
        print(json.dumps({'plan':str(path),'plan_sha256':document['plan_sha256'],'execute_before':plan['execute_before'],
                          'workspaces':list(pair.TARGETS),'canonical_overlap_count':0,'hold_seconds':pair.HOLD_SECONDS}));return 0
    pair.require(bool(args.plan) and bool(args.plan_sha256),'explicit-reviewed-plan-and-hash-required')
    path=Path(args.plan);plan=read_private(path);meta=read_private(path.with_suffix('.metadata.json'))
    pair.require(hashlib.sha256(host.canonical(plan)).hexdigest()==args.plan_sha256==meta['plan_sha256'], 'reviewed-plan-changed')
    pair.require(meta['script_sha256']==hashlib.sha256(code.encode()).hexdigest(),'reviewed-code-or-capacity-changed')
    output=PRIVATE/('pair-execution-'+plan['run_id']+'.jsonl')
    error=PRIVATE/('pair-execution-'+plan['run_id']+'.stderr')
    outfd=os.open(output,os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600)
    errfd=os.open(error,os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600)
    with os.fdopen(outfd,'wb') as saved,os.fdopen(errfd,'wb') as errors:
        process=subprocess.Popen(host.command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors)
        process.stdin.write(host.canonical({'code':code,'args':['execute','--plan-sha256',args.plan_sha256],'plan':plan}))
        process.stdin.close()
        for line in process.stdout:
            saved.write(line);saved.flush()
            try:item=json.loads(line)
            except ValueError:continue
            keys=('stage','run_id','private_directory','hold_seconds','ready','confirmed_shutdown','reservation_released',
                  'restored_windows','restored_hub_group','lifecycle_passed','hardware_cap_qualified','both_ready','workspace_results',
                  'failure_type','failure_code','workspace_failure_codes')
            print(json.dumps({k:item[k] for k in keys if k in item}),flush=True)
        result=process.wait()
    print(json.dumps({'returncode':result,'private_output':str(output),'private_errors':str(error)}));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('plan','execute'))
    parser.add_argument('--plan');parser.add_argument('--plan-sha256')
    try:raise SystemExit(main(parser.parse_args()))
    except Exception as error:
        print(json.dumps({'failed':True,'failure_type':type(error).__name__,'failure_code':str(error) if type(error) is RuntimeError else 'private-preflight-failed'}),file=sys.stderr)
        raise SystemExit(1)
