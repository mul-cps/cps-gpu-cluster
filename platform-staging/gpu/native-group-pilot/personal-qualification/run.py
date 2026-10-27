#!/usr/bin/env python3
"""Inert by default. One reviewed, already-running operator pair; no Pod writes.

Runs owned exact-source children, never a user kernel. Captures independent host
NVML/ancestry/kernel observations through the existing pinned observer. Retains
all raw bytes. This does not publish gates or qualification ConfigMaps.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import queue
import threading
import secrets


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def private(path,pin):
    p=Path(path);s=p.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and s.st_mode&0o077==0,
            'Owned regular private manifest required')
    raw=p.read_bytes();require(len(raw)<=1048576 and sha(raw)==pin,'Reviewed manifest bytes changed')
    return raw


# Fixed remote transport. No caller command or home path. Shell words are quoted
# by shlex; source bytes and role are validated before writing private /tmp.
REMOTE = r'''
import base64,hashlib,json,os,pathlib,shlex,shutil,subprocess,sys,tempfile
r=json.loads(sys.stdin.read());op=r['operation']
def check(ok):
 if not ok:raise ValueError('Owned transport contract failed')
if op=='setup':
 raw=base64.b64decode(r['source']);check(hashlib.sha256(raw).hexdigest()==r['sha256'])
 root=pathlib.Path(tempfile.mkdtemp(prefix='cps-mujoco-'));os.chmod(root,0o700)
 script=root/'probe.py';script.write_bytes(raw);script.chmod(0o600)
 role=r['role'];check(role in ('pressure','peer'))
 command=shlex.join([*(['vglrun','-d','egl'] if role=='pressure' else []),sys.executable,'-I',str(script),'--execute','--role',role])
 command='env CPS_QUALIFICATION_ACK_DIR='+shlex.quote(str(root))+' '+command
 command+=' >'+shlex.quote(str(root/'stdout'))+' 2>'+shlex.quote(str(root/'stderr'))
 command+='; result=$?; printf "%s" "$result" >'+shlex.quote(str(root/'exit'))
 if role=='pressure':
  subprocess.run(['xpra','control',':100','start-child',shlex.join(['sh','-c',command])],check=True,timeout=10,stdout=sys.stderr)
 else:subprocess.Popen(['sh','-c',command],start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 print(json.dumps({'root':str(root)}))
else:
 root=pathlib.Path(r['root']);s=root.lstat()
 check(str(root).startswith('/tmp/cps-mujoco-') and root.parent==pathlib.Path('/tmp') and not root.is_symlink() and s.st_uid==os.getuid() and s.st_mode&0o777==0o700)
 if op=='read':
  values={}
  for key in ('stdout','stderr','exit'):
   p=root/key
   if p.exists():
    check(not p.is_symlink() and p.stat().st_uid==os.getuid() and p.stat().st_size<=262144)
    values[key]=p.read_text()
  print(json.dumps(values))
 elif op=='finish-peer':
  fd=os.open(root/'peer-finish',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  os.write(fd,b'finish');os.close(fd);print('{}')
 elif op=='ack':
  key=r['event_sha256'];check(len(key)==64 and all(c in '0123456789abcdef' for c in key))
  fd=os.open(root/(key+'.ack'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  os.write(fd,b'sampled');os.close(fd);print('{}')
 elif op=='cleanup':
  check((root/'exit').is_file())
  check(set(p.name for p in root.iterdir())<={'probe.py','stdout','stderr','exit'})
  shutil.rmtree(root);print('{}')
 else:raise ValueError('Unknown operation')
'''


class OwnedWindow:
    """One bounded kubectl exec stream; root watchdog owns remote termination.

    No adoption/restart or signal to a user process. Lost transport retains a
    hold; closing our private pipe only aborts this read-only owned observer.
    """
    def __init__(self,args,request,output):
        self.process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,bufsize=0)
        self.rows=[];self.errors=bytearray();self.queue=queue.Queue(maxsize=1026)
        def read():
            try:
                while True:
                    line=self.process.stdout.readline(1048577)
                    if not line:break
                    require(len(line)<=1048576 and len(self.rows)<1024 and sum(map(len,self.rows))+len(line)<=1048576,'Observer output exceeded bounds')
                    self.rows.append(line)
                    with output.open('ab') as retained:retained.write(line)
                    self.queue.put(json.loads(line),timeout=1)
            except BaseException as exc:self.queue.put(exc,timeout=1)
            finally:self.queue.put(None,timeout=1)
        def errors():
            raw=self.process.stderr.read(65537);self.errors.extend(raw)
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        threading.Thread(target=errors,daemon=True).start()
        self.process.stdin.write(canonical(request)+b'\n');self.process.stdin.flush()
        try:
            ready=self.queue.get(timeout=12)
            require(type(ready) is dict and ready.get('kind')=='ready'
                and ready.get('registration_rc')==ready.get('create_rc')==0
                and ready.get('supported_mask',0)&8,'Supported observer registration ACK unavailable')
        except BaseException:
            self.abandon();raise
        self.token=request['token']

    def finish(self):
        self.process.stdin.write(canonical({'operation':'finish','token':self.token})+b'\n')
        self.process.stdin.flush();self.process.stdin.close()
        self.process.wait(timeout=12);self.reader.join(timeout=2)
        require(self.process.returncode==0 and not self.reader.is_alive() and len(self.errors)<=65536,
            'Observer completion/transport unknown')
        return b''.join(self.rows)

    def abandon(self):
        if self.process.stdin and not self.process.stdin.closed:self.process.stdin.close()



class Collector:
    def __init__(self,manifest,probe,host_source,output,*,command=None,window_source=None,window_factory=None):
        self.m=manifest;self.probe=probe;self.host=host_source;self.output=output
        self.window_source=window_source;self.window_factory=window_factory or OwnedWindow;self.window=None
        self.peer_checks=[]
        self.command=command or self._command;self.roots={};self.attempted=set();self.kernel_baseline=None;self.peer_identity=None

    @staticmethod
    def _command(args,stdin=None):
        result=subprocess.run(args,input=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=12,check=True)
        require(len(result.stdout)<=4194304 and len(result.stderr)<=65536,'Transport output exceeded bound')
        return result.stdout

    def get(self,kind,row):
        args=['kubectl','--request-timeout=8s']
        if 'namespace' in row:args+=['-n',row['namespace']]
        raw=self.command(args+['get',kind,row['name'],'-o','json'])
        value=json.loads(raw);require(value['metadata']['uid']==row['uid'],'Current API object UID changed')
        return raw,value

    def pod(self,role):
        from cps_compute.personal_qualification_probe import IMAGE
        from cps_compute.native_gpu_runtime import native_spec_sha256
        row=self.m['pods'][role];raw,value=self.get('pod',row)
        require(value['spec']['nodeName']==self.m['context']['node_pool']['node'],'Pod moved physical node')
        container=next(c for c in value['spec']['containers'] if c['name']=='notebook')
        status=next(c for c in value['status']['containerStatuses'] if c['name']=='notebook')
        require(container['image']==IMAGE and status['state'].get('running') and status['ready'] is True
                and status['imageID'].endswith(IMAGE.split('@')[1]),'Exact running imageID required')
        require(native_spec_sha256(value)==row['spec_sha256'],'Selected immutable Pod specification changed')
        if role=='pressure':
            require(container['resources']==self.m['resources'],'Actual exact catalog-derived resources required')
        return raw,value

    def rpc(self,role,body):
        row=self.m['pods'][role]
        return json.loads(self.command(['kubectl','--request-timeout=8s','-n',row['namespace'],'exec','-i',row['name'],
            '-c','notebook','--','python','-I','-c',REMOTE],canonical(body)))

    def initialize(self):
        from cps_compute.personal_qualification_probe import IMAGE,validate_context
        validate_context(self.m['context'])
        from cps_compute.native_qualification import NativeGroupQualification
        from cps_compute.policy import Policy
        policy=Policy(self.m['policy']);mode=NativeGroupQualification.from_config(self.m['operator'],policy)
        require(mode.personal_candidate and mode.workload_image==IMAGE and mode.policy_hash==self.m['context']['policy_hash'],
                'Exact prospective operator policy required')
        require(mode.resource_contract(next(iter(mode.profiles)))==self.m['resources'],'Canonical resources changed')
        require({(r['namespace'],r['name']) for r in self.m['pods'].values()} ==
                {(r['namespace'],r['pod']) for r in mode.workspaces.values()},
                'Only the exact two approved owned operator Pods may be measured')
        from cps_compute.native_node.config import NodeConfiguration
        from cps_compute.immutable_configmap import ImmutableConfigMapRef
        outer=self
        class ReadOnlyCore:
            def read_namespaced_config_map(self,name,namespace):
                raw=outer.command(['kubectl','--request-timeout=8s','-n',namespace,'get','configmap',name,'-o','json'])
                (outer.output/('authority-'+sha((namespace+'/'+name).encode())+'.json')).write_bytes(raw)
                return json.loads(raw)
        loaded=NodeConfiguration.load(ReadOnlyCore(),ImmutableConfigMapRef.from_dict(self.m['node_ref']),policy)
        require(loaded.operator_qualification_ref==self.m['operator_ref']
                and loaded.operator_qualification.document==mode.document,'Actual installed Node operator authority differs')
        proof=loaded.deployment.qualification_authority.proof
        for key in ('core_sha256','uvm_sha256','health_sha256'):
            require(self.m['context'][key]==proof[key],'Runtime build evidence differs from retained native authority')
        require(self.m['context']['node_pool']==mode.node_pool and self.m['context']['gate_image']==mode.gate_image,
                'Measured device/gate context differs from actual operator authority')

        raw,node=self.get('node',{'name':self.m['context']['node_pool']['node'],'uid':self.m['context']['node_pool']['node_uid']})
        require(node['status']['nodeInfo']['bootID']==self.m['context']['node_pool']['boot_id'],'API Node boot changed')
        (self.output/'node.json').write_bytes(raw)
        for role in ('pressure','peer'):
            raw,pod=self.pod(role);(self.output/(role+'-before.json')).write_bytes(raw)
        raw,observer=self.get('pod',self.m['observer']);(self.output/'observer.json').write_bytes(raw)
        require(observer['spec']['nodeName']==self.m['context']['node_pool']['node']
                and observer['spec'].get('hostPID') is True,'Existing selected host observer required')
        statuses=observer['status']['containerStatuses']
        require(len(statuses)==1 and statuses[0]['imageID']==self.m['observer']['image_id'],'Pinned observer image changed')
        # Registered observer ACK must precede the very first kernel anchor.
        self.start_window()
        raw,baseline=self.host_baseline()
        require(baseline['boot_id']==self.m['context']['node_pool']['boot_id'],'Observer boot changed')
        self.kernel_baseline=baseline['kernel_anchor'];self.baseline=baseline
        (self.output/'host-baseline.json').write_bytes(raw)
        # The actual immutable operator and Node references, never caller claims,
        # must be independently retained before child execution.
        for label in ('operator_ref','node_ref'):
            reference=self.m[label];raw,obj=self.get('configmap',reference)
            require(obj.get('immutable') is True and obj['metadata']['resourceVersion']==reference['resourceVersion']
                and 'sha256:'+sha(canonical(obj['data']))==reference['data_sha256'],'Immutable authority replaced')
            if label=='operator_ref':require(json.loads(obj['data'][reference['key']])==self.m['operator'],'Operator authority bytes changed')
            (self.output/(label+'.json')).write_bytes(raw)

    def check_final_authority(self):
        pool=self.m['context']['node_pool']
        raw,node=self.get('node',{'name':pool['node'],'uid':pool['node_uid']})
        require(node['status']['nodeInfo']['bootID']==pool['boot_id'],'Final API Node boot changed')
        (self.output/'node-final.json').write_bytes(raw)
        for label in ('node_ref','operator_ref'):
            reference=self.m[label];raw,obj=self.get('configmap',reference)
            require(obj.get('immutable') is True and obj['metadata']['resourceVersion']==reference['resourceVersion']
                and 'sha256:'+sha(canonical(obj['data']))==reference['data_sha256'],'Final immutable authority changed')
            (self.output/(label+'-final.json')).write_bytes(raw)

    def host_program(self,*,window=False):
        import base64
        from cps_compute import native_gpu_health
        raw=Path(native_gpu_health.__file__).read_bytes()
        require(sha(raw)==self.m['context']['health_sha256'],'Exact native health verifier source changed')
        (self.output/'native-health-source.py').write_bytes(raw)
        program=('import base64; h={};exec(compile(base64.b64decode('+repr(base64.b64encode(raw).decode())+'),"<reviewed-health>","exec"),h);'
            +'n={"__name__":'+repr('reviewed_collector' if window else '__main__')+',"_reviewed_health":h};exec(compile(base64.b64decode('
            +repr(base64.b64encode(self.host).decode())+'),"<reviewed-collector>","exec"),n)')
        if window:
            require(type(self.window_source) is bytes,'Pinned reset-window source required')
            program+=';w={"__name__":"__main__","_reviewed_collector":n};exec(compile(base64.b64decode('+repr(
                base64.b64encode(self.window_source).decode())+'),"<reviewed-window>","exec"),w)'
        return program

    def host_args(self,operation,*,window=False):
        observer=self.m['observer']
        return ['kubectl','--request-timeout=120s' if window else '--request-timeout=8s','-n',observer['namespace'],
            'exec','-i',observer['name'],'--','nsenter','-t','1','-m','-p','--','python3','-I','-c',
            self.host_program(window=window),operation]

    def start_window(self):
        from cps_compute.personal_qualification_probe import digest
        require(type(self.window_source) is bytes,'Reviewed reset-window source required')
        pins=json.loads((self.output/'source-pins.json').read_bytes())
        self.window_identity={'context_sha256':digest(canonical(self.m['context'])),
            'boot_id':self.m['context']['node_pool']['boot_id'],'driver_version':self.m['driver_version'],
            'source_pins':{key:'sha256:'+pins[name] for key,name in (
                ('probe','probe'),('collector','host_collector'),('window','window'),('manifest','manifest_raw'),('runner','runner'))},
            'node_ref':self.m['node_ref'],'operator_ref':self.m['operator_ref'],
            'caps':{role:{'path':row['cgroup'],'inode':row['inode'],'device':row['device'],
                'soft_bytes':10240*1048576,'hard_bytes':10240*1048576} for role,row in self.m['pods'].items()}}
        self.window=self.window_factory(self.host_args('--observe',window=True),
            {'context':self.m['context'],'identity':self.window_identity,'token':secrets.token_hex(32)},
            self.output/'reset-window.partial.jsonl')

    def check_peer(self,peer_pid):
        from cps_compute.personal_qualification_probe import IMAGE
        self.pod('peer');self.pod('pressure')
        raw=self.command(self.host_args('--host-peer'),canonical({'context':self.m['context'],
            'identity':self.window_identity,'pid':peer_pid,'token':self.roots['peer']+'/probe.py','image_id':IMAGE}))
        check=json.loads(raw)
        if self.peer_checks:require(check['binding']==self.peer_checks[0]['binding'],'Independent peer process changed')
        self.peer_checks.append(check)
        (self.output/('peer-binding-'+str(len(self.peer_checks))+'.json')).write_bytes(raw)


    def host_baseline(self):
        observer=self.m['observer']
        request={'context':self.m['context'],'cgroups':{
            role:{'path':row['cgroup'],'inode':row['inode'],'device':row['device']} for role,row in self.m['pods'].items()}}
        raw=self.command(['kubectl','--request-timeout=8s','-n',observer['namespace'],'exec','-i',observer['name'],
            '--','nsenter','-t','1','-m','-p','--','python3','-I','-c',self.host_program(),'--host-baseline'],canonical(request))
        return raw,json.loads(raw)

    def sample(self,event,peer_pid):
        from cps_compute.personal_qualification_probe import IMAGE
        row=self.m['pods']['pressure'];observer=self.m['observer']
        self.pod('pressure');self.pod('peer');self.get('pod',observer)
        request={'context':self.m['context'],'event':event,'token':self.roots['pressure']+'/probe.py',
            'cgroup':row['cgroup'],'inode':row['inode'],'device':row['device'],'image_id':IMAGE,
            'peer_pid':peer_pid,'peer_token':self.roots['peer']+'/probe.py','peer_cgroup':self.m['pods']['peer']['cgroup'],
            'expected_driver':self.m['driver_version'],'reset_baseline':self.kernel_baseline}
        raw=self.command(['kubectl','--request-timeout=8s','-n',observer['namespace'],'exec','-i',observer['name'],
            '--','nsenter','-t','1','-m','-p','--','python3','-I','-c',self.host_program(),'--host-sample'],canonical(request))
        value=json.loads(raw)
        if self.peer_identity is None:self.peer_identity=value['peer_process']
        require(value['peer_process']==self.peer_identity,'Owned peer process identity changed')
        (self.output/('host-'+str(event['monotonic_ns'])+'.json')).write_bytes(raw)
        return value['sample']

    def execute(self):
        import base64
        from cps_compute.personal_qualification_probe import derive_receipts
        samples=[];seen=set();peer_pid=None
        try:
            self.initialize()
            for role in ('peer','pressure'):
                self.attempted.add(role)
                result=self.rpc(role,{'operation':'setup','source':base64.b64encode(self.probe).decode(),
                    'sha256':sha(self.probe),'role':role});self.roots[role]=result['root']
                (self.output/'owned-roots.json').write_bytes(canonical(self.roots))
                if role=='peer':
                    deadline=time.monotonic()+15
                    while peer_pid is None:
                        require(time.monotonic()<deadline,'Peer startup timeout')
                        peer=self.rpc('peer',{'operation':'read','root':self.roots['peer']})
                        ticks=[json.loads(e) for e in peer.get('stdout','').split('\n')[:-1]]
                        if len(ticks)>=2:
                            peer_pid=ticks[0]['pid'];self.check_peer(peer_pid)
                        else:time.sleep(.2)
            deadline=time.monotonic()+65
            while True:
                require(time.monotonic()<deadline,'Bounded experiment expired')
                state={role:self.rpc(role,{'operation':'read','root':root}) for role,root in self.roots.items()}
                for role,value in state.items():
                    for key,raw in value.items():(self.output/(role+'-'+key)).write_text(raw)
                lines=state['pressure'].get('stdout','').split('\n')[:-1]
                for line in lines:
                    event=json.loads(line);key=sha(canonical(event))
                    if event['phase'] in ('frame','complete') or key in seen:continue
                    samples.append(self.sample(event,peer_pid));seen.add(key)
                    self.rpc('pressure',{'operation':'ack','root':self.roots['pressure'],'event_sha256':key})
                if 'exit' in state['pressure']:
                    require('exit' not in state['peer'],'Peer exited before post-pressure checks');break
                time.sleep(.2)
            for role in ('pressure','peer'):
                raw,_=self.pod(role);(self.output/(role+'-after.json')).write_bytes(raw)
            # Keep the same context alive THROUGH actual post-pressure cap/health
            # checks. Only then permit its final synchronized tick and exit.
            raw,post=self.host_baseline();(self.output/'host-post-pressure.json').write_bytes(raw)
            self.check_final_authority();self.check_peer(peer_pid)
            self.rpc('peer',{'operation':'finish-peer','root':self.roots['peer']})
            deadline=time.monotonic()+12
            while True:
                peer=self.rpc('peer',{'operation':'read','root':self.roots['peer']})
                if 'exit' in peer:break
                require(time.monotonic()<deadline,'Owned peer terminal timeout');time.sleep(.2)
            state['peer']=peer
            for key,value in peer.items():(self.output/('peer-'+key)).write_text(value)
            self.check_final_authority()
            raw,final=self.host_baseline();(self.output/'host-final.json').write_bytes(raw)
            raw_window=self.window.finish();(self.output/'reset-window.jsonl').write_bytes(raw_window)
            from cps_compute.personal_qualification_collect import kernel_window
            coverage=kernel_window(self.kernel_baseline,{k:v for k,v in final.items() if k!='cgroups'})
            (self.output/'reset-coverage.json').write_bytes(canonical(coverage))
            for role,prior in self.baseline['cgroups'].items():
                latest=final['cgroups'][role]
                require(all(latest[k]==prior[k] for k in ('path','inode','device','soft_bytes','hard_bytes','driver_version'))
                        and latest['used_bytes']<=prior['used_bytes'] and latest['gpu_processes']==prior['gpu_processes'],
                        'Owned allocation charge/process inventory did not recover to initial baseline')
            (self.output/'samples.json').write_bytes(canonical(samples))
            window_bundle={'raw_window':raw_window,'raw_peer':state['peer']['stdout'].encode(),
                'kernel_records':{'before':{k:v for k,v in self.baseline.items() if k!='cgroups'},
                                  'after':{k:v for k,v in final.items() if k!='cgroups'}},
                'identities':{**self.window_identity,'peer':self.peer_checks[0]['binding'],'peer_checks':self.peer_checks}}
            (self.output/'reset-window-input.json').write_bytes(canonical({**window_bundle,
                'raw_window':raw_window.hex(),'raw_peer':window_bundle['raw_peer'].hex()}))
            from cps_compute.personal_qualification_window import validate_reset_window
            window_observation=validate_reset_window(self.m['context'],**window_bundle)
            (self.output/'reset-window-observation.json').write_bytes(canonical(window_observation))
            receipts=derive_receipts(self.m['context'],state['pressure']['stdout'].encode(),samples,
                peer_raw=state['peer']['stdout'].encode(),peer_exit_code=int(state['peer']['exit']),
                probe_exit_code=int(state['pressure']['exit']),reset_window=window_bundle)
            measurement={'probe_sha256':'sha256:'+sha(state['pressure']['stdout'].encode()),
                'peer_sha256':'sha256:'+sha(state['peer']['stdout'].encode()),'samples':samples}
            (self.output/'measurement.json').write_bytes(canonical(measurement))
            (self.output/'retained-index.json').write_bytes(canonical({p.name:'sha256:'+sha(p.read_bytes())
                for p in self.output.iterdir() if p.is_file()}))
            (self.output/'review-material.json').write_bytes(canonical({'authoritative':False,'complete':True,'reset_status':window_observation['coverage'],
                'method':window_observation['method'],'exclusions':window_observation['exclusions'],'missing_probes':[],'probes':receipts}))
        finally:
            if self.window is not None:
                self.window.abandon()
                (self.output/'reset-window.partial.jsonl').write_bytes(b''.join(self.window.rows))
            # Only terminal, proven-owned directories. No remote signals, process
            # adoption, workspace Stop or automatic retry after uncertainty.
            cleanup={role:'hold-ambiguous-setup-no-adoption' for role in self.attempted-set(self.roots)}
            for role,root in self.roots.items():
                try:
                    state=self.rpc(role,{'operation':'read','root':root})
                    if 'exit' in state:
                        self.rpc(role,{'operation':'cleanup','root':root});cleanup[role]='owned-terminal-cleaned'
                    else:cleanup[role]='hold-until-watchdog-terminal'
                except Exception as exc:cleanup[role]='hold-'+type(exc).__name__
            (self.output/'cleanup.json').write_bytes(canonical(cleanup))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    for key in ('manifest','manifest-sha256','runner-sha256','probe-source','probe-sha256','collector-source','collector-sha256','window-source','window-sha256','output'):p.add_argument('--'+key)
    args=p.parse_args()
    if not args.execute:print('{"inert":true,"api_calls":false,"gpu_calls":false}');return
    require(all(vars(args).values()),'Reviewed source/manifest pins and fresh output required')
    require(sha(Path(__file__).read_bytes())==args.runner_sha256,'Runner source changed')
    manifest_raw=private(args.manifest,args.manifest_sha256)
    manifest=json.loads(manifest_raw)
    require(set(manifest)=={'version','context','policy','operator','resources','pods','observer','driver_version','operator_ref','node_ref'}
        and manifest['version']==1 and set(manifest['pods'])=={'pressure','peer'},'Closed reviewed manifest required')
    probe=Path(args.probe_source).read_bytes();host=Path(args.collector_source).read_bytes()
    require(sha(probe)==args.probe_sha256 and sha(host)==args.collector_sha256,'Probe/collector source changed')
    window=Path(args.window_source).read_bytes();require(sha(window)==args.window_sha256,'Window source changed')
    output=Path(args.output);output.mkdir(mode=0o700)
    for name,raw in (('runner',Path(__file__).read_bytes()),('probe',probe),('collector',host),('window',window)):
        (output/(name+'-source.py')).write_bytes(raw)
    (output/'manifest.raw.json').write_bytes(manifest_raw)
    (output/'manifest.json').write_bytes(canonical(manifest))
    (output/'source-pins.json').write_bytes(canonical({'runner':args.runner_sha256,'probe':args.probe_sha256,
        'host_collector':args.collector_sha256,'window':args.window_sha256,'manifest_raw':args.manifest_sha256}))
    Collector(manifest,probe,host,output,window_source=window).execute()


if __name__=='__main__':main()
