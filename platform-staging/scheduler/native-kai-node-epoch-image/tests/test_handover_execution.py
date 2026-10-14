"""Offline actual-identity boundary tests; no API or GPU calls."""
import copy,hashlib,importlib.util,json,tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
e=module('node_exec',ROOT/'handover_execution.py')

class API:
    def __init__(self,deployment,pod=None):self.deployment=deployment;self.pod=pod;self.calls=[];self.matching=[]
    def get(self,kind,ns,name,missing=False):
        self.calls.append(('get',kind,ns,name))
        return self.deployment if kind=='Deployment' else self.pod
    def command(self,args,data=None):
        self.calls.append(('command',args,data));return {'items':self.matching}

class Tests(unittest.TestCase):
    def setUp(self):
        self.m=SimpleNamespace(r=SimpleNamespace(canonical_sha256=lambda v:'sha256:'+hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()))
        node={'metadata':{'uid':'owned-controller','namespace':'cps-native-system','name':'cps-native-node-agent'},
              'spec':{'replicas':1,'selector':{'matchLabels':{'app':'node'}},'template':{'spec':{
                  'volumes':[{'name':'state','hostPath':{'path':'/actual/private-node-state','type':'Directory'}}],
                  'imagePullSecrets':[{'name':'retained-pull'}]}}}}
        old={'metadata':{'uid':'owned-old-pod','name':'old-node-pod','namespace':'cps-native-system'}}
        self.plan={'request':{'observations':{'deployments':{'node':node},'pods':{'node':old}},
                    'qualification':{'node_pool':{'node':'k3s-wk-gpu2','node_uid':'actual-node-uid'}}},
                    'projection':{'expected_deployments':{'node':{'uid':'owned-controller','namespace':'cps-native-system','name':'cps-native-node-agent'}},
                                  'process_declarations':{'node':{'image':'ghcr.io/mul-cps/cps-compute@sha256:'+'a'*64}}}}

    def test_replicas_zero_old_ready_pod_is_not_an_admission_barrier(self):
        d=copy.deepcopy(self.plan['request']['observations']['deployments']['node']);d['spec']['replicas']=0
        api=API(d,{'metadata':{'uid':'owned-old-pod'},'status':{'phase':'Running'}})
        with self.assertRaises(ValueError):e.absent_node(api,self.m,self.plan)
        api.pod=None;self.assertTrue(e.absent_node(api,self.m,self.plan)==d)
        api.matching=[{'metadata':{'uid':'foreign-same-selector'}}]
        with self.assertRaises(ValueError):e.absent_node(api,self.m,self.plan)

    def test_probe_is_only_readonly_proc_boot_authority_no_token_devices_or_privilege(self):
        r=e.readonly_probe(self.m,self.plan,'print("fixture")');s=r['spec'];c=s['containers'][0]
        self.assertFalse(s['automountServiceAccountToken']);self.assertIs(c['securityContext']['privileged'],False)
        self.assertEqual(c['securityContext']['capabilities'],{'drop':['ALL'],'add':['SYS_ADMIN']})
        self.assertTrue(all(v['readOnly'] for v in c['volumeMounts']))
        self.assertEqual(s['volumes'][-1]['hostPath']['path'],'/actual/private-node-state/authority')
        self.assertTrue(all(not v['hostPath']['path'].startswith('/dev') for v in s['volumes']))
        self.assertNotIn('nvidia.com/gpu',c['resources']['requests'])

    def test_probe_rejects_admission_added_privilege_devices_and_unknown_fields(self):
        candidate=e.readonly_probe(self.m,self.plan,'print("fixture")')
        e.probe_spec(candidate['spec'],candidate['spec'])
        for path,value in [(('hostPID',),True),(('hostIPC',),True),(('hostNetwork',),True),
             (('containers',0,'securityContext','privileged'),True),
             (('containers',0,'securityContext','capabilities','add'),['SYS_ADMIN','SYS_RAWIO']),
             (('containers',0,'volumeMounts',0,'readOnly'),False),
             (('containers',0,'command'),['python3','-c','print("tampered")']),
             (('containers',0,'volumeDevices'),[{'name':'gpu','devicePath':'/dev/nvidia0'}]),
             (('initContainers',),[{'name':'foreign'}])]:
            actual=copy.deepcopy(candidate['spec']);v=actual
            for k in path[:-1]:v=v[k]
            v[path[-1]]=value
            with self.assertRaises(ValueError):e.probe_spec(actual,candidate['spec'])
        actual=copy.deepcopy(candidate['spec']);actual.update(serviceAccountName='default',serviceAccount='default',priority=0,preemptionPolicy='PreemptLowerPriority')
        for k in ('hostPID','hostIPC','hostNetwork'):actual.pop(k)
        e.probe_spec(actual,candidate['spec'])

    def test_existing_activation_loader_retained_in_node_scope(self):
        prior=SimpleNamespace(load=lambda *a:'loaded',O=Path('/private/existing'))
        old=SimpleNamespace(g=prior)
        scope=e.bind_existing_executor(old,self.m,'helper','renderer',SimpleNamespace(validate_scope=lambda p:p),'proof-sha')
        self.assertIs(scope.load,prior.load);self.assertEqual(scope.O,prior.O)
        self.assertEqual(old.g.load('activation'),'loaded')

    def test_probe_cleanup_uses_actual_uid_and_current_rv_never_name_fallback(self):
        created={'metadata':{'namespace':'cps-native-system','name':'owned-probe','uid':'created-uid'}}
        api=API(None,{'metadata':{'uid':'created-uid','resourceVersion':'current-rv'}})
        e.delete_probe(api,self.m,created);call=api.calls[-1]
        self.assertEqual(call[2]['preconditions'],{'uid':'created-uid','resourceVersion':'current-rv'})
        api.pod['metadata']['uid']='foreign-replacement';before=len(api.calls)
        with self.assertRaises(ValueError):e.delete_probe(api,self.m,created)
        self.assertEqual(len(api.calls),before+1)

    def test_full_raw_terminal_logs_are_retained_before_reporting_actual_error(self):
        meta={'namespace':'cps-native-system','name':'owned-reader','uid':'owned-created-uid'}
        raw=b'Traceback (most recent call last):\nPermissionError: [Errno 1] Operation not permitted: cps_native_caps\n'
        api=SimpleNamespace(prefix=['kubectl','--context','fixture'],get=lambda *a:{'metadata':{'uid':meta['uid']},
            'status':{'containerStatuses':[{'name':'reader','state':{'terminated':{'exitCode':1,'reason':'Error'}}}]}})
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'private-logs'
            def write(path,value,raw=False):
                path.write_bytes(value if raw else json.dumps(value).encode());path.chmod(0o600)
            m=SimpleNamespace(write=write,r=SimpleNamespace(parse=json.loads))
            with patch.object(e,'PROBE_LOG_ROOT',root),patch.object(e.subprocess,'run',return_value=SimpleNamespace(stdout=raw,stderr=b'',returncode=0)) as run:
                with self.assertRaisesRegex(e.ProbeTerminalError,'PermissionError.*cps_native_caps'):e.probe_log(api,m,meta)
                self.assertNotIn('--tail=1',run.call_args.args[0])
            logs=list(root.iterdir());self.assertEqual(len(logs),1)
            self.assertEqual((logs[0]/'stdout.private').read_bytes(),raw)
            receipt=json.loads((logs[0]/'receipt.json').read_text());self.assertEqual(receipt['terminal']['exitCode'],1)
            self.assertEqual(receipt['stdout_sha256'],hashlib.sha256(raw).hexdigest())


if __name__=='__main__':unittest.main()
