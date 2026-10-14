"""Default-inert actual normal CIT SourceStart/Close runner; no deployment or grant writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import http.cookiejar
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import ssl
import stat
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
from packet import PROFILE, require, canonical, run_lifecycle

HERE=Path(__file__).parent
MAX_BYTES=1048576


def private(p):
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        i=os.fstat(fd);require(stat.S_ISREG(i.st_mode) and i.st_uid==os.geteuid()
            and i.st_nlink==1 and stat.S_IMODE(i.st_mode)==0o600 and i.st_size<=MAX_BYTES,'Owned private input required')
        return os.read(fd,MAX_BYTES+1)
    finally:os.close(fd)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None


class HTTP:
    def __init__(self,source_url,token):
        u=urllib.parse.urlsplit(source_url);require(u.scheme=='https' and u.netloc and not(u.username or u.password or u.query or u.fragment)
            and u.path.rstrip('/')=='/services/cit-admin','Explicit actual owning CIT HTTPS endpoint required')
        require(token and not any(c.isspace() for c in token),'Actual own-admin opaque token required')
        self.origin=u.scheme+'://'+u.netloc;self.source=source_url.rstrip('/');self.token=token
        self.cookies=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPCookieProcessor(self.cookies),
                                               urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    def request(self,path,body=None,hub=False,bootstrap=False):
        require(path in ['user','users/citnativegroupa','shares/citnativegroupa/rtc'] if hub else
            path in ['local/workspaces?course_id=native-gpu-pilot-20261009','workspaces/native-group-a/start','workspaces/native-group-a/stop'], 'Bounded actual route required')
        if body is not None:require(body=={} and not hub and path.endswith(('/start','/stop')), 'Only ordinary owned Start/Close admitted')
        url=(self.origin+'/hub/api/' if hub else self.source+'/api/')+path
        r=urllib.request.Request(url,data=canonical(body) if body is not None else None,headers={'Authorization':'Bearer '+self.token})
        if body is not None:
            self.cookies.add_cookie_header(r);cookie=SimpleCookie(r.get_header('Cookie','')).get('_xsrf');require(cookie,'Actual Source XSRF cookie required')
            r.add_header('X-XSRFToken',cookie.value);r.add_header('Content-Type','application/json')
        with self.opener.open(r,timeout=300 if body is not None else 20) as response:
            require(response.status==200,'Unexpected actual HTTP status');raw=response.read(MAX_BYTES+1)
        require(len(raw)<=MAX_BYTES,'Bounded response required');return json.loads(raw)
    def bootstrap(self):
        with self.opener.open(urllib.request.Request(self.source+'/app',headers={'Authorization':'Bearer '+self.token}),timeout=20) as r:
            require(r.status==200 and len(r.read(MAX_BYTES+1))<=MAX_BYTES,'Actual normal Source bootstrap required')
        actor=self.request('user',hub=True);require(actor.get('name')=='akadmin' and actor.get('admin') is True,'Current real CIT admin identity required')


def get(kind,namespace,name):
    return json.loads(subprocess.check_output(['kubectl','--request-timeout=10s','-n',namespace,'get',kind,name,'-o','json'],timeout=15))


def capsule(namespace,deployment,container,script,args):
    d=get('deployment',namespace,deployment);s=d['spec']['selector']['matchLabels'];sel=','.join(k+'='+v for k,v in s.items())
    pods=json.loads(subprocess.check_output(['kubectl','--request-timeout=10s','-n',namespace,'get','pods','-l',sel,'-o','json'],timeout=15))['items']
    ready=[p for p in pods if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase')=='Running'
        and any(c['name']==container and c.get('ready') for c in p['status'].get('containerStatuses',[]))]
    require(len(ready)==1,'One exact Ready process required')
    raw=script.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    loader="import hashlib,sys; b=sys.stdin.buffer.read(262145); assert len(b)<=262144 and hashlib.sha256(b).hexdigest()==sys.argv[1]; sys.argv=['verified-witness']+sys.argv[2:]; exec(compile(b,'verified-witness','exec'))"
    output=subprocess.check_output(['kubectl','--request-timeout=10s','-n',namespace,'exec','-i',ready[0]['metadata']['name'],'-c',container,'--',
        'python3','-I','-S','-u','-c',loader,digest,*args],input=raw,timeout=40)
    require(len(output)<=MAX_BYTES,'Bounded witness required');return json.loads(output)


class Backend:
    def __init__(self,client,admission,out):self.client=client;self.admission=admission;self.out=out;self.uid=None;self.binding=None;self.cleanup_names=[]
    def save(self,name,x):
        p=self.out/(name+'.json');p.write_bytes(canonical(x)+b'\n');p.chmod(0o600)
    def observe_source(self):
        ws=self.client.request('local/workspaces?course_id=native-gpu-pilot-20261009')['records']
        selected=[w for w in ws if w['id']=='native-group-a'];require(len(selected)==1,'Actual original scope required')
        w=selected[0];require(w['profile']==PROFILE and w['hub_user']=='citnativegroupa'
            and w['namespace']=='cit-jhub' and w['pod']=='jupyter-citnativegroupa--rtc'
            and w['course_ceiling']=={'cpu':'4','memory':'16Gi','gpuMemoryGiB':10},'Exact unchanged scope/cap required')
        user=self.client.request('users/citnativegroupa',hub=True)
        require(user['name']=='citnativegroupa' and user.get('admin') is False
            and 'kernel' in user.get('roles',[]) and set(user.get('roles',[]))<= {'kernel','user'}, 'Actual approved legacy marker account required')
        return {'workspace':w,'owner_model':user}
    def start(self):
        before=self.observe_source();require(before['workspace']['state']=='stopped' and 'rtc' not in before['owner_model']['servers'],'Actually stopped owner required')
        self.save('source-before',before)
        self.client.request('workspaces/native-group-a/start',{})
        running=self.observe_source();require(running['workspace']['state']=='running' and running['owner_model']['servers']['rtc']['ready'] is True,'Actual SourceReady required')
        pod=get('pod','cit-jhub','jupyter-citnativegroupa--rtc');self.uid=pod['metadata']['uid']
        ledger=get('cm','cps-native-system','cps-native-gpu-allocations');rows=json.loads(ledger['data']['state.json'])['allocations']
        exact=[r for r in rows.values() if (r.get('intent') or {}).get('pod_uid')==self.uid and r['state']=='enrolled']
        require(len(exact)==1 and exact[0]['profile']==PROFILE,'Actual enrolled original UID required');self.binding=exact[0]['binding_id']
        from cps_compute.native_scheduler_allocation import ack_name, _validate_record
        ack=get('cm','cps-native-system',ack_name(self.uid));require(ack.get('immutable') is True,'Actual immutable terminal ACK required')
        record=json.loads(ack['data']['allocation.json']);_validate_record(record)
        require(record['intent']==exact[0]['intent'] and record['profile']==PROFILE,'Actual ACK is detached from frozen ledger')
        request=get('bindrequest',record['bind_request']['namespace'],record['bind_request']['name'])
        require(request['metadata']['uid']==record['bind_request']['uid']
            and hashlib.sha256(canonical(request['spec'])).hexdigest()==record['bind_request']['spec_sha256'],'Actual BindRequest spec changed')
        group=request['spec']['selectedFractionalGpuGroups'][0]['id']
        reservation='gpu-reservation-'+hashlib.sha256(('k3s-wk-gpu2/'+group).encode()).hexdigest()[:16]
        actual_reservation=get('pod','kai-resource-reservation',reservation)
        self.cleanup_names=[{'kind':'configmap',**{k:r[k] for k in ['namespace','name','uid']}} for r in record['maps']]+[
            {'kind':'pod','namespace':'kai-resource-reservation','name':reservation,'uid':actual_reservation['metadata']['uid']}]
        self.save('actual-ack-and-cleanup-identities',{'ack':ack,'refs':self.cleanup_names})
        witness=capsule('cps-native-system','cps-native-node-agent','node-agent',HERE/'observe_node.py',
            ['--execute','--phase','running','--pod-uid',self.uid,'--binding-id',self.binding,'--crictl',self.admission['crictl']])
        self.save('actual-running-native',witness);self.save('source-ready',running);return witness
    def close(self):
        # Retries are ordinary idempotent Close only, bounded to actual cleanup.
        end=time.monotonic()+180
        while True:
            try:
                self.client.request('workspaces/native-group-a/stop',{})
                return
            except Exception:
                if time.monotonic()>=end:raise
                time.sleep(2)
    def terminal(self):
        require(self.uid and self.binding,'Unknown CREATE outcome requires durable Hold/recovery; cannot infer no Pod')
        observed=self.observe_source();require(observed['workspace']['state']=='stopped' and 'rtc' not in observed['owner_model']['servers'],'Normal Source shutdown required')
        physical=capsule('cps-native-system','cps-native-node-agent','node-agent',HERE/'observe_node.py',
            ['--execute','--phase','terminal','--pod-uid',self.uid,'--binding-id',self.binding,'--crictl',self.admission['crictl']])
        sql=capsule('cps-compute','compute-gateway','gateway',HERE/'gateway_observer.py', ['--execute','--pod-uid',self.uid,'--binding-id',self.binding])
        ledger=get('cm','cps-native-system','cps-native-gpu-allocations');row=json.loads(ledger['data']['state.json'])['allocations'][self.binding]
        require(row['state']=='released' and row['intent']['pod_uid']==self.uid,'Actual original ledger release required')
        require(sql['custody_state']=='clean' and sql['member_reservations']==sql['reservation_bindings']==0,'Actual durable custody/member barrier remains held')
        self.save('actual-terminal-native',physical);self.save('actual-terminal-gateway',sql)
        # Exact names/UIDs were captured from the immutable ACK/current reservation.
        for ref in self.cleanup_names:
            p=subprocess.run(['kubectl','--request-timeout=10s','-n',ref['namespace'],'get',ref['kind'],ref['name'],'--ignore-not-found','-o','json'],capture_output=True,timeout=15)
            require(p.returncode==0 and not p.stdout.strip(),'Actual exact map/reservation absence required')
        try: shares=self.client.request('shares/citnativegroupa/rtc',hub=True)
        except urllib.error.HTTPError as error:
            if error.code!=404:raise
            shares={'items':[]}  # exact server absence already observed above
        require(shares.get('items')==[],'Actual server Shares must close')
        self.save('source-stopped',observed)
        return {k:True for k in ['clean','native_zero','exact_pod_absent','maps_absent','ledger_released','member_reservations_zero','custody_clean','reservation_absent','shares_closed']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--admission',type=Path);p.add_argument('--admission-sha256');p.add_argument('--token-file',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if not a.execute:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'writes':False}));return
    require(a.admission and a.token_file and a.output and a.admission_sha256,'Explicit Root-reviewed private admission/token/output required')
    raw=private(a.admission);require(hashlib.sha256(raw).hexdigest()==a.admission_sha256,'Exact reviewed admission required');admission=json.loads(raw)
    now=datetime.now(timezone.utc);expires=datetime.fromisoformat(admission['expires'])
    require(admission['enabled'] is True and admission['source']=='cit' and admission['workspace']=='native-group-a'
        and 0<(expires-now).total_seconds()<=900,'Bounded explicit source ownership required')
    require(admission['maintenance_ready'] is True and admission['node_epoch_seam_qualified'] is True
        and admission['signed_identity_and_cas_readbacks_passed'] is True,
        'Unfinished actual deployment/auth/epoch gates cannot execute')
    require(a.output.parent.stat().st_uid==os.geteuid() and stat.S_IMODE(a.output.parent.stat().st_mode)==0o700,'Private output parent required')
    a.output.mkdir(mode=0o700);client=HTTP(admission['source_url'],private(a.token_file).decode().strip());client.bootstrap()
    backend=Backend(client,admission,a.output)
    try:run_lifecycle(backend)
    finally:backend.save('runner-result',{'production_qualified':False,'automatic_config_restore':False,
        'live_gpu2_case_requires_Root_review':True,'normal_source_close_attempted':True})

if __name__=='__main__':main()
