"""Root-pinned reader scope preserves the real configured readonly store path."""
import asyncio,copy,hashlib,importlib.util,json,os
from pathlib import Path
import sys,tempfile
from types import ModuleType
from unittest.mock import patch
import pytest
HERE=Path(__file__).parent;sys.path[:0]=[str(HERE),str(HERE.parent)]
from test_node_successor import fixture as contract_fixture
from cps_compute.internal import ControlStore,ServiceIdentity
from cps_compute.reservations import Reservations
import cps_compute.internal as internal
import cps_compute.runtime as runtime


def helper():
 p=HERE/'gateway_registration_reader.py';assert p.exists(),'Pinned current-pair Gateway reader required'
 s=importlib.util.spec_from_file_location('gateway_registration_reader',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def values():
 *_,contract=contract_fixture()
 raw=json.dumps(contract,sort_keys=True).encode();return (HERE.parent/'source_qualification_reader.py').read_bytes(),raw,hashlib.sha256(raw).hexdigest()


def compiled():
 base,raw,pin=values();source=helper().reader_source(base,contract_raw=raw,contract_sha256=pin)
 m=ModuleType('actual_scoped_reader');exec(compile(source,'<scoped-readonly-reader>','exec'),m.__dict__)
 return m,json.loads(raw),source


def test_reuses_all_frozen_readonly_logic_changing_only_scope_guard():
 base,raw,pin=values();source=helper().reader_source(base,contract_raw=raw,contract_sha256=pin)
 assert source.replace(helper().scope_guard(json.loads(raw),pin),helper().ORIGINAL_GUARD)==base.decode()
 assert 'mode=ro' in source and 'projected_config_bytes' in source


@pytest.mark.parametrize('index',[0,1])
def test_actual_store_reads_both_approved_registrations_without_writing(index):
 m,contract,_=compiled();scope=sorted(contract['workspaces'])[index];source,workspace=scope.split(':',1)
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);db=root/'control.sqlite';store=ControlStore(db);reservations=Reservations(root/'reservations.sqlite')
  expected=dict(workspace=workspace,owner='neutral',server='rtc',members=['person'],principal='workspace:'+scope,profiles=['interactive-cpu'],policy_hash='old',storage={'path':'/retained','state':'active'})
  store.put_workspace(expected,ServiceIdentity(source,source),reservations)
  raw=json.dumps({'state_directory':d}).encode();info=db.stat();before=hashlib.sha256(db.read_bytes()).hexdigest()
  request=dict(source=source,workspace=workspace,config_path='/config/runtime.json',config_sha256=hashlib.sha256(raw).hexdigest(),
   internal_sha256=hashlib.sha256(Path(internal.__file__).read_bytes()).hexdigest(),runtime_sha256=hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest(),
   database_path=str(db),database_device=info.st_dev,database_inode=info.st_ino,database_uid=info.st_uid)
  with patch.dict(os.environ,{'CPS_COMPUTE_CONFIG':'/config/runtime.json'}),patch.object(m,'projected_config_bytes',return_value=raw):assert m.read_registration(request)==expected
  assert hashlib.sha256(db.read_bytes()).hexdigest()==before


@pytest.mark.parametrize('scope',['cps:native-group-b','cit:native-group-a','cps:unreviewed','cit:operator-qualification-531-test-five'])
def test_foreign_or_legacy_scope_is_rejected_before_any_runtime_read(scope):
 m,_,_=compiled();source,workspace=scope.split(':',1)
 request={k:'' for k in ('config_path','config_sha256','internal_sha256','runtime_sha256','database_path','database_device','database_inode','database_uid')};request.update(source=source,workspace=workspace)
 with pytest.raises(ValueError,match='Exact approved source workspace'):m.read_registration(request)


@pytest.mark.parametrize('fault',['source','contract'])
def test_changed_base_or_unreviewed_contract_is_not_executed(fault):
 base,raw,pin=values()
 if fault=='source':base+=b'\n'
 else:pin='0'*64
 with pytest.raises(ValueError):helper().reader_source(base,contract_raw=raw,contract_sha256=pin)


def reader_fixture():
 base,raw,pin=values();scope=sorted(json.loads(raw)['workspaces'])[0];source,workspace=scope.split(':',1)
 pod=dict(apiVersion='v1',kind='Pod',metadata=dict(namespace='cps-compute',name='compute-gateway-test',uid='00000000-0000-0000-0000-000000000006'),
  spec={'containers':[{'name':'gateway','image':'reviewed'}]},status={'containerStatuses':[dict(name='gateway',imageID='reviewed-id',ready=True,state={'running':{}})]})
 meta=dict(namespace='cps-compute',pod='compute-gateway-test',pod_uid=pod['metadata']['uid'],pod_spec_sha256=hashlib.sha256(json.dumps(pod['spec'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
  container='gateway',image_id='reviewed-id',python_path='/usr/local/bin/python',request={})
 class Core:
  calls=0
  def read_namespaced_pod(self,*args,**kwargs):self.calls+=1;return copy.deepcopy(pod)
 return base,raw,pin,source,workspace,pod,meta,Core()


def test_transport_checks_real_process_before_and_after_and_returns_exact_record():
 base,raw,pin,source,workspace,pod,meta,core=reader_fixture();calls=[]
 expected=dict(workspace=workspace,principal='workspace:'+source+':'+workspace,storage={'state':'active','evidence':{'retained':True}})
 def transport(**kwargs):calls.append(kwargs);return json.dumps(expected)
 tool=helper();assert hasattr(tool,'GatewayReader'),'Actual SDK reader transport required'
 reader=tool.GatewayReader(meta,core=core,execute=transport,original=base,contract_raw=raw,contract_sha256=pin)
 assert reader.get(source,workspace)==expected and core.calls==2 and len(calls)==1
 assert calls[0]['namespace']=='cps-compute' and calls[0]['pod']==meta['pod']
 assert 'mode=ro' in calls[0]['payload'] and workspace in calls[0]['payload']


@pytest.mark.parametrize('fault',['foreign','uid','spec','image','post-read-uid','invalid-json','wrong-result'])
def test_changed_process_or_foreign_result_never_becomes_registration(fault):
 base,raw,pin,source,workspace,pod,meta,core=reader_fixture()
 def transport(**kwargs):
  if fault=='post-read-uid':pod['metadata']['uid']='changed'
  if fault=='invalid-json':return 'not-json'
  return json.dumps(dict(workspace='foreign' if fault=='wrong-result' else workspace,principal='workspace:'+source+':'+workspace))
 if fault=='uid':meta['pod_uid']='wrong'
 elif fault=='spec':pod['spec']['extra']='changed'
 elif fault=='image':pod['status']['containerStatuses'][0]['imageID']='wrong'
 elif fault=='foreign':workspace='unreviewed'
 tool=helper();assert hasattr(tool,'GatewayReader'),'Actual SDK reader transport required'
 reader=tool.GatewayReader(meta,core=core,execute=transport,original=base,contract_raw=raw,contract_sha256=pin)
 with pytest.raises(ValueError):reader.get(source,workspace)


@pytest.mark.parametrize('fault',[None,'stdout-bound','stderr','exit','timeout'])
def test_sdk_transport_sends_length_framed_stdin_and_closes_on_every_path(fault):
 tool=helper();assert hasattr(tool,'sdk_exec'),'Bounded actual SDK exec transport required'
 class WS:
  opened=True;closed=False;written=None
  returncode=1 if fault=='exit' else 0
  def is_open(self):return self.opened
  def write_stdin(self,value):self.written=value
  def update(self,**kwargs):self.opened=False
  def read_stdout(self):return 'x'*1048577 if fault=='stdout-bound' else '{"ok":true}'
  def read_stderr(self):return 'private failure' if fault=='stderr' else ''
  def close(self):self.closed=True
 class Core:
  def connect_get_namespaced_pod_exec(self):pass
 connection=WS();calls=[]
 def stream(*args,**kwargs):calls.append((args,kwargs));return connection
 def run():return tool.sdk_exec(namespace='cps-compute',pod='gateway',container='gateway',python_path='/usr/local/bin/python',payload='π=1\n',core=Core(),stream_factory=stream)
 if fault=='timeout':
  with patch('time.monotonic',side_effect=[0,31]),pytest.raises(TimeoutError):run()
 elif fault:
  with pytest.raises(ValueError):run()
 else:assert run()=='{"ok":true}'
 assert connection.closed and connection.written=='π=1\n'
 argv=calls[0][1]['command'];assert argv[-1]==str(len('π=1\n'.encode())) and 'π=1' not in ' '.join(argv)
 assert calls[0][1]['tty'] is False
