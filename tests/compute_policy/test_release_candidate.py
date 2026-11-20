"""CPU fixtures test compatibility integrity; they create no hardware authority."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'scripts/compute-platform/verify-release-candidate.py'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def put(value, fields, item):
    for field in fields[:-1]:
        value = value.setdefault(field, {})
    value[fields[-1]] = item


class ReleaseCandidateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), 'Current candidate compatibility verifier is not implemented')
        spec = importlib.util.spec_from_file_location('release_candidate', MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.private = Path(self.tmp.name) / 'private'
        self.repository = Path(self.tmp.name) / 'repository'
        self.private.mkdir(); self.repository.mkdir()
        self.inventory = json.loads((ROOT / 'platform-staging/releases/qualification-20261009.json').read_text())
        # These synthetic artifacts exercise the current verifier/compiler;
        # the historical qualification inventory itself remains untouched.
        self.inventory['compilerSha256'] = sha((ROOT / 'scripts/compile_compute_policy.py').read_bytes())
        spec = importlib.util.spec_from_file_location('native_fixture', ROOT / 'tests/compute_policy/test_native_group.py')
        native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
        catalog, proof, self.gate_paths = native.NativeGroupTests().fixture(self.private)
        self.values = {name: {} for name in self.inventory['artifacts']}
        for package in self.inventory['sdkPackages'].values():
            body = ('# ' + package['sourceCommit'] + '\n').encode()
            package['modules'] = {'cps_compute/__init__.py': hashlib.sha256(body).hexdigest()}
            wheel = io.BytesIO()
            with zipfile.ZipFile(wheel, 'w') as z:
                z.writestr('cps_compute/__init__.py', body)
                z.writestr('cps_compute-0.1.0.dist-info/METADATA', 'Name: cps-compute\nVersion: 0.1.0\n')
            raw = wheel.getvalue(); self.values[package['wheelArtifact']] = raw
            put(self.values[package['sourceReceipt']], package['revisionField'], package['sourceCommit'])
            put(self.values[package['sourceReceipt']], package['wheelHashField'], sha(raw).removeprefix('sha256:'))
            put(self.values[package['moduleEvidence']], package['moduleField'], package['modules'])
        for role, component in self.inventory['components'].items():
            package = self.inventory['sdkPackages'][component['sdkPackage']]
            put(self.values[component['imageReceipt']], component['imageField'], component['image'])
            report = self.values[component['verificationArtifact']]
            put(report, component['moduleField'], package['modules'])
            report['wheel_sha256'] = sha(self.values[package['wheelArtifact']]).removeprefix('sha256:')
            report['runtime_versions'] = {'cps-compute':'0.1.0','jupyterhub':'5.5.2','jupyterhub-kubespawner':'7.1.0'}
            report['versions'] = report['runtime_versions']
            report['source_revision'] = package['sourceCommit']
            report['runtime_versions']['e2x-course-hub']='0.1.1'
            component['registryKind'] = 'digest'
            self.values[component['registryArtifact']] = component['image'].split('@')[1].encode() + b'\n'
        admin = self.inventory['components']['admin']
        body = b'# synthetic backend\n'
        admin['backendModules'] = {'e2x_course_hub/__init__.py':hashlib.sha256(body).hexdigest()}
        admin['staticFiles'] = {}
        for name, artifact in admin['staticArtifacts'].items():
            static = ('# synthetic ' + name + '\n').encode()
            self.values[artifact] = static
            admin['staticFiles'][name] = hashlib.sha256(static).hexdigest()
        self.values['adminVerify'].update(admin_source_files_verified=1,admin_static_files_verified=3)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as tar:
            item = tarfile.TarInfo('e2x_course_hub/__init__.py'); item.size=len(body); tar.addfile(item,io.BytesIO(body))
        self.values['adminArchive'] = archive.getvalue()
        self.values['adminSource'].update(backend_revision=admin['backendCommit'],ui_revision=admin['uiCommit'],python_backend_files=admin['backendModules'],static_files=admin['staticFiles'])
        self.values['adminReceipt'].update(backend_revision=admin['backendCommit'],ui_source_revision=admin['uiCommit'],static_manifest=admin['staticFiles'])
        self.values['notebookConfig']={'Labels':{'org.opencontainers.image.revision':self.inventory['components']['notebook']['parentNotebookCommit']}}
        self.values['catalog'] = catalog
        self.values['nativeProof'] = proof
        compiled = native.compiler.compile_catalog(catalog,native_group_evidence=proof,native_group_artifacts=self.gate_paths)
        self.values['compiledPolicy'] = compiled
        self.values['releaseLock'] = {'policyVersion':compiled['version'],'policyHash':compiled['policyHash'],'status':'unqualified','compatibility':compiled['compatibility']}
        summary = json.loads((ROOT/'compute-policy/qualification/native-groups-v1.json').read_text())
        receipt = json.loads((ROOT/'platform-staging/gpu/native-group-pilot/qualification/qualified-runtime-receipt-20261009.json').read_text())
        summary['policy']['hash'] = compiled['policyHash']; receipt['policyHash'] = compiled['policyHash']
        self.inventory['policy']['hash'] = compiled['policyHash']
        summary['evidence']['privateProofRawSha256'] = sha(self.encode(proof))
        summary['evidence']['privateProofCanonicalSha256'] = sha(native.compiler.canonical(proof))
        for gate, entry in proof['gates'].items():
            self.values['gate:'+gate] = self.gate_paths[gate].read_bytes()
            summary['gates'][gate]['privateReportRawSha256'] = entry['evidence_sha256']
        self.values['runtimeReceipt'] = receipt
        summary['runtimeActivation']['receiptSha256'] = sha(self.encode(receipt))
        self.values['summary'] = summary
        self.flush()

    def encode(self, value):
        return value if isinstance(value,bytes) else (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()

    def flush(self):
        for name, value in self.values.items():
            artifact = self.inventory['artifacts'][name]
            artifact['path'] = name.replace(':','-') + '.bin'
            path = (self.repository if artifact['root']=='repository' else self.private)/artifact['path']
            raw = self.encode(value); path.write_bytes(raw); path.chmod(0o600)
            artifact['sha256'] = sha(raw)

    def verify(self):
        return self.module.verify_candidate(self.inventory,self.repository,self.private)

    def test_current_candidate_integrity_preserves_unqualified_full_platform(self):
        result = self.verify()
        self.assertFalse(result['productionQualified'])
        self.assertEqual(result['qualifiedScopes'],['cps:native-group-b','cit:native-group-a'])
        self.assertEqual(result['verifiedArtifacts'],len(self.values))

    def test_same_version_stale_wheel_is_rejected_after_artifact_rehash(self):
        self.values['sdkWheel'] = self.values['notebookWheel']; self.flush()
        with self.assertRaisesRegex(ValueError,'wheel|module'): self.verify()

    def test_rehashed_installed_module_mismatch_is_rejected(self):
        self.values['gatewayVerify']['python_source_sha256']['cps_compute/__init__.py']='0'*64; self.flush()
        with self.assertRaisesRegex(ValueError,'module'): self.verify()

    def test_rehashed_source_commit_mismatch_is_rejected(self):
        self.values['sdkReceipt']['sdk_revision']='f'*40; self.flush()
        with self.assertRaisesRegex(ValueError,'source'): self.verify()

    def test_rehashed_image_receipt_mismatch_is_rejected(self):
        self.values['sdkReceipt']['images']['gateway']='example.invalid@gateway'; self.flush()
        with self.assertRaisesRegex(ValueError,'image'): self.verify()

    def test_stale_compiled_policy_and_release_lock_are_rejected(self):
        for name in ['compiledPolicy','releaseLock']:
            original=copy.deepcopy(self.values[name]); self.values[name]['policyHash']='sha256:'+'f'*64; self.flush()
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'policy|lock'):self.verify()
            self.values[name]=original
        self.flush()

    def test_scope_or_full_platform_promotion_is_rejected(self):
        for field in ['productionQualified','matchingCurrentSdkNotebookMatrix','releasePublished','fleetPromoted']:
            self.inventory[field]=True
            with self.subTest(field=field),self.assertRaises(ValueError):self.verify()
            self.inventory[field]=False
        self.inventory['scope']['workspaces'].append('cps:native-group-a')
        with self.assertRaisesRegex(ValueError,'scope'):self.verify()

    def test_missing_private_inputs_do_not_report_passed(self):
        artifact=self.inventory['artifacts']['sdkWheel'];(self.private/artifact['path']).unlink()
        with self.assertRaises((ValueError,OSError)):self.verify()

    def test_rehashed_admin_source_or_ui_mismatch_is_rejected(self):
        for field in ['backend_revision','ui_source_revision']:
            original=self.values['adminReceipt'][field];self.values['adminReceipt'][field]='f'*40;self.flush()
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'admin'):self.verify()
            self.values['adminReceipt'][field]=original
        self.flush()

    def test_rehashed_runtime_scope_mismatch_is_rejected(self):
        self.values['runtimeReceipt']['scopes']=['cps:native-group-a'];self.flush()
        with self.assertRaisesRegex(ValueError,'receipt|scope'):self.verify()

    def test_unknown_registry_evidence_kind_is_rejected(self):
        self.inventory['components']['gateway']['registryKind']='unverified-placeholder'
        with self.assertRaisesRegex(ValueError,'registry'):self.verify()

    def test_failed_runtime_acceptance_cannot_be_rehashed_into_success(self):
        self.values['runtimeReceipt']['gpuControls']['kernelPositiveAndRecoveryPassedBoth']=False
        self.values['summary']['runtimeActivation']['receiptSha256']=sha(self.encode(self.values['runtimeReceipt']))
        self.flush()
        with self.assertRaisesRegex(ValueError,'acceptance'):self.verify()

    def test_rehashed_pool_broadening_must_match_native_proof(self):
        self.values['summary']['nodePool']['maxWorkspaces']=3
        self.inventory['scope']['nodePool']['maxWorkspaces']=3
        self.flush()
        with self.assertRaisesRegex(ValueError,'pool'):self.verify()

    def test_rehashed_image_source_revision_mismatch_is_rejected(self):
        self.values['gatewayVerify']['source_revision']='f'*40;self.flush()
        with self.assertRaisesRegex(ValueError,'source'):self.verify()

    def test_rehashed_admin_package_version_mismatch_is_rejected(self):
        self.values['adminVerify']['runtime_versions']['e2x-course-hub']='99.0.0';self.flush()
        with self.assertRaisesRegex(ValueError,'admin.*version'):self.verify()

    def test_rehashed_admin_static_bytes_mismatch_is_rejected(self):
        self.values['adminStaticJs'] += b'// changed after build\n';self.flush()
        with self.assertRaisesRegex(ValueError,'admin.*static'):self.verify()

    def test_rehashed_admin_installed_verification_count_mismatch_is_rejected(self):
        for field in ['admin_source_files_verified','admin_static_files_verified']:
            original=self.values['adminVerify'][field]
            self.values['adminVerify'][field]=original+1;self.flush()
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'admin.*installed'):self.verify()
            self.values['adminVerify'][field]=original
        self.flush()
