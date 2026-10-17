"""Default-inert binding of existing frozen IPC endpoints to one approved Pod.
Two actual notebook processes; no kernel witness/driver changes or cross-Pod claim.
"""
import argparse,hashlib,importlib.util,json,os,pathlib,stat,subprocess,sys,uuid
BASE=pathlib.Path('/home/bjoern/.local/state/cps-group-native-20261009/group-probes/imports-cross-pod')
RUN_PIN='ee8772c7caa0ba5eceaba18b4b8a3c7373ab35ac67b9426384513f1998570c87'
ENDPOINT_PIN='0faa5fddc8db4e81b4cc49784cf6eb5933c1cb95366ea0218c9b367e6c2a9aad'
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
LAB='jupyter-cps-ws-27c474f74f9d41c53eac0be01fcca8a3--rtc'
NODE_READ=r'''import sys,json,pathlib
from cps_compute.native_gpu_controller import CapRecord
from cps_compute.native_node.backend import private_read
from cps_compute.native_node.nvml import Nvml
uid=sys.argv[1];r=CapRecord.from_dict(private_read(pathlib.Path('/run/cps-native-gpu/journal')/(uid+'.json')))
assert r.intent.pod_uid==uid and r.intent.cap_mib==5120 and r.state=='sealed' and r.readback==r.limit
p=pathlib.Path('/sys/fs/cgroup')/r.identity.cgroup_relative.lstrip('/');s=p.stat()
assert s.st_ino==r.identity.cgroup_inode and s.st_dev==r.identity.cgroup_device
n=Nvml()
try:
 v=n.get(r.intent.gpu_uuid,p);assert v['soft']==v['hard']==5368709120 and 0<=v['used']<=5368709120
 print(json.dumps({'record':r.to_dict(),'limits':v}))
finally:n.close()
'''
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
 for name in ('pod-name','pod-uid','node-pod','node-uid','output'):parser.add_argument('--'+name)
 args=parser.parse_args(argv)
 if not args.execute:
  print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'scope':'distinct-process same-Pod IPC positive only','production_qualified':False}));return 0
 assert args.pod_name==LAB and args.node_pod and args.output
 for uid in (args.pod_uid,args.node_uid):assert uid and str(uuid.UUID(uid))==uid and uuid.UUID(uid).int!=0
 endpoint=(BASE/'ipc_endpoint.py').read_bytes();source=(BASE/'run_cross_pod.py').read_bytes()
 assert hashlib.sha256(endpoint).hexdigest()==ENDPOINT_PIN and hashlib.sha256(source).hexdigest()==RUN_PIN
 output=pathlib.Path(args.output);parent=output.parent.stat();assert parent.st_uid==os.getuid() and stat.S_IMODE(parent.st_mode)==0o700
 output.mkdir(mode=0o700);os.umask(0o077)
 def save(name,value):(output/name).write_text(json.dumps(value,sort_keys=True)+'\n')
 def call(argv,stdin=None,timeout=30):
  p=subprocess.run(['kubectl',*argv],input=stdin,text=True,capture_output=True,timeout=timeout)
  assert p.returncode==0,p.stderr;return json.loads(p.stdout)
 def preflight():
  p=call(['-n','jupyterhub','get','pod',args.pod_name,'-o','json']);n=call(['-n','cps-native-system','get','pod',args.node_pod,'-o','json'])
  assert p['metadata']['uid']==args.pod_uid and p['status']['phase']=='Running' and not p['metadata'].get('deletionTimestamp')
  assert p['spec']['nodeName']=='k3s-wk-gpu2' and all(c['ready'] and c['restartCount']==0 for c in p['status']['containerStatuses'])
  assert n['metadata']['uid']==args.node_uid and n['status']['phase']=='Running' and not n['metadata'].get('deletionTimestamp')
  assert next(c for c in p['spec']['containers'] if c['name']=='notebook')['image']=='ghcr.io/mul-cps/cps-jupyter-notebook:qualification-native-group-980408a@sha256:9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0'
  record=call(['-n','cps-native-system','exec','-i',args.node_pod,'-c','node-agent','--','python','-B','-',args.pod_uid],NODE_READ)
  assert record['record']['intent']['name']==args.pod_name and record['record']['intent']['gpu_uuid']==GPU
  assert record['record']['intent']['policy_hash']=='sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
  return record
 before=preflight();save('native-before.private.json',before)
 spec=importlib.util.spec_from_file_location('_frozen_ipc_session',BASE/'run_cross_pod.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
 target={'namespace':'jupyterhub','name':args.pod_name};trial=str(uuid.uuid4());sessions=[];complete=[]
 try:
  base=['--execute','--gpu-uuid',GPU,'--trial-id',trial]
  exporter=runner.Session(target,[*base,'--role','exporter'],endpoint,'exporter',output);sessions.append(exporter)
  handle=exporter.wait('handle-ready');exporter.wait('exporter-tick')
  preflight()
  importer=runner.Session(target,[*base,'--role','importer','--wait-for-root','--expect','allow','--handle-b64',handle['handle_b64']],endpoint,'importer',output);sessions.append(importer)
  ready=importer.wait('importer-ready');assert ready['namespace_pid']!=handle['namespace_pid'],'Distinct actual namespace PIDs required'
  importer.send('open',trial);events=importer.complete();complete.append('importer')
  def one(values,phase):
   matches=[v for v in values if v.get('phase')==phase and v.get('trial_id')==trial];assert len(matches)==1;return matches[0]
  imported=one(events,'import-result');assert imported['api']=='cuIpcOpenMemHandle_v2' and imported['cuda_result']==0
  assert imported['handle_sha256']==handle['handle_sha256'] and one(events,'same-parent-positive')['imported_byte']==19
  assert one(events,'importer-before-kernel')['kernel_byte']==11 and one(events,'importer-after-kernel')['kernel_byte']==17
  exporter.send('recover',trial);exporter.wait('exporter-recovery')
  exporter.wait_matching(lambda v:v.get('phase')=='exporter-tick' and v.get('monotonic_ns',0)>imported['call_ended_monotonic_ns'])
  exporter.send('finish',trial);exported=exporter.complete();complete.append('exporter')
  assert one(exported,'exporter-recovery')['recovery_byte']==37
  after=preflight();assert after['record']==before['record'];save('native-after.private.json',after)
  result={'passed':True,'scope':'two-distinct-processes-one-Pod IPC positive','pod_uid':args.pod_uid,'trial_id':trial,
   'namespace_pids':[handle['namespace_pid'],ready['namespace_pid']],'cuda_import_result':0,'imported_byte':19,
   'ordinary_kernels_before_after':True,'exporter_recovery':True,'both_endpoint_cleanup_receipts':True,
   'endpoint_source_sha256':ENDPOINT_PIN,'runner_source_sha256':RUN_PIN,
   'workload_image':'ghcr.io/mul-cps/cps-jupyter-notebook:qualification-native-group-980408a@sha256:9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0',
   'policy_hash':'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0',
   'cross_pod_isolation_qualified':False,'VMM_qualified':False,'production_qualified':False}
  save('receipt.json',result);print(json.dumps(result));return 0
 finally:
  failures=[]
  for session in reversed(sessions):
   try:session.abandon()
   except BaseException as error:failures.append(type(error).__name__)
  if failures:raise RuntimeError('Endpoint transport cleanup failure: '+','.join(failures))
if __name__=='__main__':raise SystemExit(main())
