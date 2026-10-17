"""GET-only fresh writer-stop / post-stop ACK+metadata fence CAS. Never applies."""
import argparse,copy,json,os,subprocess
from pathlib import Path
from publication import require,save,cas,volume,key

def get(kind,ns,name=None):return json.loads(subprocess.check_output(['kubectl','-n',ns,'get',kind]+([name] if name else [])+['-o','json'],timeout=30))
def withdraw_ack_patch(ack,target):
 from cps_compute.native_group_revision import NamedAcknowledgmentPublisher
 publisher=NamedAcknowledgmentPublisher(None,target,component='node')
 publisher._target(ack)
 # Empty RECEIPT, not an empty ConfigMap data map. The stable key is required.
 desired={'ack.json':'{}'}
 publisher._target({**ack,'data':desired})
 return cas(ack,'/data',desired)

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',action='store_true');p.add_argument('--stage',choices=['stop','poststop']);p.add_argument('--snapshot',type=Path);p.add_argument('--revision');p.add_argument('--output',type=Path);a=p.parse_args(argv)
 if not a.capture:print('{"inert":true,"live_writes":false}');return
 require(a.stage and a.snapshot and a.output and a.revision,'Explicit stage/current snapshot/revision required');snapshot=json.loads(a.snapshot.read_text());original=snapshot['deployments']['node'];ns=original['metadata']['namespace'];dep=get('deployment',ns,original['metadata']['name'])
 require(dep['metadata']['uid']==original['metadata']['uid'],'Node controller replaced')
 expected=copy.deepcopy(original['spec']);expected['replicas']=1 if a.stage=='stop' else 0
 require(dep['spec']==expected,'Node spec changed beyond expected replicas')
 ledger=get('configmap',ns,'cps-native-gpu-allocations');before=snapshot['objects'][key('configmap',ns,'cps-native-gpu-allocations')]
 require(ledger['metadata']['uid']==before['metadata']['uid'] and not ledger['metadata'].get('deletionTimestamp'),'Ledger replaced')
 claims=json.loads(ledger['data']['state.json'])['allocations'];require(all(x['state']=='released' for x in claims.values()),'Unreleased native lifetime remains')
 code="import sqlite3,json;c=sqlite3.connect('file:/data/reservations.sqlite?mode=ro',uri=True);c.execute('PRAGMA query_only=ON');print(json.dumps([c.execute('select count(*) from '+t).fetchone()[0] for t in ('reservation','reservation_binding')]));c.close()"
 counts=json.loads(subprocess.check_output(['kubectl','-n','cps-compute','exec','deployment/compute-gateway','-c','gateway','--','python','-c',code],timeout=30));require(counts==[0,0],'SQL reservations remain')
 for workload_ns in ('jupyterhub','cit-jhub'):
  pods=get('pods',workload_ns)['items'];names={c['name'] for c in claims.values() if c['namespace']==workload_ns}
  require(not any(pod['metadata']['name'] in names for pod in pods),'Existing native lifetime Pod remains')
 os.umask(0o077);a.output.mkdir(mode=0o700,exist_ok=False);save(a.output,'deployment.preimage.private.json',dep);save(a.output,'ledger.preimage.private.json',ledger)
 if a.stage=='stop':
  patch=cas(dep,'/spec',dep['spec'])[:3]+[{'op':'replace','path':'/spec/replicas','value':0}];save(a.output,'stop-node.patch.private.json',patch)
 else:
  labels=dep['spec']['selector']['matchLabels'];pods=get('pods',ns)['items'];require(not any(all(pod['metadata'].get('labels',{}).get(k)==v for k,v in labels.items()) for pod in pods),'Old Node Pod must be completely gone')
  bootstrap=volume(snapshot,'node','packaged-bootstrap-input');cfgref=json.loads(bootstrap['data']['config-ref.json']);cfg=json.loads(snapshot['objects'][key('configmap',cfgref['namespace'],cfgref['name'])]['data']['config.json']);target=cfg['acknowledgment_targets']['node'];ack=get('configmap',target['namespace'],target['name'])
  require(all(ack['metadata'][k]==v for k,v in target.items()) and not ack['metadata'].get('deletionTimestamp') and set(ack['data'])=={'ack.json'},'Exact own ACK target required')
  save(a.output,'ack.preimage.private.json',ack);save(a.output,'withdraw-ack.patch.private.json',withdraw_ack_patch(ack,target))
  annotations=copy.deepcopy(ledger['metadata'].get('annotations',{}));annotations['cps.compute/approval-publication']=a.revision
  patch=cas(ledger,'/data',ledger['data'])[:3]+[{'op':'add','path':'/metadata/annotations','value':annotations}];save(a.output,'ledger-metadata-barrier.patch.private.json',patch)
 save(a.output,'validation.private.json',{'stage':a.stage,'revision':a.revision,'released_claims':len(claims),'sql_counts':counts,'live_writes':False});print(json.dumps({'stage':a.stage,'released_claims':len(claims),'live_writes':False}))
if __name__=='__main__':main()
