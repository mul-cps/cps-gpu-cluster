"""CPU-only synthetic qualification fixtures; these are not hardware receipts."""
import ast,copy,hashlib,importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_group_policy_compiler',ROOT/'scripts/compile_compute_policy.py')
compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
IMAGE='ghcr.io/mul-cps/cps-jupyter-notebook:qualification-native-group-980408a@sha256:9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0'
GATES={'cap-assignment','oom-peer','aggregate','memory-import','restart-cleanup','mps'}

class NativeGroupTests(unittest.TestCase):
 def fixture(self,root):
  catalog=json.loads((ROOT/'compute-policy/catalog.json').read_text());catalog['version']='0.1.1';catalog['approvedImages']=[IMAGE]
  profile=catalog['profiles']['interactive-shared-5'];profile['enabled']=True;profile['images']=[IMAGE];profile.pop('qualificationRequired')
  profile['gpu']={'mode':'shared','nominalMemoryGiB':5,'qualification':{'mechanism':'r615-native-cgroup-managed-deny','status':'qualified-group','policyVersion':catalog['version'],'evidence':['native-groups-v1']}}
  digest='sha256:'+hashlib.sha256(compiler.canonical(catalog)).hexdigest()
  proof={'version':1,'policy_hash':digest,'policy_version':catalog['version'],'node_pool':{'node':'k3s-wk-gpu2','node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41','gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56','max_workspaces':2},'core_sha256':'4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421','uvm_sha256':'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61','health_sha256':'52fdbdae3d5e2f66fd4653d94ef5a62f734e185fabec30450f4a1b70cfee7d67','gate_image':'ghcr.io/mul-cps/cps-compute@sha256:bc5b128f582641eae8395e1121d1fb248eddc39a56c9e863b7c564badd94b167','workload_image':IMAGE,'gates':{}}
  paths={}
  for gate in GATES:
   path=Path(root)/(gate+'.json');path.write_text(json.dumps({'gate':gate,'passed':True,'policy_hash':digest,'policy_version':catalog['version'],'synthetic_cpu_test_only':True}));path.chmod(0o600)
   proof['gates'][gate]={'passed':True,'evidence_sha256':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()};paths[gate]=path
  return catalog,proof,paths
 def compile(self,c,p,a):return compiler.compile_catalog(c,native_group_evidence=p,native_group_artifacts=a)
 def test_default_still_rejects_all_enabled_gpu_and_no_profile_mutation(self):
  c=json.loads((ROOT/'compute-policy/catalog.json').read_text())
  for name,profile in c['profiles'].items():
   if profile['gpu']['mode']=='none':continue
   changed=copy.deepcopy(c);changed['profiles'][name]['enabled']=True
   with self.subTest(profile=name),self.assertRaises(ValueError):compiler.compile_catalog(changed)
  with tempfile.TemporaryDirectory()as root:
   c,p,a=self.fixture(root);original=copy.deepcopy(c)
   with self.assertRaises(ValueError):compiler.compile_catalog(c)
   self.assertEqual(c,original)
 def test_only_exact_canonical_native_profile_with_six_actual_files_compiles(self):
  with tempfile.TemporaryDirectory()as root:
   c,p,a=self.fixture(root);original=copy.deepcopy(c);result=self.compile(c,p,a)
   self.assertEqual(result['policyHash'],p['policy_hash']);self.assertEqual(c,original)
   self.assertEqual(set(result['profiles']),set(original['profiles']))
   for key,value in original.items():self.assertEqual(result[key],value)
 def test_exact_profile_contract_negatives(self):
  for field,value in [('cpu','8'),('memory','32Gi'),('queue','batch'),('kind','batch'),('images',[]),('enabled',1),('enabled',False)]:
   with self.subTest(field=field),tempfile.TemporaryDirectory()as root:
    c,p,a=self.fixture(root);c['profiles']['interactive-shared-5'][field]=value
    with self.assertRaises(ValueError):self.compile(c,p,a)
  for fault in ['fraction','cap','cap-bool','mechanism','status','policy-version','evidence','extra-gpu','other-enabled','global-qualified']:
   with self.subTest(fault=fault),tempfile.TemporaryDirectory()as root:
    c,p,a=self.fixture(root);gpu=c['profiles']['interactive-shared-5']['gpu'];q=gpu['qualification']
    if fault=='fraction':gpu['fraction']='0.125'
    elif fault=='cap':gpu['nominalMemoryGiB']=10
    elif fault=='cap-bool':gpu['nominalMemoryGiB']=True
    elif fault=='extra-gpu':gpu['count']=1
    elif fault=='other-enabled':c['profiles']['interactive-shared-10']['enabled']=True
    elif fault=='global-qualified':c['gpuQualification']['qualified']=True
    else:q[{'mechanism':'mechanism','status':'status','policy-version':'policyVersion','evidence':'evidence'}[fault]]='forged'
    with self.assertRaises(ValueError):self.compile(c,p,a)
 def test_proof_binding_pins_closed_fields_and_all_gates(self):
  for fault in ['policy-hash','version','proof-version','pool','max-bool','core','uvm','health','image','mutable-gate','wrong-gate','missing-gate','extra-gate','not-passed','bool-string','zero','extra-proof','extra-entry']:
   with self.subTest(fault=fault),tempfile.TemporaryDirectory()as root:
    c,p,a=self.fixture(root)
    if fault=='policy-hash':p['policy_hash']='sha256:'+'b'*64
    elif fault=='version':p['policy_version']='0.1.2'
    elif fault=='proof-version':p['version']=True
    elif fault=='pool':p['node_pool']['gpu_uuid']='GPU-forged'
    elif fault=='max-bool':p['node_pool']['max_workspaces']=True
    elif fault in ('core','uvm','health'):p[fault+'_sha256']='b'*64
    elif fault=='image':p['workload_image']='forged@sha256:'+'b'*64
    elif fault=='mutable-gate':p['gate_image']='gw:latest'
    elif fault=='wrong-gate':p['gate_image']='ghcr.io/mul-cps/cps-compute@sha256:'+'a'*64
    elif fault=='missing-gate':p['gates'].pop('mps')
    elif fault=='extra-gate':p['gates']['forged']=p['gates']['mps']
    elif fault=='not-passed':p['gates']['mps']['passed']=False
    elif fault=='bool-string':p['gates']['mps']['passed']='true'
    elif fault=='zero':p['gates']['mps']['evidence_sha256']='sha256:'+'0'*64
    elif fault=='extra-proof':p['enabled']=True
    else:p['gates']['mps']['waiver']=True
    with self.assertRaises(ValueError):self.compile(c,p,a)
 def test_missing_tampered_replaced_and_wrong_target_gate_files(self):
  for fault in ['missing','tamper','symlink','public','wrong-policy','wrong-version','wrong-gate','not-passed','missing-map','extra-map']:
   with self.subTest(fault=fault),tempfile.TemporaryDirectory()as root:
    c,p,a=self.fixture(root);path=a['mps']
    if fault=='missing':path.unlink()
    elif fault=='tamper':path.write_text('changed')
    elif fault=='symlink':other=path.with_name('other');path.rename(other);path.symlink_to(other)
    elif fault=='public':path.chmod(0o644)
    elif fault=='missing-map':a.pop('mps')
    elif fault=='extra-map':a['other']=path
    else:
     report=json.loads(path.read_text());report[{'wrong-policy':'policy_hash','wrong-version':'policy_version','wrong-gate':'gate','not-passed':'passed'}[fault]]='forged';path.write_text(json.dumps(report));p['gates']['mps']['evidence_sha256']='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
    with self.assertRaises((ValueError,OSError)):self.compile(c,p,a)
 def test_no_proof_only_artifacts_and_no_artifacts_only_proof(self):
  with tempfile.TemporaryDirectory()as root:
   c,p,a=self.fixture(root)
   for proof,paths in [(None,a),(p,None)]:
    with self.assertRaises(ValueError):self.compile(c,proof,paths)
 def test_actual_cli_requires_explicit_proof_and_map_before_writing(self):
  with tempfile.TemporaryDirectory()as root:
   root=Path(root);c,p,a=self.fixture(root);catalog=root/'catalog.json';catalog.write_text(json.dumps(c))
   proof=root/'proof.json';proof.write_text(json.dumps(p));paths=root/'paths.json';paths.write_text(json.dumps({k:str(v)for k,v in a.items()}));output=root/'output'
   command=[sys.executable,str(ROOT/'scripts/compile_compute_policy.py'),'--catalog',str(catalog),'--output',str(output)]
   for extra in [[],['--native-group-evidence',str(proof)],['--native-group-artifacts',str(paths)]]:
    run=subprocess.run(command+extra,capture_output=True,timeout=3);self.assertEqual(run.returncode,1);self.assertFalse(output.exists())
   extra=['--native-group-evidence',str(proof),'--native-group-artifacts',str(paths)]
   run=subprocess.run(command+extra,capture_output=True,timeout=3);self.assertEqual(run.returncode,0,run.stderr)
   self.assertEqual(json.loads((output/'policy.json').read_text())['policyHash'],p['policy_hash'])
   self.assertEqual(json.loads((output/'native-group-evidence.json').read_text()),p)
   self.assertEqual(json.loads((output/'release-lock.json').read_text())['status'],'unqualified')
   run=subprocess.run(command+extra+['--check'],capture_output=True,timeout=3);self.assertEqual(run.returncode,0,run.stderr)
 def test_rehashed_duplicate_and_nonfinite_gate_json_are_not_trusted(self):
  for raw in [b'{"gate":"mps","gate":"forged"}',b'{"gate":"mps","value":NaN}']:
   with self.subTest(raw=raw),tempfile.TemporaryDirectory()as root:
    c,p,a=self.fixture(root);a['mps'].write_bytes(raw);p['gates']['mps']['evidence_sha256']='sha256:'+hashlib.sha256(raw).hexdigest()
    with self.assertRaises(ValueError):self.compile(c,p,a)
 def test_gate_file_hardlinks_and_wrong_actual_owner_are_rejected(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory()as root:
   c,p,a=self.fixture(root);os.link(a['mps'],Path(root)/'duplicate')
   with self.assertRaises(ValueError):self.compile(c,p,a)
  with tempfile.TemporaryDirectory()as root:
   c,p,a=self.fixture(root)
   with patch.object(compiler.os,'geteuid',return_value=os.geteuid()+1),self.assertRaises(ValueError):self.compile(c,p,a)
