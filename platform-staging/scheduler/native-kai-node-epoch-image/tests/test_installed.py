"""CPU-only installed source/import/health/operator proofs; no hardware claim."""
import ast
import copy
from datetime import datetime,timezone
import importlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import node_agent as agent
import native_operator_epoch as operator
import native_gpu_health as health

HERE=Path(__file__).parent
FIXTURE=json.loads((HERE/'operator-fixture.json').read_text())
BUNDLE=Path('/opt/native')


class Installed(unittest.TestCase):
    def test_every_runtime_module_imports_without_new_installed_core(self):
        for f in BUNDLE.glob('*.py'):
            importlib.import_module(f.stem)
        bundle=agent.load_bundle(BUNDLE)
        self.assertTrue(callable(bundle[2]['health'].validate_native_driver_health))
        self.assertFalse(importlib.util.find_spec('cps_compute.native_group_process'))
        self.assertFalse(importlib.util.find_spec('cps_compute_hub'))
        for name in ['node_agent.py','native_operator_epoch.py']:
            tree=ast.parse((BUNDLE/name).read_text())
            self.assertFalse(any(isinstance(n,ast.Import) and any(a.name.startswith('cps_compute') for a in n.names) for n in ast.walk(tree)))
            relative=[n for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.level]
            self.assertEqual([(n.module,n.level) for n in relative],[] if name=='node_agent.py' else [('native_qualification',1)])
            # That sole lazy import belongs to the unused Gateway observer, not
            # node startup/publication. No Core namespace is injected in tests.

    def test_existing_v2_process_observer_rejects_changed_controller(self):
        import native_approval_process as process
        s=copy.deepcopy(FIXTURE)
        core=SimpleNamespace(read_namespaced_pod=lambda *a:copy.deepcopy(s['pod']))
        apps=SimpleNamespace(read_namespaced_deployment=lambda *a:copy.deepcopy(s['controller']),read_namespaced_replica_set=lambda *a:copy.deepcopy(s['rs']))
        decl={k:v for k,v in s['declaration'].items() if k!='service_account_uid'}
        pod,receipt=process.observe_process(core,apps,decl,s['process']);self.assertEqual(receipt,s['process'])
        s['controller']['spec']['template']['spec']['containers'][0].setdefault('args',[]).append('--foreign')
        with self.assertRaises(ValueError):process.observe_process(core,apps,decl,s['process'])

    def test_default_off_does_not_open_api_driver_or_settings(self):
        with patch.object(agent,'read_config',side_effect=AssertionError('configuration I/O')),patch.object(agent,'load_bundle',side_effect=AssertionError('driver/API initialization')),redirect_stdout(io.StringIO()) as out:
            agent.main(['--operator-epoch-config','/absent','--config','/absent'])
        self.assertEqual(json.loads(out.getvalue())['api_calls'],False)

    def test_operator_and_v2_are_exclusive_before_any_api_or_gpu(self):
        args=['--execute','--config','/absent','--operator-epoch-config','/absent','--approval-reference','/r','--approval-template','/t','--approval-process','/p','--approval-acknowledgment','/a']
        with patch.object(agent,'read_config',return_value={'enabled':True}),patch.object(agent,'load_bundle',side_effect=AssertionError('unexpected initialization')):
            with self.assertRaisesRegex(ValueError,'cannot overlap'):agent.main(args)

    def test_explicit_disabled_factory_does_not_observe_api_or_gpu(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'settings.json';p.write_text('{"enabled":false}');p.chmod(0o600)
            with patch.object(operator,'OperatorEpochRawAPI',side_effect=AssertionError('API initialized')):
                self.assertIsNone(operator.build_installed(agent,None,None,BUNDLE,None,None,None,None,p,Path('/absent')))

    def factory(self,damage=None):
        s=copy.deepcopy(FIXTURE);s['ack']={'apiVersion':'v1','kind':'ConfigMap','metadata':{**s['target'],'resourceVersion':'3'},'data':{'epoch.json':'{}'}}
        calls=[]
        class API:
            def __init__(self,*args):pass
            def read_namespaced_config_map(self,name,namespace):return copy.deepcopy(s['ack'] if name==s['target']['name'] else s['config_cm'])
            def read_namespaced_pod(self,*args):return copy.deepcopy(s['pod'])
            def read_namespaced_service_account(self,*args):return copy.deepcopy(s['sa'])
            def read_node(self,*args):return copy.deepcopy(s['node'])
            def read_namespaced_deployment(self,*args):return copy.deepcopy(s['controller'])
            def read_namespaced_replica_set(self,*args):return copy.deepcopy(s['rs'])
            def patch_namespaced_config_map(self,name,namespace,ops):
                for op in ops:
                    if op['op']=='test':
                        actual=s['ack']['data'] if op['path']=='/data' else s['ack']['metadata'][op['path'].split('/')[-1]]
                        if actual!=op['value']:raise ValueError('Actual UID/RV/data conflict')
                    else:
                        self_op=op;assert op['op']=='replace' and op['path']=='/data';s['ack']['data']=copy.deepcopy(op['value'])
                calls.append(ops);s['ack']['metadata']['resourceVersion']='4'
                if damage=='unknown-patch':raise TimeoutError('Response lost after actual patch')
                return copy.deepcopy(s['ack'])
        if damage in ['pod','sa','node']:s[damage]['metadata']['uid']='66666666-6666-4666-8666-666666666666'
        if damage=='group-mode':s['config']['mode']='qualified-group'
        if damage=='cap5':next(iter(s['config']['workspaces'].values())).update(profile='interactive-native-qualification-5',cap_mib=5120)
        settings={'enabled':True,'version':1,'target':s['target'],'node_configuration':s['config_ref'],'process':s['declaration'],'ttlSeconds':30}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'settings.json';p.write_text(json.dumps(settings));p.chmod(0o600)
            epoch_calls=[]
            def actual_epoch(*args):epoch_calls.append(1);return SimpleNamespace(**s['epoch'])
            env={'CPS_NATIVE_OPERATOR_POD_NAME':s['process']['name'],'CPS_NATIVE_OPERATOR_POD_UID':s['process']['uid'],'CPS_NATIVE_OPERATOR_POD_NAMESPACE':s['process']['namespace']}
            with patch.object(operator,'OperatorEpochRawAPI',API),patch.object(agent,'abort_current_epoch',side_effect=actual_epoch),patch.dict(os.environ,env):
                callback=operator.build_installed(agent,None,s['config'],BUNDLE,Path(td),None,None,None,p,Path('/absent'))
                self.assertTrue(callable(callback));callback(s['config'])
        return s,calls,epoch_calls

    def test_enabled_operator_installed_factory_uses_exact_vendored_process_and_cas(self):
        s,calls,epochs=self.factory();self.assertEqual(len(calls),1);self.assertEqual(len(epochs),3)
        body=json.loads(s['ack']['data']['epoch.json']);self.assertEqual(body['driver_epoch'],s['epoch']);self.assertEqual(body['service_account_uid'],s['declaration']['service_account_uid'])
        self.assertEqual([x['path'] for x in calls[0]],['/metadata/uid','/metadata/resourceVersion','/data','/data'])

    def test_foreign_identity_group_mode_cap_or_unknown_result_never_succeeds(self):
        for damage in ['pod','sa','node','group-mode','cap5','unknown-patch']:
            with self.subTest(damage=damage),self.assertRaises((ValueError,TimeoutError)):self.factory(damage)


class DriverHealth(unittest.TestCase):
    def fixture(self,root):
        meta=root/'metadata';meta.mkdir(mode=0o700);authority=root/'authority';authority.mkdir(mode=0o700)
        for name,value in {'nvidia/version':health.DRIVER_VERSION,**health.GUARD_PARAMETERS,**{name+'/srcversion':row['srcversion'] for name,row in health.MODULE_BUILDS.items()}}.items():
            p=meta/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value);p.chmod(0o400 if name=='nvidia/parameters/NVreg_CpsNativeImportGuard' else 0o600)
        epoch=FIXTURE['epoch'];manifest={'protocol':health.PROTOCOL,'boot_id':epoch['boot_id'],'driver_generation':epoch['driver_generation'],'kernel_release':os.uname().release,'driver_version':health.DRIVER_VERSION,'modules':{}}
        for name,build in health.MODULE_BUILDS.items():
            stat=(meta/name).stat();manifest['modules'][name]={**build,'sysfs_device':stat.st_dev,'sysfs_inode':stat.st_ino}
        p=authority/'driver-generation';p.write_text(epoch['driver_generation']);p.chmod(0o600)
        p=authority/health.MANIFEST_NAME;p.write_text(json.dumps(manifest));p.chmod(0o400)
        return meta,authority

    def check(self,meta,authority):return health.validate_native_driver_health(str(meta),authority_directory=str(authority),boot_id=FIXTURE['epoch']['boot_id'])

    def test_existing_exact_loaded_health_cpu_fixture_passes(self):
        with tempfile.TemporaryDirectory() as td:
            meta,auth=self.fixture(Path(td));self.assertEqual(self.check(meta,auth),FIXTURE['epoch']['driver_generation'])

    def test_missing_stale_or_weakened_health_is_still_denied(self):
        for damage in ['missing','generation','guard','uvm','srcversion','inode','mode','directory','symlink']:
            with self.subTest(damage=damage),tempfile.TemporaryDirectory() as td:
                meta,auth=self.fixture(Path(td))
                if damage=='missing':(auth/health.MANIFEST_NAME).unlink()
                elif damage=='generation':(auth/'driver-generation').write_text('66666666-6666-4666-8666-666666666666')
                elif damage=='guard':
                    p=meta/'nvidia/parameters/NVreg_CpsNativeImportGuard';p.chmod(0o600);p.write_text('0');p.chmod(0o400)
                elif damage=='uvm':(meta/'nvidia_uvm/parameters/uvm_deny_managed_mmap').write_text('N')
                elif damage=='srcversion':(meta/'nvidia/srcversion').write_text('foreign')
                elif damage=='inode':(meta/'nvidia').rename(meta/'old-nvidia');(meta/'nvidia').mkdir();
                elif damage=='mode':(auth/'driver-generation').chmod(0o644)
                elif damage=='directory':auth.chmod(0o777)
                else:
                    p=meta/'nvidia/parameters/NVreg_CpsNativeImportGuard';p.rename(p.with_name('original'));p.symlink_to('original')
                with self.assertRaises((ValueError,OSError)):self.check(meta,auth)



class Transport(unittest.TestCase):
    def test_python312_actual_tls_patch_token_rotation_and_redirect_denial(self):
        import ssl,subprocess,threading,urllib.request
        from http.server import BaseHTTPRequestHandler,HTTPServer
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);key=root/'key';cert=root/'cert';volume=root/'sa';volume.mkdir(mode=0o700)
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1'],check=True,capture_output=True)
            token=volume/'token';token.write_text('test.first.signature');token.chmod(0o600)
            rows=[];status=[200]
            class Handler(BaseHTTPRequestHandler):
                def operation(self):
                    raw=self.rfile.read(int(self.headers.get('Content-Length','0')));rows.append((self.command,dict(self.headers),raw))
                    self.send_response(status[0])
                    if status[0]==302:self.send_header('Location','https://127.0.0.1:1/foreign')
                    self.end_headers();self.wfile.write(b'{"apiVersion":"v1","kind":"ConfigMap"}')
                do_PATCH=operation;do_GET=operation
                def log_message(self,*args):pass
            server=HTTPServer(('127.0.0.1',0),Handler);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key);server.socket=context.wrap_socket(server.socket,server_side=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                context=ssl.create_default_context(cafile=str(cert));kube=SimpleNamespace(base='https://127.0.0.1:'+str(server.server_port),opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context)))
                api=operator.OperatorEpochRawAPI(kube,volume);ops=[{'op':'test','path':'/metadata/uid','value':FIXTURE['target']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':'3'},{'op':'test','path':'/data','value':{'epoch.json':'{}'}},{'op':'replace','path':'/data','value':{'epoch.json':'{}'}}]
                api.patch_namespaced_config_map('cps-native-kai-epoch-node','cps-native-system',ops)
                self.assertEqual(rows[-1][1]['Content-Type'],'application/json-patch+json');self.assertEqual(json.loads(rows[-1][2]),ops)
                token.write_text('test.rotated.signature');api.read_node('k3s-wk-gpu2');self.assertEqual(rows[-1][1]['Authorization'],'Bearer test.rotated.signature')
                status[0]=302
                with self.assertRaises(ValueError):api.read_node('k3s-wk-gpu2')
                self.assertEqual(len(rows),3)
            finally:server.shutdown();thread.join(timeout=5);server.server_close()

if __name__=='__main__':unittest.main(verbosity=2)
