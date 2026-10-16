"""Genuine Source construction remains behind the actual writer/exclusion gate."""
import asyncio,copy,hashlib,importlib.util,json,os
from pathlib import Path
import sys,tempfile
from types import SimpleNamespace
from unittest.mock import patch
import pytest
HERE=Path(__file__).parent;sys.path[:0]=[str(HERE),str(HERE.parent)]
import test_source_maintenance as maintenance
import test_source_handover as forward
import test_source_qualification_handover as prior
import gateway_registration_reader as reader
from cps_compute.policy import Policy


def helper():
 p=HERE/'source_context.py';assert p.exists(),'Genuine guarded Source context factory required'
 s=importlib.util.spec_from_file_location('source_context',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


async def fixture(directory,operation='forward'):
 f=await prior.Fixture().setup(directory,fresh_profile=5)
 originals,current,operator,review=maintenance.observations()
 raw,pin=forward.contract(f)
 policy=f.policy
 if operation=='restore':
  catalog=copy.deepcopy(policy.catalog);catalog['version']='restore-fixture';policy=Policy(catalog)
 gateway={'pod_uid':maintenance.uid(6),'policy_hash':policy.hash,'contract_sha256':pin};review['gateway']=gateway
 spec={'containers':[{'name':'gateway','image':'reviewed'}]}
 gw=dict(apiVersion='v1',kind='Pod',metadata=dict(namespace='cps-compute',name='compute-gateway-test',uid=gateway['pod_uid']),spec=spec,
  status={'containerStatuses':[dict(name='gateway',imageID='reviewed-id',ready=True,state={'running':{}})]})
 class Api:
  def read_namespaced_deployment(self,name,namespace,**kwargs):return copy.deepcopy(current[name.split('-')[0]])
  def list_namespaced_pod(self,namespace,**kwargs):return {'apiVersion':'v1','kind':'PodList','metadata':{},'items':[copy.deepcopy(operator)]}
  def read_namespaced_pod(self,name,namespace,**kwargs):return copy.deepcopy(gw)
 api=Api()
 meta=dict(namespace='cps-compute',pod=gw['metadata']['name'],pod_uid=gateway['pod_uid'],pod_spec_sha256=maintenance.helper().digest(spec),container='gateway',image_id='reviewed-id',python_path='/usr/local/bin/python',request={})
 r=reader.GatewayReader(meta,core=api,execute=lambda **kw:json.dumps(f.old),original=(HERE.parent/'source_qualification_reader.py').read_bytes(),contract_raw=raw,contract_sha256=pin)
 from e2x_course_hub.cps.bootstrap import ensure_initial_config
 server=directory/'server.yml';ensure_initial_config(server)
 cfg=directory/'source.py';cfg.write_text('\n'.join(['c=get_config()',"c.CourseServiceApp.console_owner='cps'",'c.CourseServiceApp.database_path='+repr(str(directory/'console.sqlite')),
  'c.CourseServiceApp.server_config_file='+repr(str(server)),"c.CourseServiceApp.api_url='https://hub.invalid/api'","c.CourseServiceApp.compute_policy_url='https://fixture.invalid'","c.CourseServiceApp.compute_policy_token='fixture-token'" ]));cfg.chmod(0o600)
 console=dict(config_path=str(cfg),config_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),database_path=str(directory/'console.sqlite'),server_config_path=str(server),hub_api_url='https://hub.invalid/api',compute_policy_url='https://fixture.invalid')
 kw=dict(workspace=f.workspace,operation=operation,contract_raw=raw,contract_sha256=pin,policy=policy,qualification=f.groups,
  source_closure_raw=(HERE.parent/'source531-qualification-closure.json').read_bytes(),console=console,core=api,apps=api,
  originals=originals,operator_ref={'name':operator['metadata']['name'],'uid':operator['metadata']['uid'],'spec_sha256':maintenance.helper().digest(operator['spec'])},review=review,gateway=gateway,gateway_reader=r)
 return f,current,operator,cfg,kw


def source_user_stat(fd):
 info=REAL_FSTAT(fd)
 return SimpleNamespace(**{k:getattr(info,k) for k in dir(info) if k.startswith('st_') and k!='st_uid'},st_uid=10001)
REAL_FSTAT=os.fstat


@pytest.mark.parametrize('operation',['forward','restore'])
def test_constructs_actual_application_services_and_revalidates_callbacks(operation):
 async def run():
  with tempfile.TemporaryDirectory() as d:
   f,current,operator,cfg,kw=await fixture(Path(d),operation);m=helper()
   try:
    with patch.dict(os.environ,{'JUPYTERHUB_API_TOKEN':'fixture-hub-token'}),patch('os.fstat',source_user_stat),patch('cps_compute.runtime.create_runtime',side_effect=AssertionError('workflow bootstrap')):
     context=await m.build_context(**kw)
    assert type(context['service']) is type(f.service) and context['policy'].hash==kw['policy'].hash
    assert await context['read_registration']('cps',f.workspace)==f.old
    current['cps']['spec']['replicas']=1
    with pytest.raises(ValueError):await context['verify_external_freeze']()
    with pytest.raises(ValueError):await context['read_registration']('cps',f.workspace)
   finally:
    for app in m.APPS:app.tornado_settings['course_provider'].db.close()
    await f.close()
 asyncio.run(run())


@pytest.mark.parametrize('fault',['active-writer','foreign-workspace','policy-binding','closure','moodle','database-path','endpoint','operation','reader-code'])
def test_unsafe_context_never_initializes_any_provider(fault):
 async def run():
  with tempfile.TemporaryDirectory() as d:
   f,current,operator,cfg,kw=await fixture(Path(d));m=helper()
   try:
    if fault=='active-writer':current['cps']['spec']['replicas']=1
    elif fault=='foreign-workspace':kw['workspace']='unreviewed'
    elif fault=='policy-binding':kw['gateway']['policy_hash']='sha256:'+'0'*64
    elif fault=='endpoint':kw['console']['compute_policy_url']='https://wrong.invalid'
    elif fault=='operation':kw['operation']='restore'
    elif fault=='reader-code':kw['gateway_reader'].source+='\n# unreviewed'
    elif fault=='closure':kw['source_closure_raw']+=b'\n'
    elif fault=='database-path':kw['console']['database_path']=str(Path(d)/'wrong.sqlite')
    else:
     cfg.write_text(cfg.read_text()+"\nc.CourseServiceApp.course_providers={'local':{'enabled':True},'moodle':{'enabled':True}}\n");kw['console']['config_sha256']=hashlib.sha256(cfg.read_bytes()).hexdigest()
    with patch('os.fstat',source_user_stat),patch('e2x_course_hub.cps.providers.configure_provider',side_effect=AssertionError('provider initialized')):
     with pytest.raises(ValueError):await m.build_context(**kw)
   finally:await f.close()
 asyncio.run(run())
