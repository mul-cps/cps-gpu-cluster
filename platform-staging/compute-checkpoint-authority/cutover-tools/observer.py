"""Unarmed GET-only outage observer; no tokens minted and no mutating HTTP methods."""
import argparse,hashlib,http.client,json,multiprocessing as mp,os,pathlib,re,ssl,time,signal,subprocess,urllib.request,urllib.parse,urllib.error

MAX_BODY=1024*1024
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def private_file(path):
 p=pathlib.Path(path);s=p.lstat();assert p.is_absolute() and not p.is_symlink() and p.is_file() and s.st_uid==os.getuid() and s.st_mode&0o077==0 and s.st_nlink==1 and s.st_size<=16384
 return p.read_bytes()
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def save(p,x):
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as f:f.write(canonical(x));f.flush();os.fsync(f.fileno())
 syncdir(pathlib.Path(p).parent)
def validate(c):
 assert c.get('rootRelease') and c.get('operation')=='planned-checkpoint-20261118'
 assert time.time()<c['expiresAt']<=time.time()+900
 assert 0<c['intervalSeconds']<=.5 and c['maximumSeconds']<=600 and c['maximumSeconds']>0
 assert isinstance(c['endpoints'],list) and 1<=len(c['endpoints'])<=8
 ids=[];required=0
 for e in c['endpoints']:
  assert re.fullmatch('[a-z][a-z0-9-]{0,63}',e['id']);ids.append(e['id'])
  u=urllib.parse.urlsplit(e['url']);assert u.scheme=='https' and u.hostname and u.username is None and u.password is None and not u.query and not u.fragment and '\\'not in e['url'] and not any(ord(x)<33 for x in e['url'])
  assert re.fullmatch(r'/(healthz?|internal/v1/(profiles|reservations/[A-Za-z0-9_.:-]+|workspaces/[A-Za-z0-9_.:-]+)|services/(cps|cit)-admin/api/(platform-status|local/workspaces))',u.path)
  assert e['expectedStatus']in (200,404) and type(e['required'])is bool
  assert e['authScheme']in ('Bearer','token')
  assert e['transport']in ('direct-tls','source-pod')
  if e['transport']=='direct-tls':assert e['tokenFile']
  else:
   b=e['podBinding'];assert b['namespace']=='cps-compute' and b['container']=='console' and b['source']in ('cps','cit')
   assert b['name'].startswith(b['source']+'-admin-') and all(b[k]for k in ('uid','containerID','imageID'))
   assert e['authScheme']=='Bearer' and e['caFile']=='/trust/ca.crt' and u.netloc=='compute-gateway.cps-compute.svc.cluster.local:8000'
   assert u.path.startswith('/internal/v1/')
  assert isinstance(e['expectedJSONSubset'],dict) and e['expectedJSONSubset']
  if e['required']:
   assert e['category']=='authenticated-api' and u.path not in ('/health','/healthz')
   if e['expectedStatus']==200:required+=1
 assert required>=1 and len(ids)==len(set(ids))
 return c

def subset(expected,actual):
 return isinstance(actual,dict) and all(k in actual and (subset(v,actual[k]) if isinstance(v,dict) else type(v)==type(actual[k]) and v==actual[k])for k,v in expected.items())
def probe(e,source_environment=False):
 # Values remain process RAM. No response body, URL, token or exception text is emitted.
 result={'id':e['id'],'required':e['required'],'ok':False,'status':None,'category':'transport-error'}
 try:
  token=(os.environ['COMPUTE_POLICY_TOKEN'] if source_environment else private_file(e['tokenFile']).decode()).strip();assert token and len(token)<=8192 and not any(x.isspace()for x in token)
  ctx=ssl.create_default_context(cafile=e.get('caFile')or None)
  assert ctx.verify_mode==ssl.CERT_REQUIRED and ctx.check_hostname
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ctx))
  req=urllib.request.Request(e['url'],method='GET',headers={'Authorization':e['authScheme']+' '+token,'Accept':'application/json','Connection':'close'})
  with opener.open(req,timeout=.6)as response:
   result['status']=response.status;raw=response.read(MAX_BODY+1);assert len(raw)<=MAX_BODY
   body=json.loads(raw);result['ok']=response.status==e['expectedStatus'] and subset(e['expectedJSONSubset'],body) and (not e.get('expectedBodySHA256') or hashlib.sha256(raw).hexdigest()==e['expectedBodySHA256'])
   result['category']='verified-api'if result['ok']else'body-or-status-mismatch'
 except urllib.error.HTTPError as ex:
  result.update(status=ex.code,category='http-error')
  if ex.code==e['expectedStatus']==404:
   try:
    raw=ex.read(MAX_BODY+1);assert len(raw)<=MAX_BODY;body=json.loads(raw);result['ok']=subset(e['expectedJSONSubset'],body);result['category']='verified-source-isolation' if result['ok'] else 'body-or-status-mismatch'
   except (ValueError,AssertionError):pass
 except (ssl.SSLCertVerificationError,ssl.CertificateError):result['category']='tls-verification-failed'
 except urllib.error.URLError as ex:
  result['category']='tls-verification-failed'if isinstance(ex.reason,(ssl.SSLCertVerificationError,ssl.CertificateError))else'transport-error'
 except (ValueError,AssertionError):result['category']='input-or-body-invalid'
 return result

def source_https_batch(endpoints):
 host='compute-gateway.cps-compute.svc.cluster.local'
 context=ssl.create_default_context(cafile='/trust/ca.crt')
 assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
 token=os.environ['COMPUTE_POLICY_TOKEN'].strip()
 assert token and len(token)<=8192 and not any(c.isspace() for c in token)
 connection=http.client.HTTPSConnection(host,8000,timeout=.6,context=context)
 rows=[]
 try:
  for e in endpoints:
   row=failures([e],'transport-error')[0]
   rows.append(row)
   url=urllib.parse.urlsplit(e['url'])
   assert url.scheme=='https' and url.netloc==host+':8000' and not url.query and not url.fragment
   try:
    connection.request('GET',url.path,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
    response=connection.getresponse()
    row['status']=response.status
    raw=response.read(MAX_BODY+1)
    if len(raw)>MAX_BODY:
     row['category']='input-or-body-invalid'
     connection.close()
     continue
    row['ok']=(response.status==e['expectedStatus'] and subset(e['expectedJSONSubset'],json.loads(raw))
       and (not e.get('expectedBodySHA256') or hashlib.sha256(raw).hexdigest()==e['expectedBodySHA256']))
    row['category']=('verified-source-isolation' if response.status==404 else 'verified-api') if row['ok'] else 'body-or-status-mismatch'
   except (ssl.CertificateError,ssl.SSLCertVerificationError):
    row['category']='tls-verification-failed'
    connection.close()
   except (OSError,http.client.HTTPException):
    connection.close()
   except ValueError:
    row['category']='input-or-body-invalid'
 finally:
  connection.close()
 return rows

def source_probe_batch(endpoints):
 assert endpoints and all(e['transport']=='source-pod' for e in endpoints)
 b=endpoints[0]['podBinding'];assert all(e['podBinding']==b for e in endpoints),'Mixed Source identity in batch'
 assert len({e['id']for e in endpoints})==len(endpoints)
 base=['kubectl','--insecure-skip-tls-verify=false','--request-timeout=1s','-n','cps-compute']
 p=json.loads(subprocess.check_output(base+['get','pod',b['name'],'-o','json'],stderr=subprocess.PIPE,timeout=.7))
 assert p['metadata']['uid']==b['uid'] and not p['metadata'].get('deletionTimestamp')
 c=next(c for c in p['status']['containerStatuses']if c['name']=='console')
 assert c['containerID']==b['containerID'] and c['imageID']==b['imageID'] and c['ready']is True
 remote_endpoints=[{k:v for k,v in e.items()if k not in ('podBinding','tokenFile')}for e in endpoints]
 # Fixed code goes on stdin, never a token/long script in exec argv. Remote
 # existing Source credential stays in that process and never returns to Root.
 code="import signal;signal.alarm(1)\n"+pathlib.Path(__file__).read_text().rsplit("if __name__=='__main__':",1)[0]+"\nprint(json.dumps(source_https_batch("+repr(remote_endpoints)+")))\n"
 r=subprocess.run(base+['exec','-i',b['name'],'-c','console','--','python','-'],input=code.encode(),capture_output=True,timeout=.8)
 assert r.returncode==0 and len(r.stdout)<=8192
 rows=json.loads(r.stdout);assert isinstance(rows,list) and len(rows)==len(endpoints)
 assert [r['id']for r in rows]==[e['id']for e in endpoints]
 return rows

def source_probe(e):return source_probe_batch([e])[0]

def groups(endpoints):
 result=[];by_pod={}
 for e in endpoints:
  if e['transport']!='source-pod':result.append([e]);continue
  b=e['podBinding'];key=(b.get('namespace'),b['name'],b['uid'])
  if key not in by_pod:by_pod[key]=[];result.append(by_pod[key])
  else:assert by_pod[key][0]['podBinding']==b,'Conflicting bindings for the same Source Pod'
  by_pod[key].append(e)
 return result

def failures(endpoints,category):return [{'id':e['id'],'required':e['required'],'ok':False,'status':None,'category':category}for e in endpoints]

def child(endpoints,pipe):
 os.setsid()
 try:pipe.send(source_probe_batch(endpoints) if endpoints[0]['transport']=='source-pod' else [probe(endpoints[0])])
 except BaseException:pipe.send(failures(endpoints,'probe-process-failed'))
 finally:pipe.close()
def sample(endpoints):
 # One pinned GET + one exec per Source Pod; deadlines and cadence are unchanged.
 ctx=mp.get_context('fork');jobs=[];end=time.monotonic()+.8
 for batch in groups(endpoints):
  parent,remote=ctx.Pipe(duplex=False);p=ctx.Process(target=child,args=(batch,remote));p.start();remote.close();jobs.append((batch,p,parent))
 rows=[]
 try:
  for batch,p,pipe in jobs:
   if pipe.poll(max(0,end-time.monotonic())):
    try:rows.extend(pipe.recv())
    except EOFError:rows.extend(failures(batch,'probe-process-failed'))
   else:rows.extend(failures(batch,'bounded-probe-timeout'))
 finally:
  for _,p,pipe in jobs:
   if p.is_alive():
    try:os.killpg(p.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    if p.is_alive():p.kill()
   p.join(timeout=.3)
   if p.is_alive():
    p.kill();p.join(timeout=1)
   pipe.close()
   if p.is_alive():raise RuntimeError('Probe child could not be reaped; observer incomplete')
 return rows

def duration(start,end,boot):
 assert start['hostBootID']==boot and start['operation']=='planned-checkpoint-20261118'
 t0=start['monotonicNs'];earlier=start.get('earlierRestrictionMonotonicNs')
 if earlier is not None:assert 0<earlier<=t0;t0=earlier
 else:assert start['noEarlierRestrictionAttested']is True
 assert end>=t0
 return (end-t0)/1e9

def validate_timing(c,start,finish,boot,endns):
 assert start['rootRelease']==c['rootRelease'],'Timing receipt belongs to another release'
 assert start['operation']==c['operation'] and start['hostBootID']==boot
 assert finish['operation']==c['operation'] and finish['rootRelease']==c['rootRelease'] and finish['hostBootID']==boot
 assert all(finish[k]is True for k in ('bothServicesRestored','targetStatePreservationVerified','requiredControlOperationVerified'))
 assert finish['monotonicNs']>=start['monotonicNs'] and finish['monotonicNs']<=endns

def run(c,output,start_file,finish_file):
 validate(c);os.umask(0o077);output.mkdir(mode=0o700);syncdir(output.parent)
 boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();save(output/'observer-start.safe.json',{'operation':c['operation'],'rootRelease':c['rootRelease'],'hostBootID':boot,'configSHA256':hashlib.sha256(canonical(c)).hexdigest(),'time':time.time(),'monotonicNs':time.monotonic_ns()})
 begin=time.monotonic();previous=None;maxgap=0;streak=0;final=None;baseline=0;ready=False;first_loss_lower=None;last_good_start=None;all_samples_good=True
 with (output/'samples.safe.jsonl').open('x')as log:
  while time.monotonic()-begin<c['maximumSeconds'] and time.time()<c['expiresAt']:
   cycle=time.monotonic();ns=time.monotonic_ns()
   if previous is not None:maxgap=max(maxgap,(ns-previous)/1e9)
   previous=ns;rows=sample(c['endpoints']);endns=time.monotonic_ns()
   good=all(r['ok'] for r in rows if r['required']);all_samples_good=all_samples_good and good
   if c.get('prequalificationOnly'):assert not start_file.exists(),'Prequalification cannot cross a real fence'
   if good:
    last_good_start=ns;baseline+=1
   else:
    baseline=0
    if ready and first_loss_lower is None:first_loss_lower=last_good_start
   if not ready and baseline>=2 and not start_file.exists():
    save(output/'ready.safe.json',{'rootRelease':c['rootRelease'],'operation':c['operation'],'hostBootID':boot,'monotonicNs':endns,'twoConsecutiveAuthenticatedAPIObservations':True});ready=True
   row={'time':time.time(),'startMonotonicNs':ns,'endMonotonicNs':endns,'endpoints':rows};log.write(json.dumps(row)+'\n');log.flush();os.fsync(log.fileno())
   if start_file.exists() and finish_file.exists():
    start=json.loads(start_file.read_text());finish=json.loads(finish_file.read_text())
    assert ready,'No measured usable API baseline before fencing'
    validate_timing(c,start,finish,boot,endns)
    good=all(r['ok'] for r in rows if r['required']);streak=streak+1 if good else 0
    if streak>=2:
     seconds=duration(start,endns,boot)
     if first_loss_lower is not None:seconds=max(seconds,(endns-first_loss_lower)/1e9)
     final={'status':'MEASURED','seconds':seconds,'thresholdSeconds':60,'thresholdPass':seconds<=60 and maxgap<=1,'maxSampleStartGapSeconds':maxgap,'observerCadenceQualified':maxgap<=1,'hostBootID':boot,'finishReceiptSHA256':hashlib.sha256(canonical(finish)).hexdigest(),'rootAttestedPreservationAndControlOperation':True,'coldHAClaim':False};break
   time.sleep(max(0,c['intervalSeconds']-(time.monotonic()-cycle)))
 if final is None:
  final={'status':'PREQUALIFICATION_ONLY' if c.get('prequalificationOnly') else 'INCOMPLETE_OR_TIMED_OUT','thresholdPass':False,'maxSampleStartGapSeconds':maxgap,'baselineReady':ready,'requiredAPIsEverySampleGood':all_samples_good,'cadenceQualified':maxgap<=1,'noCutoverClaim':True}
 save(output/'result.safe.json',final);return final
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--start',type=pathlib.Path,required=True);p.add_argument('--finish',type=pathlib.Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:print(json.dumps({'preparedOnly':True,'noRequests':True}));raise SystemExit(0)
 print(json.dumps(run(json.loads(a.config.read_text()),a.output,a.start,a.finish)))
