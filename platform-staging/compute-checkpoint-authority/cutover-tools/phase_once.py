"""One reviewed controller phase per invocation. No auto-sequence, retry or rollback."""
import argparse,hashlib,json,os,pathlib,subprocess,time
from observer import canonical,save,syncdir
PHASES=('main-service-fence','native-service-fence','cron-fence','main-stop','native-stop','admission-deny','main-retarget-zero','native-retarget-zero','cron-retarget','main-start','native-start','main-service-restore','native-service-restore','cron-restore')
OBJECTS={'main':('deployment','compute-gateway','f5f9b266-433d-4825-83de-d51e31c71648'),'native':('deployment','native-lifecycle147-gateway','b0cb0842-5bce-4a0d-a63a-6c8d682ea454'),'cron':('cronjob','compute-state-backup','8924e2ab-df98-466f-924c-3100bae8b5b3'),'main-service':('service','compute-gateway','402a4453-127e-43fb-a2b9-1b6bc9f316de'),'native-service':('service','native-lifecycle147-gateway','31469c80-567a-468a-bb2b-cff10f29644f'),'admission':('validatingadmissionpolicybinding','cps-retired-compute-state-write-fence','620b91f2-2267-4a0d-b2eb-fc9b54cf2abc')}
KUBE=['kubectl','--request-timeout=12s','--insecure-skip-tls-verify=false','-n','cps-compute']
REQUIRED={'main-stop':('callers-quiesced',),'admission-deny':('old-writers-stopped',),'main-retarget-zero':('final-install-verified',),'main-start':('old-writers-stopped','final-install-verified','deny-admission-verified'),'main-service-restore':('target-preservation-verified',),'cron-restore':('target-preservation-verified','normal-api-verified')}

def load_pinned(pin):
 p=pathlib.Path(pin['path']);assert p.is_absolute() and not p.is_symlink() and p.is_file() and p.stat().st_size<=2*1024*1024
 raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==pin['sha256'];return json.loads(raw)
def fields(phase):
 role=next(r for r in sorted(OBJECTS,key=len,reverse=True)if phase.startswith(r+'-'))
 return role,OBJECTS[role]
def check_external(plan,phase):
 for name in REQUIRED.get(phase,()):
  proof=load_pinned(plan['evidence'][name]);assert proof['operation']==plan['operation'] and proof['rootRelease']==plan['rootRelease'] and proof['gate']==name and proof['passed']is True
  assert time.time()<proof['expiresAt']<=time.time()+600
  if name=='old-writers-stopped':
   assert proof['liveWriterCount']==0 and type(proof['liveWriterCount'])is int
   assert all(proof[k]is True for k in ('bothServicesFenced','cronSuspended','allCallersQuiescent','currentCustodyClear'))
   expected={x['uid']:sorted(x['cids'])for x in plan['oldWriters']};actual={x['uid']:sorted(x['cids'])for x in proof['oldWritersStopped']}
   assert len(expected)==len(actual)==2 and expected==actual and all(actual.values()),'Exact old Pod/all-CID exclusion required'

 # These are explicitly Root-reviewed external facts. This executor does not
 # manufacture a Kubernetes/CRI, caller, data-copy or authenticated API witness.
def validate(plan,phase):
 assert phase in PHASES and plan['operation']=='planned-checkpoint-20261118' and plan['rootRelease']
 assert time.time()<plan['expiresAt']<=time.time()+600
 assert plan['targetPVCUID']=='bfe673db-6d32-4ddd-a8a7-94cf9b86890e'
 assert plan['targetPVUID']=='63513db8-9ec4-48f9-947d-8faf5ba0ccea'
 row=plan['phases'][phase];role,(kind,name,uid)=fields(phase)
 assert row['kind']==kind and row['name']==name and row['uid']==uid
 return row

def cas(row,current):
 before=load_pinned(row['expectedSpec']);after=load_pinned(row['desiredSpec'])
 assert current['metadata']['uid']==row['uid'] and current['spec']==before and current['metadata']['resourceVersion']
 return [{'op':'test','path':'/metadata/uid','value':row['uid']},{'op':'test','path':'/metadata/resourceVersion','value':current['metadata']['resourceVersion']},{'op':'test','path':'/spec','value':before},{'op':'replace','path':'/spec','value':after}],after

def get(row):return json.loads(subprocess.check_output(KUBE+['get',row['kind'],row['name'],'-o','json'],stderr=subprocess.PIPE,timeout=15))
def begin_directory(d,plan):
 d.mkdir(mode=0o700);syncdir(d.parent);save(d/'operation.safe.json',{'operation':plan['operation'],'rootRelease':plan['rootRelease'],'created':time.time()})
def run(plan,phase,directory):
 os.umask(0o077);row=validate(plan,phase);assert directory.is_dir() and not directory.is_symlink()
 op=json.loads((directory/'operation.safe.json').read_text());assert op['rootRelease']==plan['rootRelease'] and op['operation']==plan['operation']
 index=PHASES.index(phase)
 if index:
  prev=json.loads((directory/(PHASES[index-1]+'-reply.safe.json')).read_text());assert prev['verifiedSpec']is True and prev['phase']==PHASES[index-1]
 assert not (directory/(phase+'-intent.safe.json')).exists(),'UNKNOWN or completed phase: reconcile; never resubmit'
 check_external(plan,phase)
 current=get(row);patch,desired=cas(row,current)
 if phase=='main-service-fence':
  ready=load_pinned(plan['observerReady']);boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
  assert ready['rootRelease']==plan['rootRelease'] and ready['hostBootID']==boot and ready['twoConsecutiveAuthenticatedAPIObservations']is True
  journal=pathlib.Path(plan['observerReady']['path']).parent/'samples.safe.jsonl'
  assert journal.is_file() and not journal.is_symlink()
  with journal.open('rb')as f:
   f.seek(max(0,journal.stat().st_size-65536));lines=f.read().splitlines()
  latest=json.loads(lines[-1]);assert ready['monotonicNs']<=latest['endMonotonicNs']
  assert 0<=time.monotonic_ns()-latest['endMonotonicNs']<=2*10**9 and all(e['ok']for e in latest['endpoints']if e['required']),'Observer baseline stale or unhealthy'
  # First deliberate restriction is timed BEFORE the first API request or intent.
  start={'operation':plan['operation'],'rootRelease':plan['rootRelease'],'hostBootID':boot,'monotonicNs':time.monotonic_ns(),'time':time.time(),'earlierRestrictionMonotonicNs':plan.get('earlierRestrictionMonotonicNs'),'noEarlierRestrictionAttested':plan['noEarlierRestrictionAttested']}
  assert start['earlierRestrictionMonotonicNs']is not None or start['noEarlierRestrictionAttested']is True
  save(directory/'timing-start.safe.json',start)
 save(directory/(phase+'-intent.safe.json'),{'phase':phase,'status':'UNKNOWN','time':time.time(),'patchSHA256':hashlib.sha256(canonical(patch)).hexdigest(),'expectedUID':row['uid'],'expectedResourceVersion':current['metadata']['resourceVersion'],'desiredSpecSHA256':hashlib.sha256(canonical(desired)).hexdigest()})
 # Private request/response only, never command arguments; one mutation only.
 request=directory/(phase+'-patch.private.json');save(request,patch)
 with (directory/(phase+'-reply.private.json')).open('xb')as out,(directory/(phase+'-stderr.private.txt')).open('xb')as err:
  result=subprocess.run(KUBE+['patch',row['kind'],row['name'],'--type=json','--patch-file',str(request),'-o','json'],stdout=out,stderr=err,timeout=15)
 assert result.returncode==0,'Unknown/failed mutation; reconcile read-only before any further phase'
 reply=json.loads((directory/(phase+'-reply.private.json')).read_text());assert reply['metadata']['uid']==row['uid'] and reply['spec']==desired
 fresh=get(row);assert fresh['metadata']['uid']==row['uid'] and fresh['spec']==desired
 proof={'phase':phase,'verifiedSpec':True,'uid':row['uid'],'resourceVersion':fresh['metadata']['resourceVersion'],'time':time.time(),'monotonicNs':time.monotonic_ns()};save(directory/(phase+'-reply.safe.json'),proof);return proof

def reconcile(plan,phase,directory):
 # Expired release may still be inspected. Never writes a successful phase receipt.
 row=plan['phases'][phase];assert (directory/(phase+'-intent.safe.json')).exists()
 actual=get(row);desired=load_pinned(row['desiredSpec']);before=load_pinned(row['expectedSpec'])
 return {'phase':phase,'readOnly':True,'uidMatches':actual['metadata']['uid']==row['uid'],'specMatchesDesired':actual['spec']==desired,'specMatchesBefore':actual['spec']==before,'automaticContinuationPermitted':False}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--plan',type=pathlib.Path,required=True);a.add_argument('--directory',type=pathlib.Path,required=True);a.add_argument('--phase',choices=PHASES,required=True);a.add_argument('--execute',action='store_true');a.add_argument('--reconcile',action='store_true');args=a.parse_args();plan=json.loads(args.plan.read_text());os.umask(0o077)
 assert not(args.execute and args.reconcile)
 if args.reconcile:print(json.dumps(reconcile(plan,args.phase,args.directory)))
 elif args.execute:print(json.dumps(run(plan,args.phase,args.directory)))
 else:print(json.dumps({'preparedOnly':True,'phase':args.phase,'noAPIRequests':True}))
