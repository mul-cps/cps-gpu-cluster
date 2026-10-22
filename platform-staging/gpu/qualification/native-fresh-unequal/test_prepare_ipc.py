import hashlib,importlib.util,json
from pathlib import Path
import pytest
HERE=Path(__file__).parent

def module():
 s=importlib.util.spec_from_file_location('prepare_ipc',HERE/'prepare_ipc.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def manifest():
 cohort='a9fc091b-f388-4f21-8771-b6ae7b4734dc'
 return dict(version=1,cohort_uid=cohort,namespace_uid='1f7d941a-872d-4453-a1ba-fd489d8aff14',pods={k:dict(namespace='cps-native-qa147-20261022',name='native-qa147-'+k+'-'+cohort[:8],uid=('1' if k=='a' else '2')*8+'-1111-4111-8111-111111111111',cap_mib=cap,spec_sha256='a'*64) for k,cap in [('a',5120),('b',10240)]},observer_argv=['ssh','host','observe.py','--execute','--cohort-uid',cohort],physical_argv=['ssh','host','physical_samples.py','--execute'])

def test_fixed_endpoints_host_uid_root_and_source_pins():
 m=module();v=manifest();out=m.build_sources(v,'c'*64)
 assert out['ipc_endpoint.py']==(HERE.parent/'native-fresh-ipc/ipc_endpoint.py').read_bytes()
 assert b'CAP = 10737418240' in out['ipc_endpoint_b.py']
 host=out['ipc_host_pid.py'].decode();assert repr(v['pods']['b']['uid']) in host and 'actual[\'used\'] <= 10737418240' in host
 assert b'6ba3353d-bf13-4cad-9c35-3119dd279a67' not in out['kernel_witness_collector.py']
 runner=out['run_cross_pod.py'].decode();assert "choices=('a-to-b',)" in runner and "raw['ipc_endpoint_b.py'],'cross-pod-importer'" in runner
 assert 'c'*64 in runner and m.POLICY in runner
 assert out['ipc_engine.py']==(HERE.parent/'native-fresh-ipc/ipc_engine.py').read_bytes()
 assert out['kernel_witness_validator.py']==(HERE.parent/'native-fresh-ipc/kernel_witness_validator.py').read_bytes()
 for name,raw in out.items():compile(raw,name,'exec')

@pytest.mark.parametrize('fault',['cap','cohort','extra','same-uid','pin'])
def test_manifest_denials(fault):
 m=module();v=manifest();pin='c'*64
 if fault=='cap':v['pods']['b']['cap_mib']=20480
 elif fault=='cohort':v['cohort_uid']='33333333-1111-4111-8111-111111111111'
 elif fault=='extra':v['extra']=True
 elif fault=='same-uid':v['pods']['b']['uid']=v['pods']['a']['uid']
 else:pin='bad'
 with pytest.raises(ValueError):m.build_sources(v,pin)

def test_default_inert_without_source_reads(capsys,monkeypatch):
 m=module();monkeypatch.setattr(Path,'read_bytes',lambda *_:pytest.fail('inert reads'))
 m.main([]);assert '"state":"inert"' in capsys.readouterr().out


def test_foreign_importer_uid_denied_before_any_host_probe(monkeypatch):
 m=module();out=m.build_sources(manifest(),'c'*64);host=m.load('ipc_host_pid.py',out['ipc_host_pid.py'])
 monkeypatch.setattr(Path,'read_bytes',lambda *_:pytest.fail('foreign host read'))
 request={'trial_id':'33333333-1111-4111-8111-111111111111','namespace_pid':123,'identity':{'pod_uid':'foreign'}}
 with pytest.raises(ValueError,match='importer UID'):host.observe(request)


def test_generated_runner_all_embedded_source_hashes_are_coherent():
 m=module();out=m.build_sources(manifest(),'c'*64);runner=m.load('run_cross_pod.py',out['run_cross_pod.py'])
 assert all(hashlib.sha256(out[n]).hexdigest()==pin for n,pin in runner.PINS.items())
 assert hashlib.sha256(out['ipc_endpoint_b.py']).hexdigest()==runner.ENDPOINT_B_SHA
 assert hashlib.sha256(out['fresh_preflight.py']).hexdigest()==runner.PREFLIGHT_SHA

@pytest.mark.parametrize('bad_index',[0,1])
def test_actual_runner_checks_both_source_policies_before_any_cuda_session(tmp_path,monkeypatch,bad_index):
 from types import SimpleNamespace
 m=module();v=manifest();out=m.build_sources(v,'c'*64);runner=m.load('run_cross_pod.py',out['run_cross_pod.py']);writes=[]
 policies=[m.POLICY,m.POLICY];policies[bad_index]='sha256:'+'f'*64
 current=SimpleNamespace(read_targets=lambda *_:v,unique=m.unique,preflight=lambda *_:{'host':{'targets':[{'intent':{'policy_hash':p}}for p in policies]}})
 engine=SimpleNamespace(Session=lambda *_:pytest.fail('CUDA dispatched before policy guard'))
 retained=SimpleNamespace(write=lambda *args:writes.append(args))
 def load(name,*args):return {'fresh_ipc_engine':engine,'fresh_qa_preflight':current,'fresh_import_proof':retained,'fresh_kernel_transport':SimpleNamespace()}[name]
 monkeypatch.setattr(runner,'load',load);monkeypatch.setattr(runner,'checked',lambda *_:b'{}')
 monkeypatch.setattr(runner,'transports',lambda *_:{})
 with pytest.raises(SystemExit) as error:
  runner.main(['--execute','--manifest','actual','--manifest-sha256','c'*64,'--transports','reviewed','--transports-sha256','d'*64,'--runner-sha256','e'*64,'--output',str(tmp_path/'new')])
 assert error.value.code==1 and writes[-1][1]['state']=='inconclusive'


def test_exclusive_preparation_actual_files_and_manifest_hash(tmp_path,capsys):
 m=module();v=manifest();raw=json.dumps(v).encode();p=tmp_path/'manifest';p.write_bytes(raw);p.chmod(0o600);pin=hashlib.sha256(raw).hexdigest();out=tmp_path/'new'
 argv=['--prepare','--manifest',str(p),'--manifest-sha256',pin,'--output',str(out)]
 m.main(argv);assert (out/'ipc_host_pid.py').stat().st_mode&0o777==0o600
 assert pin in (out/'run_cross_pod.py').read_text()
 with pytest.raises(FileExistsError):m.main(argv)
 with pytest.raises(ValueError):m.read_manifest(p,'f'*64)
