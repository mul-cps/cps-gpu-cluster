import hashlib,importlib.util,json
from pathlib import Path
import pytest
HERE=Path(__file__).parent

def module():
 s=importlib.util.spec_from_file_location('closure',HERE/'fresh_import_closure.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.PREFLIGHT_SHA=hashlib.sha256(preflight()).hexdigest();return m

def fixture():
 cohort='3b217fe8-5750-4ead-954a-09286afd7d3f'
 return {'version':1,'cohort_uid':cohort,'namespace_uid':'1f7d941a-872d-4453-a1ba-fd489d8aff14','pods':{k:{'namespace':'cps-native-qa147-20261022','name':'native-qa147-'+k+'-'+cohort[:8],'uid':('1' if k=='a' else '2')*8+'-1111-4111-8111-111111111111','cap_mib':cap,'spec_sha256':'a'*64}for k,cap in [('a',5120),('b',10240)]},'observer_argv':['ssh','root','observe.py','--execute','--cohort-uid',cohort],'physical_argv':['ssh','root','physical_samples.py','--execute']}

def preflight():
 return (HERE.parent/'native-fresh-domain/fresh_preflight.py').read_bytes().replace(b"and row['cap_mib']==5120",b"and row['cap_mib']==(5120 if key=='a' else 10240)")

def test_preparation_keeps_engines_and_thresholds_but_binds_fresh_targets():
 m=module();v=fixture();out=m.build(v,'c'*64,preflight(),hashlib.sha256(preflight()).hexdigest())
 for name,raw in out.items():
  if name.endswith('.py'):compile(raw,name,'exec')
 for mode in ('managed','vmm-owner-exit','vmm-cross-parent'):
  assert any(k.startswith(mode+'/') for k in out)
 assert b'GENERATION=\'4ebffc96-e25e-4583-a3b8-0d853fd90efd\'' in out['managed/managed_probe.py']
 owner=out['vmm-owner-exit/run_owner_exit.py'].decode()
 assert '20_000_000_000' in owner and "cohort=None" in owner
 bridge=out['vmm-cross-parent/vmm_bridge.py'].decode()
 assert 'CAPS[identity[\'pod_uid\']]' in bridge and v['pods']['b']['uid'] in bridge
 assert b'kernel_status' in out['vmm-cross-parent/kernel_witness_validator.py']
 assert 'c'*64 in out['run_group_acceptance.py'].decode()

@pytest.mark.parametrize('fault',['cap','uid','cohort','extra','preflight'])
def test_wrong_manifest_or_source_denies(fault):
 m=module();v=fixture();pref=preflight();pin=hashlib.sha256(pref).hexdigest()
 if fault=='cap':v['pods']['b']['cap_mib']=20480
 elif fault=='uid':v['pods']['a']['uid']=v['pods']['b']['uid']
 elif fault=='cohort':v['cohort_uid']='33333333-1111-4111-8111-111111111111'
 elif fault=='extra':v['untrusted']=True
 else:pin='0'*64
 with pytest.raises(ValueError):m.build(v,'c'*64,pref,pin)

def test_default_inert_without_reads(monkeypatch,capsys):
 m=module();monkeypatch.setattr(Path,'read_bytes',lambda *_:pytest.fail('inert read'));m.main([])
 assert '"inert": true' in capsys.readouterr().out


def test_original_assessment_threshold_asts_are_unchanged():
 import ast
 m=module();out=m.build(fixture(),'c'*64,preflight(),hashlib.sha256(preflight()).hexdigest())
 for old,new,fn in [('managed/run_managed.py','managed/run_managed.py','assess'),('vmm-owner-exit/run_owner_exit.py','vmm-owner-exit/run_owner_exit.py','assess'),('vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py','vmm-cross-parent/run_vmm_cross_parent.py','assess')]:
  get=lambda raw:next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)and n.name==fn)
  assert ast.dump(get((m.OLD/old).read_bytes()))==ast.dump(get(out[new]))


def test_fresh_facade_repeats_real_brackets_and_denies_changed_policy(tmp_path,monkeypatch):
 import copy
 m=module();v=fixture();raw=json.dumps(v).encode();pin=hashlib.sha256(raw).hexdigest();out=m.build(v,pin,preflight(),hashlib.sha256(preflight()).hexdigest())
 for name in ('run_group_acceptance.py','fresh_preflight.py','manifest.json'):(tmp_path/name).write_bytes(raw if name=='manifest.json' else out[name])
 spec=importlib.util.spec_from_file_location('fresh_facade',tmp_path/'run_group_acceptance.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
 calls=[];rows=[{'inode':i+1,'soft':cap*1048576,'hard':cap*1048576,'used':0}for i,cap in enumerate((5120,10240))]
 snapshot={'pods':[{'uid':v['pods'][k]['uid'],'status':{'imageID':'image','containerID':'container'}}for k in ('a','b')],'host':{'processes':[{'pid':11},{'pid':12}],'targets':[{'pod_uid':v['pods'][k]['uid'],'identity':{'cgroup_inode':i+1},'intent':{'policy_hash':m.POLICY,'cap_mib':v['pods'][k]['cap_mib']}}for i,k in enumerate(('a','b'))],'inventory':{'entries':rows}}}
 def fresh(*args):calls.append(True);return copy.deepcopy(snapshot)
 monkeypatch.setattr(h.current,'preflight',fresh)
 config={'driver_generation':m.GEN,'targets':[{'namespace':v['pods'][k]['namespace'],'name':v['pods'][k]['name'],'pod_uid':v['pods'][k]['uid']}for k in ('a','b')]}
 assert h.preflight(config)['host']['targets'][1]['inventory_row']['hard']==10240*1048576
 h.preflight(config);assert len(calls)==2
 snapshot['host']['targets'][1]['intent']['policy_hash']='foreign'
 with pytest.raises(ValueError,match='Source332'):h.preflight(config)
 assert len(calls)==3


def test_generated_host_capmap_rejects_foreign_uid_before_filesystem(monkeypatch):
 m=module();out=m.build(fixture(),'c'*64,preflight(),hashlib.sha256(preflight()).hexdigest())
 bridge=m.load('bridge',out['vmm-cross-parent/vmm_bridge.py'])
 monkeypatch.setattr(Path,'stat',lambda *a,**k:pytest.fail('foreign filesystem probe'))
 request={'trial_id':'33333333-1111-4111-8111-111111111111','namespace_pid':123,'identity':{'pod_uid':'foreign'},'role':'importer','expect':'deny','source_sha256':'a'*64}
 with pytest.raises(ValueError,match='enrolled'):bridge.observe(request)


def test_real_offline_cli_preserves_raw_manifest_and_exclusive_output(tmp_path):
 m=module();v=fixture();raw=json.dumps(v,indent=2).encode();manifest=tmp_path/'actual.json';manifest.write_bytes(raw);pref=tmp_path/'fresh.py';pref.write_bytes(preflight());out=tmp_path/'new'
 argv=['--prepare','--manifest',str(manifest),'--manifest-sha256',hashlib.sha256(raw).hexdigest(),'--preflight',str(pref),'--preflight-sha256',hashlib.sha256(preflight()).hexdigest(),'--output',str(out)]
 m.main(argv);assert (out/'manifest.json').read_bytes()==raw
 assert (out/'managed/run_managed.py').stat().st_mode&0o777==0o600
 with pytest.raises(FileExistsError):m.main(argv)


def test_existing_owner_exit_empty_baseline_branch_rejects_extra_gpu_clients():
 m=module();out=m.build(fixture(),'c'*64,preflight(),hashlib.sha256(preflight()).hexdigest());host=m.load('host_observer',out['vmm-owner-exit/host_owner_observer.py'])
 host.validate_client_cohort(set(),set(),None)
 host.validate_client_cohort({11,12},{11,12},None)
 with pytest.raises(ValueError):host.validate_client_cohort({11,12,99},{11,12},None)
