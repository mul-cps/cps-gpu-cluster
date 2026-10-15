"""Mode-bound operator node epoch; never approval, cap sealing or cleanup evidence.

The protected mutable epoch CM is distinct from the four qualified approval ACKs.
Node publication is independent of the dynamic v2 template consumer. No resource
creation or group/lease mutation is performed here.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID
from native_approval_process import observe_process, validate_process_declaration
from native_approval_process import _api_document
from native_approval_revision import canonical as _node_canonical
def _canonical(value):return _node_canonical(value).encode()

PROTOCOL = 'cps-native-kai-node-epoch/v1'
PROFILE = 'interactive-native-qualification-10'
EPOCH_FIELDS = frozenset({'node_uid', 'boot_id', 'driver_generation', 'gpu_uuid'})
BODY_FIELDS = frozenset({'protocol', 'mode', 'policy_hash', 'node_configuration', 'process',
                        'service_account_uid', 'driver_epoch', 'observed_at'})
_NAME = re.compile(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?')
_SHA = re.compile(r'sha256:[a-f0-9]{64}')


def require(value, message='Invalid protected operator epoch proof'):
    if not value: raise ValueError(message)


def uid(value):
    try:
        parsed=UUID(value);require(str(parsed)==value and parsed.int!=0)
    except (TypeError,ValueError,AttributeError):raise ValueError('Actual canonical nonzero UID required') from None
    return value


def document(raw):
    require(isinstance(raw,str) and len(raw.encode())<=1048576)
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate node epoch JSON field');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite node epoch JSON')))


def canonical_sha(value): return 'sha256:'+hashlib.sha256(_canonical(value)).hexdigest()


def reference(value, *, configuration=False):
    fields={'namespace','name','uid'}|({'resourceVersion','data_sha256'} if configuration else set())
    require(isinstance(value,dict) and set(value)==fields)
    require(all(isinstance(value[k],str) and _NAME.fullmatch(value[k]) for k in ['namespace','name']))
    uid(value['uid'])
    if configuration:
        require(isinstance(value['resourceVersion'],str) and re.fullmatch('[1-9][0-9]*',value['resourceVersion'])
                and isinstance(value['data_sha256'],str) and _SHA.fullmatch(value['data_sha256']))
    return json.loads(_canonical(value))


def declaration(value):
    require(isinstance(value,dict) and 'service_account_uid' in value,
            'Operator node config must pin the actual signed ServiceAccount UID')
    normal={k:v for k,v in value.items() if k!='service_account_uid'}
    return validate_process_declaration(normal),uid(value['service_account_uid'])


def epoch(value):
    require(isinstance(value,dict) and set(value)==EPOCH_FIELDS)
    for k in ['node_uid','boot_id','driver_generation']:uid(value[k])
    require(isinstance(value['gpu_uuid'],str) and value['gpu_uuid'].startswith('GPU-'))
    uid(value['gpu_uuid'][4:]);return json.loads(_canonical(value))


def node_configuration(cm, ref, *, expected=None):
    ref=reference(ref,configuration=True);meta=cm.get('metadata',{}) if isinstance(cm,dict) else {}
    require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
        and cm.get('immutable') is True and not cm.get('binaryData') and not meta.get('deletionTimestamp')
        and not meta.get('ownerReferences') and all(meta.get(k)==ref[k] for k in ['namespace','name','uid','resourceVersion'])
        and isinstance(cm.get('data'),dict) and set(cm['data'])=={'config.json'}
        and canonical_sha(cm['data'])==ref['data_sha256'],'Actual immutable operator node configuration changed')
    config=document(cm['data']['config.json'])
    require(isinstance(config,dict) and set(config)=={'version','enabled','mode','authority_namespace',
        'policy_hash','pool','workspaces','terminal_history'} and type(config['version']) is int and config['version']==2
        and config['enabled'] is True and config['mode']=='operator-qualification' and config['authority_namespace']==ref['namespace']
        and isinstance(config['policy_hash'],str) and _SHA.fullmatch(config['policy_hash'])
        and isinstance(config['terminal_history'],dict),'Only explicit measured operator node mode is admitted')
    require(isinstance(config['workspaces'],dict) and 1<=len(config['workspaces'])<=2
        and all(isinstance(k,str) and k.split(':',1)[0] in ('cps','cit') and ':' in k and isinstance(v,dict)
            and set(v)=={'profile','cap_mib'} and v['profile']==PROFILE and type(v['cap_mib']) is int and v['cap_mib']==10240
            for k,v in config['workspaces'].items()),'Only exact bounded qualification10 scopes are admitted')
    pool=config['pool'];require(isinstance(pool,dict) and EPOCH_FIELDS<=set(pool));epoch({k:pool[k] for k in EPOCH_FIELDS})
    require(type(pool.get('max_workspaces')) is int and 1<=pool['max_workspaces']<=2
        and type(pool.get('memory_budget_mib')) is int and 10240<=pool['memory_budget_mib']<=15360)
    if expected is not None:require(_canonical(config)==_canonical(expected),'Mounted and API node configurations differ')
    return config


def current_process(core,apps,decl,receipt_process,expected_sa_uid,pool):
    pod,actual=observe_process(core,apps,decl,receipt_process)
    require(pod['spec'].get('nodeName')==pool['node'],'Actual node process runs on another node')
    sa=_api_document(core,core.read_namespaced_service_account(decl['service_account'],decl['namespace']))
    meta=sa.get('metadata',{}) if isinstance(sa,dict) else {}
    require(isinstance(sa,dict) and sa.get('apiVersion')=='v1' and sa.get('kind')=='ServiceAccount'
        and meta.get('namespace')==decl['namespace'] and meta.get('name')==decl['service_account']
        and meta.get('uid')==expected_sa_uid and not meta.get('deletionTimestamp'),'Actual signed node SA identity changed')
    return pod,actual


def current_node(core,pool,observed):
    expected=epoch({k:pool[k] for k in EPOCH_FIELDS});require(epoch(observed)==expected,'Node/boot/driver/device epoch changed')
    node=_api_document(core,core.read_node(pool['node']));meta=node.get('metadata',{}) if isinstance(node,dict) else {}
    require(isinstance(node,dict) and node.get('apiVersion')=='v1' and node.get('kind')=='Node'
        and meta.get('name')==pool['node'] and meta.get('uid')==expected['node_uid'] and not meta.get('deletionTimestamp')
        and node.get('status',{}).get('nodeInfo',{}).get('bootID')==expected['boot_id'],'Actual post-Bind node/boot changed')
    return expected


class OperatorNodeEpochObserver:
    def __init__(self,policy,qualification,target,process,core,apps,*,ttl_seconds,now):
        from .native_qualification import NativeGroupQualification
        require(type(qualification) is NativeGroupQualification and qualification.policy_hash==policy.hash
            and qualification.profiles==frozenset({PROFILE}) and type(ttl_seconds) is int and 15<=ttl_seconds<=120 and callable(now))
        self.policy,self.mode=policy,qualification;self.target=reference(target)
        require(self.target['name']=='cps-native-kai-epoch-node' and self.target['namespace']==qualification.authority_namespace)
        self.decl,self.sa_uid=declaration(process);require(self.decl['namespace']==self.target['namespace'])
        self.core,self.apps,self.ttl,self.now=core,apps,ttl_seconds,now

    def observe(self):
        r=self.target;cm=_api_document(self.core,self.core.read_namespaced_config_map(r['name'],r['namespace']))
        meta=cm.get('metadata',{}) if isinstance(cm,dict) else {}
        require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
            and all(meta.get(k)==r[k] for k in r) and not meta.get('deletionTimestamp') and not meta.get('ownerReferences')
            and not cm.get('binaryData') and cm.get('immutable') in (None,False) and set(cm.get('data',{}))=={'epoch.json'})
        body=document(cm['data']['epoch.json']);require(isinstance(body,dict) and set(body)==BODY_FIELDS
            and body['protocol']==PROTOCOL and body['mode']=='operator-qualification' and body['policy_hash']==self.policy.hash
            and body['service_account_uid']==self.sa_uid)
        observed=datetime.fromisoformat(body['observed_at'].replace('Z','+00:00'));now=self.now()
        require(observed.tzinfo is not None and now.tzinfo is not None and 0<=(now-observed).total_seconds()<=self.ttl,
                'Operator node epoch is stale/future/undated')
        ref=reference(body['node_configuration'],configuration=True);require(ref['namespace']==r['namespace'])
        config=node_configuration(_api_document(self.core,self.core.read_namespaced_config_map(ref['name'],ref['namespace'])),ref)
        expected_workspaces={scope:{'profile':approval['profiles'][0],'cap_mib':10240} for scope,approval in self.mode.workspaces.items()}
        require(config['policy_hash']==self.policy.hash and _canonical(config['pool'])==_canonical(self.mode.node_pool)
            and _canonical(config['workspaces'])==_canonical(expected_workspaces),'Current node mode differs from the central typed operator authority')
        current_process(self.core,self.apps,self.decl,body['process'],self.sa_uid,config['pool'])
        result=current_node(self.core,config['pool'],body['driver_epoch'])
        # Mutable process, SA and node are observed twice; the configuration is
        # immutable and the exact UID/RV/full data is read again at the end.
        current_process(self.core,self.apps,self.decl,body['process'],self.sa_uid,config['pool'])
        current_node(self.core,config['pool'],body['driver_epoch'])
        node_configuration(_api_document(self.core,self.core.read_namespaced_config_map(ref['name'],ref['namespace'])),ref,expected=config)
        require(_api_document(self.core,self.core.read_namespaced_config_map(r['name'],r['namespace']))==cm,
                'Operator epoch target changed during observation')
        require(0<=(self.now()-observed).total_seconds()<=self.ttl)
        return result


class OperatorNodeEpochPublisher:
    def __init__(self,core,apps,target,node_ref,process,own_process,*,epoch,now):
        self.core,self.apps=core,apps;self.target=reference(target);self.node_ref=reference(node_ref,configuration=True)
        require(self.target['name']=='cps-native-kai-epoch-node' and self.node_ref['namespace']==self.target['namespace'])
        self.decl,self.sa_uid=declaration(process);require(self.decl['namespace']==self.target['namespace'])
        require(callable(epoch) and callable(now));self.epoch,self.now=epoch,now;self.process=json.loads(_canonical(own_process))

    def _actual(self,mounted):
        r=self.node_ref;config=node_configuration(_api_document(self.core,self.core.read_namespaced_config_map(r['name'],r['namespace'])),r,expected=mounted)
        _,process=current_process(self.core,self.apps,self.decl,self.process,self.sa_uid,config['pool'])
        result=current_node(self.core,config['pool'],self.epoch())
        return config,process,result

    def _target(self,cm):
        m=cm.get('metadata',{}) if isinstance(cm,dict) else {};r=self.target
        require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
            and all(m.get(k)==v for k,v in r.items()) and isinstance(m.get('resourceVersion'),str) and m['resourceVersion']
            and not m.get('ownerReferences') and not m.get('deletionTimestamp') and not cm.get('binaryData')
            and cm.get('immutable') in (None,False) and set(cm.get('data',{}))=={'epoch.json'})
        old=document(cm['data']['epoch.json']);require(old=={} or (isinstance(old,dict) and set(old)==BODY_FIELDS
            and old['protocol']==PROTOCOL and old['mode']=='operator-qualification' and old['process']['namespace']==r['namespace']),
            'Foreign node epoch target cannot be adopted')
        return cm

    def acknowledge(self,mounted):
        config,process,result=self._actual(mounted);now=self.now();require(now.tzinfo is not None)
        body={'protocol':PROTOCOL,'mode':'operator-qualification','policy_hash':config['policy_hash'],
            'node_configuration':self.node_ref,'process':process,'service_account_uid':self.sa_uid,
            'driver_epoch':result,'observed_at':now.isoformat()}
        r=self.target;before=self._target(_api_document(self.core,self.core.read_namespaced_config_map(r['name'],r['namespace'])))
        require(self._actual(mounted)==(config,process,result),'Current node observation changed before publication')
        data={'epoch.json':_canonical(body).decode()};patch=[{'op':'test','path':'/metadata/uid','value':r['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':before['metadata']['resourceVersion']},
            {'op':'test','path':'/data','value':before['data']},{'op':'replace','path':'/data','value':data}]
        after=self._target(_api_document(self.core,self.core.patch_namespaced_config_map(r['name'],r['namespace'],patch)))
        require(after['data']==data,'Unknown node epoch publication outcome')
        original=json.loads(_canonical(before));normalized=json.loads(_canonical(after))
        normalized['data']=original['data'];normalized['metadata']['resourceVersion']=original['metadata']['resourceVersion']
        original['metadata'].pop('managedFields',None);normalized['metadata'].pop('managedFields',None)
        require(original==normalized,'Epoch patch changed unrelated object fields')
        require(self._target(_api_document(self.core,self.core.read_namespaced_config_map(r['name'],r['namespace'])))==after,
                'Epoch readback changed')
        require(self._actual(mounted)==(config,process,result),'Actual health/epoch/config changed after publication')
        return json.loads(_canonical(body))

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
            require(token and len(token)<=65536 and not re.search(r'\s',token) and len(token.split('.'))==3)
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
