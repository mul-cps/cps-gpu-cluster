"""Own exactly one normal-user Jupyter kernel. No I/O at import; no GPU API here."""
import hashlib,json,os,re,stat,threading,time,uuid
from pathlib import Path
from urllib.parse import quote
from kernel_transport import exchange,probe_code

ORIGIN='https://jupyterhub.dshl.unileoben.ac.at'

def require(ok,message):
    if not ok:raise ValueError(message)

def private_read(path,limit):
    require(isinstance(path,str) and Path(path).is_absolute(),'Absolute private file required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,limit+1);after=os.fstat(fd)
        require(len(raw)==before.st_size and stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600 and before.st_uid==os.getuid() and before.st_nlink==1 and 0<len(raw)<=limit and all(getattr(before,k)==getattr(after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Stable owned private0600 file required')
        return raw
    finally:os.close(fd)

def read_token(path):
    token=private_read(path,4096).decode().strip()
    require(bool(re.fullmatch('[A-Za-z0-9_-]{1,4096}',token)),'Bounded Hub token required')
    return token

def route(plan):
    return '/user/'+quote(plan['owner'],safe='')+'/'+quote(plan['server'],safe='')

def validate_plan(plan,target):
    require(type(plan)is dict and set(plan)=={'hub_origin','operator','owner','server','pod_uid','token_file'},'Closed kernel credential row required')
    require(plan['hub_origin']==ORIGIN,'Fixed CPS HTTPS origin required')
    for key in ('operator','owner','server'):
        require(isinstance(plan[key],str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.@-]{0,252}',plan[key]) and '..' not in plan[key],'Safe explicit user/server identifier required')
    require(isinstance(plan['pod_uid'],str) and str(uuid.UUID(plan['pod_uid']))==plan['pod_uid'] and uuid.UUID(plan['pod_uid']).int and plan['pod_uid']==target['uid'],'Exact target Pod UID required')
    require(isinstance(plan['token_file'],str) and Path(plan['token_file']).is_absolute(),'Absolute token path required')
    return plan

def read_plans(path,digest,targets):
    raw=private_read(str(path),16384)
    require(hashlib.sha256(raw).hexdigest()==digest,'Separately reviewed kernel manifest SHA required')
    value=json.loads(raw)
    require(type(value)is dict and set(value)=={'a','b'},'Closed a/b kernel manifest required')
    for name in ('a','b'):validate_plan(value[name],targets['pods'][name])
    return value

def check_target(target,plan):
    import current_preflight as current
    pod=current.pod(target)
    require(pod['metadata']['uid']==target['uid'] and not pod['metadata'].get('deletionTimestamp') and pod['status']['phase']=='Running','Exact running owned target required')
    states=[x for x in pod['status'].get('containerStatuses',[])if x['name']=='notebook']
    require(len(states)==1 and states[0].get('ready')is True and 'running'in states[0].get('state',{}),'Ready notebook target required')
    containers=[x for x in pod['spec']['containers']if x['name']=='notebook']
    require(len(containers)==1,'One notebook container required')
    env=containers[0].get('env',[])
    for key,value in {'JUPYTERHUB_USER':plan['owner'],'JUPYTERHUB_SERVER_NAME':plan['server'],'JUPYTERHUB_SERVICE_PREFIX':route(plan)+'/'}.items():
        found=[x for x in env if x.get('name')==key]
        require(len(found)==1 and found[0].get('value')==value and 'valueFrom'not in found[0],'Actual named server route mismatch')

class Hub:
    def __init__(self,plan,token):
        import httpx
        self.prefix=route(plan);self.token=token
        self.client=httpx.Client(base_url=ORIGIN,headers={'Authorization':'token '+token},timeout=20,follow_redirects=False,trust_env=False)
    def request(self,method,path,**kwargs):
        allowed={self.prefix+'/api/kernels','/hub/api/user'}
        require(path in allowed or (method=='DELETE' and path.startswith(self.prefix+'/api/kernels/') and checked_uuid(path.rsplit('/',1)[1])),'Exact kernel API path required')
        response=self.client.request(method,path,**kwargs)
        require(response.status_code in (200,201,204),'Hub/Jupyter request failed: '+str(response.status_code))
        require(len(response.content)<=1024*1024,'Bounded Jupyter response required')
        return response
    def socket(self,kernel_id,session):
        from websockets.sync.client import connect
        return connect('wss://jupyterhub.dshl.unileoben.ac.at'+self.prefix+'/api/kernels/'+checked_uuid(kernel_id)+'/channels?session_id='+checked_uuid(session),origin=ORIGIN,additional_headers={'Authorization':'token '+self.token},proxy=None,open_timeout=20,close_timeout=5,max_size=8*1024*1024,max_queue=32)
    def close(self):self.client.close();self.token=None

def checked_uuid(value):
    require(isinstance(value,str) and str(uuid.UUID(value))==value and uuid.UUID(value).int,'Canonical fresh kernel UUID required')
    return value

def wait_watchdog(deadline):
    # A closed local socket does not terminate remote work. Never interrupt/replay.
    while time.monotonic()<deadline:time.sleep(min(.5,deadline-time.monotonic()))

def kernel_ids(value):
    require(type(value)is list and len(value)<=1024,'Bounded kernel list required')
    ids=[checked_uuid(row.get('id'))for row in value if type(row)is dict]
    require(len(ids)==len(value) and len(ids)==len(set(ids)),'Unique actual kernel list required')
    return set(ids)

class KernelProbeRun:
    def __init__(self,target,case,duration,source,output,*,plan,expected_sha,hub_factory=Hub,pod_check=check_target):
        self.events=[];self.error=None;self.condition=threading.Condition();self.reader=None
        self.hub=None;self.kid=None;self.started=None;self.failure_deadline=None;self.closed=False;self.output=Path(output)
        self.target=target;self.plan=validate_plan(plan,target);self.pod_check=pod_check;self.duration=duration
        directory=self.output.lstat()
        require(stat.S_ISDIR(directory.st_mode) and stat.S_IMODE(directory.st_mode)==0o700 and directory.st_uid==os.getuid(),'Owned existing0700 output directory required')
        self.receipt={'created_kernel':None,'deleted_own_kernel':False,'manual_cleanup_required':False,'gpu_cleanup_proven':False,'source_sha256':expected_sha}
        self.receipt_path=self.output/(case+'.kernel.json')
        self.receipt_fd=os.open(self.receipt_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        self.stream=None
        try:
            code=probe_code(source.decode('utf-8'),expected_sha,case,duration)
            token=read_token(plan['token_file']);self.hub=hub_factory(plan,token)
            self.pod_check(target,plan)
            actor=self.hub.request('GET','/hub/api/user').json()
            require(actor.get('name')==plan['operator'] and actor.get('kind')=='user' and actor.get('admin')is False,'Normal non-admin operator identity required')
            old=kernel_ids(self.hub.request('GET',self.hub.prefix+'/api/kernels').json())
            self.receipt['manual_cleanup_required']=True;self._receipt()
            # Exactly one POST. Exceptions after dispatch never cause automatic replay/adoption.
            model=self.hub.request('POST',self.hub.prefix+'/api/kernels',json={'name':'python3'}).json()
            candidate=checked_uuid(model.get('id'))
            require(candidate not in old,'Fresh kernel required; never delete an existing UUID')
            self.kid=candidate;self.receipt['created_kernel']=candidate;self.receipt['pod_uid']=target['uid'];self.receipt['route']=self.hub.prefix;self._receipt()
            require(model.get('name')=='python3','Fresh python3 kernel required')
            self.pod_check(target,plan)
            fd=os.open(self.output/(case+'.jsonl'),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            self.stream=os.fdopen(fd,'w',encoding='utf-8')
            def collect():
                try:
                    self.pod_check(target,plan)
                    session=str(uuid.uuid4())
                    with self.hub.socket(self.kid,session)as socket:
                        self.started=time.monotonic()
                        exchange(socket,code,session,self._consume,timeout=duration+15)
                    self.pod_check(target,plan)
                except Exception as error:
                    self.error=type(error).__name__
                    if self.started is not None:self.failure_deadline=time.monotonic()+self.duration+10
                finally:
                    try:self._cleanup()
                    except Exception as error:self.error=type(error).__name__
                    with self.condition:self.condition.notify_all()
            self.reader=threading.Thread(target=collect,daemon=True);self.reader.start()
        except BaseException:
            self._cleanup();raise
    def _receipt(self):
        raw=(json.dumps(self.receipt,sort_keys=True)+'\n').encode()
        os.lseek(self.receipt_fd,0,os.SEEK_SET);os.ftruncate(self.receipt_fd,0);os.write(self.receipt_fd,raw);os.fsync(self.receipt_fd)
    def _consume(self,event):
        raw=json.dumps(event,sort_keys=True)
        self.stream.write(raw+'\n');self.stream.flush()
        with self.condition:self.events.append(event);self.condition.notify_all()
    def _cleanup(self):
        if self.closed:return
        self.closed=True
        try:
            if self.kid is not None:
                if self.failure_deadline is not None:wait_watchdog(self.failure_deadline)
                self.pod_check(self.target,self.plan)
                self.hub.request('DELETE',self.hub.prefix+'/api/kernels/'+self.kid)
                remaining=kernel_ids(self.hub.request('GET',self.hub.prefix+'/api/kernels').json())
                require(self.kid not in remaining,'Owned kernel deletion unconfirmed')
                self.receipt['deleted_own_kernel']=True;self.receipt['manual_cleanup_required']=False
        except BaseException:
            self.receipt['manual_cleanup_required']=True;raise
        finally:
            try:
                try:
                    if self.stream:self.stream.close()
                finally:
                    if self.hub:self.hub.close()
            finally:
                try:self._receipt()
                finally:os.close(self.receipt_fd)
    def wait(self,predicate,timeout):
        require(type(timeout)in (int,float) and 0<timeout<=240,'Bounded overlap wait required')
        deadline=time.monotonic()+timeout
        with self.condition:
            while not predicate(self.events):
                require(not self.error,'Kernel probe stream failed: '+str(self.error))
                require(self.reader.is_alive(),'Kernel probe ended before overlap')
                remaining=deadline-time.monotonic();require(remaining>0,'Probe overlap deadline exceeded')
                self.condition.wait(min(remaining,.5))
    def complete(self):
        self.reader.join(timeout=self.duration+180)
        require(not self.reader.is_alive() and not self.error and self.receipt['deleted_own_kernel'],'Kernel probe or owned cleanup failed')
        return self.events
    def close(self):
        if self.reader:
            # Never delete a busy kernel early; worker enforces bounded execution/cleanup.
            self.reader.join(timeout=self.duration+180)
            require(not self.reader.is_alive(),'Kernel cleanup still running; manual hold required')
        else:self._cleanup()
