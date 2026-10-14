import ast
import importlib.util
import json
import os
from pathlib import Path
import pytest

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('node_epoch_patch',HERE/'node_epoch_patch.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PRIVATE=Path(os.environ.get('CPS_KAI_ACTUAL507_SOURCE_BUNDLE','/home/bjoern/.local/state/cps-full-project-20261013/kai-v1-live-qualification-preparation-20261014/original-node-source-bundle.json'))
CORE=Path(os.environ.get('CPS_KAI_OPERATOR_EPOCH_SOURCE','/home/bjoern/git/cps-compute-worktrees/native-kai-operator-node-epoch-20261014/src/cps_compute/native_scheduler_node_epoch.py'))


def test_exact_actual507_patch_keeps_legacy_consumer_and_adds_only_explicit_epoch():
    original=json.loads(PRIVATE.read_text())['data'];out=m.render(original,CORE.read_text())
    assert set(out)==set(original)|{'native_operator_epoch.py'}
    assert all(out[name]==value for name,value in original.items() if name!='node_agent.py')
    assert out['native_approval_revision.py']==original['native_approval_revision.py']
    assert out['native_approval_process.py']==original['native_approval_process.py']
    assert out['native_gpu_controller.py']==original['native_gpu_controller.py']
    assert out['node_backend.py']==original['node_backend.py']
    tree=ast.parse(out['node_agent.py']);run=next(f for f in tree.body if isinstance(f,ast.FunctionDef) and f.name=='run')
    assert run.args.kwonlyargs[-1].arg=='operator_epoch'
    assert run.args.kw_defaults[-1].value is None
    assert '--operator-epoch-config' in out['node_agent.py']
    assert 'Operator epoch and dynamic v2 consumer cannot overlap' in out['node_agent.py']
    assert 'operator_epoch(config)' in out['node_agent.py']
    for name,source in out.items():
        if name.endswith('.py'):ast.parse(source)


def test_changed_or_unknown_original_code_cannot_be_patched():
    original=json.loads(PRIVATE.read_text())['data'];original['node_agent.py']+='\n#changed'
    with pytest.raises(ValueError):m.render(original,CORE.read_text())


def installed_module(monkeypatch):
    import sys, types
    original=json.loads(PRIVATE.read_text())['data'];out=m.render(original,CORE.read_text())
    for name in ['native_approval_process','native_approval_revision']:
        module=types.ModuleType(name);monkeypatch.setitem(sys.modules,name,module)
        exec(compile(original[name+'.py'],name+'.py','exec'),module.__dict__)
    module=types.ModuleType('installed_operator_epoch')
    exec(compile(out['native_operator_epoch.py'],'native_operator_epoch.py','exec'),module.__dict__)
    return module


@pytest.fixture
def actual_tls_api(tmp_path):
    import ssl, subprocess, threading, urllib.request
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from types import SimpleNamespace
    cert,key=tmp_path/'cert.pem',tmp_path/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),
        '-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1'],check=True,capture_output=True)
    volume=tmp_path/'sa';volume.mkdir(mode=0o700)
    token=volume/'token';token.write_text('test.first.signature');token.chmod(0o600)
    seen=[];reply={'status':200,'body':b'{"apiVersion":"v1","kind":"ConfigMap"}'}
    class Handler(BaseHTTPRequestHandler):
        def operation(self):
            raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
            seen.append((self.command,self.path,dict(self.headers),raw))
            self.send_response(reply['status'])
            if reply['status']==302:self.send_header('Location','https://127.0.0.1:1/foreign')
            self.end_headers();self.wfile.write(reply['body'])
        do_GET=operation;do_PATCH=operation
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    context=ssl.create_default_context(cafile=str(cert))
    kube=SimpleNamespace(base='https://127.0.0.1:'+str(server.server_port),
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context)))
    try:yield SimpleNamespace(kube=kube,volume=volume,token=token,seen=seen,reply=reply)
    finally:server.shutdown();thread.join(timeout=5);server.server_close()


def test_actual_tls_json_patch_uses_fresh_token_and_exact_uid_rv_data(monkeypatch,actual_tls_api):
    api=actual_tls_api;module=installed_module(monkeypatch)
    raw=module.OperatorEpochRawAPI(api.kube,api.volume)
    patch=[{'op':'test','path':'/metadata/uid','value':'55555555-5555-4555-8555-555555555555'},
        {'op':'test','path':'/metadata/resourceVersion','value':'2'},
        {'op':'test','path':'/data','value':{'epoch.json':'{}'}},
        {'op':'replace','path':'/data','value':{'epoch.json':'{"mode":"operator-qualification"}'}}]
    raw.patch_namespaced_config_map('cps-native-kai-epoch-node','cps-native-system',patch)
    method,path,headers,body=api.seen[-1]
    assert method=='PATCH' and path=='/api/v1/namespaces/cps-native-system/configmaps/cps-native-kai-epoch-node'
    assert headers['Content-Type']=='application/json-patch+json'
    assert headers['Authorization']=='Bearer test.first.signature' and json.loads(body)==patch
    api.token.write_text('test.rotated.signature')
    raw.read_namespaced_service_account('cps-native-node-agent','cps-native-system')
    assert api.seen[-1][2]['Authorization']=='Bearer test.rotated.signature'


@pytest.mark.parametrize('damage',['redirect','huge','duplicate','404patch','conflict'])
def test_actual_tls_unknown_patch_outcome_never_returns_success(monkeypatch,actual_tls_api,damage):
    api=actual_tls_api;raw=installed_module(monkeypatch).OperatorEpochRawAPI(api.kube,api.volume)
    if damage=='redirect':api.reply['status']=302
    elif damage=='huge':api.reply['body']=b' '*(1048577)
    elif damage=='duplicate':api.reply['body']=b'{"a":1,"a":2}'
    elif damage=='404patch':api.reply['status']=404
    else:api.reply['status']=409
    with pytest.raises(ValueError):raw.patch_namespaced_config_map('cps-native-kai-epoch-node','cps-native-system',[])
    assert len(api.seen)==1


def test_actual_tls_get_absence_and_token_volume_escape(monkeypatch,actual_tls_api,tmp_path):
    api=actual_tls_api;raw=installed_module(monkeypatch).OperatorEpochRawAPI(api.kube,api.volume)
    api.reply['status']=404
    assert raw.read_namespaced_config_map('cps-native-kai-epoch-node','cps-native-system') is None
    other=tmp_path/'foreign';other.write_text('foreign.token.signature');other.chmod(0o600)
    api.token.unlink();api.token.symlink_to(other)
    with pytest.raises(ValueError):raw.read_node('k3s-wk-gpu2')
    assert len(api.seen)==1


def patched_agent(monkeypatch,tmp_path):
    import sys,types
    data=m.render(json.loads(PRIVATE.read_text())['data'],CORE.read_text())
    module=types.ModuleType('patched_actual507');module.__file__=str(tmp_path/'node_agent.py')
    monkeypatch.setitem(sys.modules,module.__name__,module)
    exec(compile(data['node_agent.py'],module.__file__,'exec'),module.__dict__)
    return module


def test_real507_entrypoint_with_optin_path_stays_inert_before_execute(monkeypatch,tmp_path,capsys):
    agent=patched_agent(monkeypatch,tmp_path)
    monkeypatch.setattr(agent,'read_config',lambda p:pytest.fail('Default-off must not open configuration'))
    agent.main(['--operator-epoch-config','/absent/epoch.json','--config','/absent/node.json'])
    assert json.loads(capsys.readouterr().out)['api_calls'] is False


def test_real507_entrypoint_refuses_operator_and_v2_consumer_overlap_before_any_api(monkeypatch,tmp_path):
    agent=patched_agent(monkeypatch,tmp_path)
    monkeypatch.setattr(agent.os,'geteuid',lambda:0)
    monkeypatch.setattr(agent,'read_config',lambda p:{'enabled':True})
    monkeypatch.setattr(agent,'load_bundle',lambda p:pytest.fail('Must reject before node/GPU initialization'))
    with pytest.raises(ValueError,match='cannot overlap'):
        agent.main(['--execute','--config','/x','--operator-epoch-config','/y','--approval-reference','/r',
            '--approval-template','/t','--approval-process','/p','--approval-acknowledgment','/a'])


def test_installed_factory_disabled_has_no_api_env_or_gpu_observation(monkeypatch):
    from types import SimpleNamespace
    module=installed_module(monkeypatch)
    backend=SimpleNamespace(private_read=lambda path,uid:{'enabled':False})
    agent=SimpleNamespace(load_source=lambda *args:backend,snapshot_sources=lambda:{'node_backend.py':'actual'},SOURCE_PINS={'node_backend.py':'pin'})
    monkeypatch.setattr(module,'OperatorEpochRawAPI',lambda *args:pytest.fail('Disabled factory must not initialize transport'))
    assert module.build_installed(agent,None,None,None,None,None,None,None,Path('/unused'),Path('/unused')) is None


def test_installed_factory_uses_real507_config_and_attests_before_cap_work(monkeypatch,tmp_path):
    import sys
    from types import SimpleNamespace
    # Reuse the reviewed SDK process/config fixtures without inventing a new wire object.
    sys.path.insert(0,str(CORE.parents[2]/'tests'))
    try:
        from test_native_scheduler_node_epoch import fixture
        s=fixture()
    finally:sys.path.remove(str(CORE.parents[2]/'tests'))
    module=installed_module(monkeypatch);agent=patched_agent(monkeypatch,tmp_path)
    settings={'enabled':True,'version':1,'target':s['target'],'node_configuration':s['config_ref'],
        'process':s['declaration'],'ttlSeconds':30}
    backend=SimpleNamespace(private_read=lambda path,uid:settings)
    monkeypatch.setattr(agent,'load_source',lambda *args:backend)
    monkeypatch.setattr(agent,'snapshot_sources',lambda:{'node_backend.py':'actual'})
    monkeypatch.setattr(agent,'abort_current_epoch',lambda *args:SimpleNamespace(**s['epoch']))
    class Raw:
        def __init__(self,*args):pass
        def __getattr__(self,key):return getattr(s['core'],key,None) or getattr(s['apps'],key)
    monkeypatch.setattr(module,'OperatorEpochRawAPI',Raw)
    for key,value in [('NAME',s['process']['name']),('UID',s['process']['uid']),('NAMESPACE',s['process']['namespace'])]:
        monkeypatch.setenv('CPS_NATIVE_OPERATOR_POD_'+key,value)
    s['ack']['data']['epoch.json']='{}'
    callback=module.build_installed(agent,None,s['config'],None,None,None,None,None,Path('/unused'),Path('/unused'))
    assert callable(callback) and sum(x[0]=='patch' for x in s['calls'])==1
    callback(s['config'])
    assert sum(x[0]=='patch' for x in s['calls'])==1  # bounded TTL/3, no background thread
    assert json.loads(s['ack']['data']['epoch.json'])['service_account_uid']==s['declaration']['service_account_uid']
