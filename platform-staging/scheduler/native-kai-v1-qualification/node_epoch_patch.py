"""Offline opt-in patch of exact captured507 code; no API, file or GPU writes."""
import argparse
import hashlib
import json
from pathlib import Path

BASE_SHA='b1deccd3e48b8c38ec0c87416dc04d9ae860e260910ff929f697be5d17e14429'
PROCESS_SHA='e121dd491d709d945b96fa475902486f783151f76f903344d06871b49aab2875'
REVISION_SHA='ddaaf9593dfbc9cba2d4aa3227102895a435e2537346ddd467c4941c0201658d'


def need(x,text):
    if not x:raise ValueError(text)


def once(source,old,new):
    need(source.count(old)==1,'Exact507 seam changed: '+old[:80]);return source.replace(old,new,1)


WRAPPER='''
class OperatorEpochRawAPI:
    # This opt-in transport does not alter the ordinary node client's methods.
    def __init__(self,kube,service_account):
        import ssl,urllib.parse,urllib.request
        from pathlib import Path
        parsed=urllib.parse.urlsplit(kube.base)
        require(parsed.scheme=='https' and parsed.hostname is not None and not parsed.username
            and not parsed.password and parsed.path=='' and not parsed.query and not parsed.fragment)
        handlers=[h for h in kube.opener.handlers if isinstance(h,urllib.request.HTTPSHandler)]
        require(len(handlers)==1 and handlers[0]._context is not None
            and handlers[0]._context.verify_mode==ssl.CERT_REQUIRED and handlers[0]._context.check_hostname,
            'Existing authenticated Kubernetes TLS context required')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        self.base=kube.base;self.token_path=Path(service_account)/'token'
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),
            urllib.request.HTTPSHandler(context=handlers[0]._context))

    def token(self):
        import os,stat
        parent=self.token_path.parent.resolve(strict=True);info=parent.stat()
        require(info.st_uid in (0,os.geteuid()) and not info.st_mode & 0o022)
        resolved=self.token_path.resolve(strict=True)
        require(resolved.is_relative_to(parent),'Projected node token escapes configured volume')
        fd=os.open(resolved,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            info=os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid in (0,os.geteuid())
                and not info.st_mode & 0o022 and info.st_size<=65536)
            token=os.read(fd,65537).decode().strip()
            require(token and len(token)<=65536 and not re.search(r'\\s',token) and len(token.split('.'))==3)
            return token
        finally:os.close(fd)

    def call(self,method,path,value=None):
        import urllib.error,urllib.request
        require(method in ('GET','PATCH') and path.startswith(('/api/v1/','/apis/apps/v1/'))
            and '?' not in path and '#' not in path and '..' not in path)
        raw=_canonical(value) if value is not None else None
        require(raw is None or len(raw)<=1048576)
        request=urllib.request.Request(self.base+path,data=raw,method=method,headers={
            'Authorization':'Bearer '+self.token(),
            'Content-Type':'application/json-patch+json' if method=='PATCH' else 'application/json'})
        try:
            with self.opener.open(request,timeout=5) as response:
                require(response.status==200 and response.geturl()==self.base+path)
                result=document(response.read(1048577).decode())
                require(isinstance(result,dict),'Actual bounded raw Kubernetes object required')
                return result
        except urllib.error.HTTPError as error:
            if method=='GET' and error.code==404:return None
            raise ValueError('Operator node epoch API rejected request or has unknown outcome') from None
        except (OSError,UnicodeError) as error:
            raise ValueError('Operator node epoch API unavailable or has unknown outcome') from error

    @staticmethod
    def path(prefix,namespace,kind,name):
        require(all(isinstance(x,str) and _NAME.fullmatch(x) for x in (name,namespace)))
        return prefix+'/namespaces/'+namespace+'/'+kind+'/'+name
    def read_namespaced_config_map(self,name,namespace):return self.call('GET',self.path('/api/v1',namespace,'configmaps',name))
    def patch_namespaced_config_map(self,name,namespace,value):return self.call('PATCH',self.path('/api/v1',namespace,'configmaps',name),value)
    def read_namespaced_pod(self,name,namespace):return self.call('GET',self.path('/api/v1',namespace,'pods',name))
    def read_namespaced_service_account(self,name,namespace):return self.call('GET',self.path('/api/v1',namespace,'serviceaccounts',name))
    def read_node(self,name):
        require(isinstance(name,str) and _NAME.fullmatch(name));return self.call('GET','/api/v1/nodes/'+name)
    def read_namespaced_deployment(self,name,namespace):return self.call('GET',self.path('/apis/apps/v1',namespace,'deployments',name))
    def read_namespaced_replica_set(self,name,namespace):return self.call('GET',self.path('/apis/apps/v1',namespace,'replicasets',name))


def build_installed(agent,kube,config,bundle,state,driver,verifier,models,settings_path,service_account):
    # Disabled startup stays inert; current node code owns the ordinary client.
    backend=agent.load_source('_operator_epoch_private_backend',agent.snapshot_sources()['node_backend.py'].encode(),
        agent.SOURCE_PINS['node_backend.py'],'node_backend.py')
    settings=backend.private_read(settings_path,0)
    require(isinstance(settings,dict) and type(settings.get('enabled')) is bool)
    if not settings['enabled']:
        require(set(settings)=={'enabled'});return None
    require(set(settings)=={'enabled','version','target','node_configuration','process','ttlSeconds'}
        and type(settings['version']) is int and settings['version']==1 and type(settings['ttlSeconds']) is int
        and 15<=settings['ttlSeconds']<=120)
    agent.validate_config(config)
    require(config['version']==2 and config['mode']=='operator-qualification')
    import os,time
    declared=settings['process'];own={key:declared[key] for key in ['namespace','container','image','service_account']}
    own.update(name=os.environ.get('CPS_NATIVE_OPERATOR_POD_NAME'),uid=os.environ.get('CPS_NATIVE_OPERATOR_POD_UID'))
    require(os.environ.get('CPS_NATIVE_OPERATOR_POD_NAMESPACE')==own['namespace'])
    api=OperatorEpochRawAPI(kube,service_account)
    def current_epoch():
        # Existing protected generation/driver/no-MIG/UVM health path, no cap claim.
        return agent.abort_current_epoch(config,state,driver,verifier,models).__dict__
    publisher=OperatorNodeEpochPublisher(api,api,settings['target'],settings['node_configuration'],declared,own,
        epoch=current_epoch,now=lambda:datetime.now(timezone.utc))
    last=[None]
    def acknowledge(actual):
        now=time.monotonic()
        if last[0] is None or now-last[0]>=settings['ttlSeconds']/3:
            publisher.acknowledge(actual);last[0]=now
    # Validate and read back before the first protected cap reconciliation.
    acknowledge(config)
    return acknowledge
'''


def render(original,core_source):
    need(isinstance(original,dict) and hashlib.sha256(original['node_agent.py'].encode()).hexdigest()==BASE_SHA,'Exact actual507 source required')
    need(hashlib.sha256(original['native_approval_process.py'].encode()).hexdigest()==PROCESS_SHA
        and hashlib.sha256(original['native_approval_revision.py'].encode()).hexdigest()==REVISION_SHA,'Actual process/revision helper pins changed')
    shared=once(core_source,'from .native_group_process import observe_process, validate_process_declaration',
                'from native_approval_process import observe_process, validate_process_declaration')
    shared=once(shared,'from .native_group_revision import _api_document, _canonical',
                'from native_approval_process import _api_document\nfrom native_approval_revision import canonical as _node_canonical\ndef _canonical(value):return _node_canonical(value).encode()')
    shared+=WRAPPER;digest=hashlib.sha256(shared.encode()).hexdigest();out=dict(original)
    source=once(original['node_agent.py'],'cri_socket, approval=None):','cri_socket, approval=None, operator_epoch=None):')
    source=once(source,'    for iteration in range(iterations):\n','    for iteration in range(iterations):\n        if operator_epoch is not None: operator_epoch(config)\n')
    source=once(source,"    parser.add_argument('--execute', action='store_true')", "    parser.add_argument('--execute', action='store_true')\n    parser.add_argument('--operator-epoch-config',type=Path)")
    source=once(source,"    require(config['enabled'], 'Node authority deployment is disabled')", "    require(args.operator_epoch_config is None or all(v is None for v in (args.approval_reference,args.approval_template,args.approval_process,args.approval_acknowledgment)),\n            'Operator epoch and dynamic v2 consumer cannot overlap')\n    require(config['enabled'], 'Node authority deployment is disabled')")
    before="        driver = modules['manual'].Nvml()\n        run(config, bundle, state, kube, driver, iterations=args.iterations, interval=args.interval,"
    after=f"""        driver = modules['manual'].Nvml()
        operator_epoch = None
        if args.operator_epoch_config is not None:
            # Reuse exactly the unchanged vendored process proof and raw API codecs.
            revision = load_source('native_approval_revision',(args.bundle/'native_approval_revision.py').read_bytes(),'{REVISION_SHA}','native_approval_revision.py')
            process = load_source('native_approval_process',(args.bundle/'native_approval_process.py').read_bytes(),'{PROCESS_SHA}','native_approval_process.py')
            epoch_module = load_source('_native_operator_epoch',(args.bundle/'native_operator_epoch.py').read_bytes(),'{digest}','native_operator_epoch.py')
            operator_epoch = epoch_module.build_installed(sys.modules[__name__],kube,config,args.bundle,state,driver,modules['health'],modules['models'],args.operator_epoch_config,args.service_account)
        run(config, bundle, state, kube, driver, iterations=args.iterations, interval=args.interval,"""
    source=once(source,before,after)
    source=once(source,'crictl=args.crictl, cri_socket=args.cri_socket, approval=approval)',
                'crictl=args.crictl, cri_socket=args.cri_socket, approval=approval, operator_epoch=operator_epoch)')
    out['node_agent.py']=source;out['native_operator_epoch.py']=shared;return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-bundle',type=Path);p.add_argument('--core-source',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if not a.output:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False}));return
    need(a.base_bundle and a.core_source,'Exact private base and tested core source required')
    source=json.loads(a.base_bundle.read_text());data=render(source['data'],a.core_source.read_text());a.output.mkdir(mode=0o700)
    for name,value in data.items():
        f=a.output/name;f.write_text(value);f.chmod(0o600)
    receipt={'base_sha256':BASE_SHA,'module_sha256':hashlib.sha256(a.core_source.read_bytes()).hexdigest(),
        'files':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in data.items()},'live_applied':False,'hardware_qualified':False}
    (a.output/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')

if __name__=='__main__':main()
