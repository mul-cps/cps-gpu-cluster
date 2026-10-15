"""Actual wheel compiler regressions; no controller, Kubernetes or GPU calls."""
import copy
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
import uuid
from unittest.mock import patch

import compiled_fixtures as fixture


class CompiledFixtureTests(unittest.TestCase):
    def test_reproducible_actual_compiler_output_and_provenance(self):
        before = fixture.DEFAULT_CATALOG.read_bytes()
        a,b = fixture.generate(),fixture.generate()
        self.assertEqual(a,b)
        self.assertTrue(fixture.verify(a))
        self.assertEqual(fixture.DEFAULT_CATALOG.read_bytes(),before)
        self.assertEqual(a['provenance']['baseCatalogSha256'],hashlib.sha256(before).hexdigest())
        self.assertEqual(a['provenance']['moduleSha256']['cps_compute/gpu_runtime.py'],fixture.GPU_MODULE_SHA256)
        self.assertIs(a['provenance']['baseCatalogGpuQualified'],False)
        self.assertIs(a['provenance']['baseCatalogProfilesEnabled'],False)
        self.assertTrue(all(value is False for value in a['qualification'].values()))
        self.assertEqual(a['pendingSurfaces']['hub']['status'],'pending-fresh-actual-KubeSpawner-manifest')
        self.assertEqual(a['pendingSurfaces']['jobset']['status'],'pending-separate-generator-and-admission-contract')
        owners = [entry['declaredControllerPod']['object']['metadata']['ownerReferences'][0]
                  for entry in a['fixtures'].values()]
        self.assertEqual(len({owner['uid'] for owner in owners}),3)
        for owner in owners:
            self.assertEqual(owner['uid'],str(uuid.uuid5(uuid.NAMESPACE_URL,
                'fixture://workflow/'+fixture.NAMESPACE+'/'+owner['name'])))
        other = fixture.generate(namespace='cps-dynamic-admission-different')
        self.assertTrue({owner['uid'] for owner in owners}.isdisjoint({
            entry['declaredControllerPod']['object']['metadata']['ownerReferences'][0]['uid']
            for entry in other['fixtures'].values()}))

    def test_actual_argo_patch_contains_exact_compiler_private_runtime(self):
        manifest = fixture.generate()
        for gib in (5,10,20):
            entry = manifest['fixtures']['batch-shared-'+str(gib)]
            workflow = entry['compiledWorkflow'];projection = entry['runtimeProjection']
            self.assertEqual(projection,json.loads(workflow['spec']['templates'][0]['podSpecPatch']))
            self.assertEqual(entry['evidenceStage'],'compiled-pre-controller')
            self.assertEqual(workflow['spec']['podMetadata']['annotations'],
                {'gpu-memory':str(gib*1024),'gpu-fraction-container-name':'main'})
            init = projection['initContainers'][0]
            self.assertEqual(init['image'],fixture.IMAGE)
            self.assertEqual(init['command'],['python','-m','cps_compute.gpu_runtime'])
            self.assertEqual(init['args'],['initialize-cache','--directory','/cache-root','--uid','1000','--gid','100'])
            self.assertEqual(init['securityContext']['readOnlyRootFilesystem'],True)
            main = projection['containers'][0]
            env = {entry['name']:entry['value'] for entry in main['env']}
            self.assertEqual(env['CUDA_DEVICE_MEMORY_LIMIT_0'],str(gib*1024)+'m')
            self.assertEqual(main['volumeMounts'][0],{'name':'cps-gpu-cache','mountPath':'/tmp/cps-workspace-usage.cache',
                                                      'subPath':'private/usage.cache'})
            self.assertEqual(projection['volumes'][0],{'name':'cps-gpu-cache','emptyDir':{'sizeLimit':'64Mi'}})
            self.assertEqual({v['hostPath']['path'] for v in projection['volumes'] if 'hostPath' in v},
                {'/run/nvidia/mps/nvidia.com/gpu/pipe','/run/nvidia/mps/shm'})
            self.assertNotIn('NVIDIA_VISIBLE_DEVICES',env)
            self.assertNotIn('CUDA_DEVICE_MEMORY_LIMIT',env)
            self.assertFalse(entry['declaredControllerPod']['actualControllerExecuted'])
            self.assertFalse(entry['declaredControllerPod']['actualWebhookExecuted'])
            self.assertFalse(entry['declaredControllerPod']['executorMaterialized'])

    def test_actual_policy_rejects_malicious_submission_inputs(self):
        base = json.loads(fixture.DEFAULT_CATALOG.read_bytes())
        catalog = fixture.fixture_catalog(base,fixture.NAMESPACE)
        module,_ = fixture.load_sdk(fixture.DEFAULT_WHEEL)
        policy = module.Policy(catalog)
        cases = []
        for field,value in [('serviceAccountName','admin'),('schedulerName','other'),('podSpecPatch','{}'),
                            ('hostNetwork',True),('podPriorityClassName','exam')]:
            source = fixture.workflow_input(catalog,5);source['spec'][field] = value;cases.append((field,source))
        for field,value in [('env',[{'name':'LD_PRELOAD','value':'unsafe'}]),
                            ('securityContext',{'privileged':True}),
                            ('volumeMounts',[{'name':'host','mountPath':'/host'}]),
                            ('envFrom',[{'secretRef':{'name':'private'}}])]:
            source = fixture.workflow_input(catalog,5);source['spec']['templates'][0]['container'][field] = value
            cases.append((field,source))
        source = fixture.workflow_input(catalog,5)
        source['spec']['templates'][0]['container']['resources']['limits']['memory'] = '64Gi'
        cases.append(('resourceOverride',source))
        source = fixture.workflow_input(catalog,5);source['spec']['templates'][0]['container']['image'] = 'python:latest'
        cases.append(('mutableImage',source))
        source = fixture.workflow_input(catalog,5);source['spec']['templates'][0]['initContainers'] = []
        cases.append(('userInitializer',source))
        source = fixture.workflow_input(catalog,5);source['metadata']['namespace'] = 'cps-workflows'
        cases.append(('userNamespace',source))
        for name,value in cases:
            with self.subTest(name=name),self.assertRaises(module.PolicyError):policy.validate(value,'batch-shared-5',fixture.OWNER)

    def test_recomputed_manifest_hash_cannot_bless_matching_forgery(self):
        for change in ('projection','initializer','source','uid','hostPath','declaredPod','compiledWorkflow','qualified','pending'):
            value = fixture.generate();entry = value['fixtures']['batch-shared-20']
            if change == 'projection':entry['runtimeProjection']['containers'][0]['env'][0]['value'] = '40960m'
            if change == 'initializer':entry['runtimeProjection']['initContainers'][0]['args'] = ['evil']
            if change == 'source':value['provenance']['sourceCommit'] = '0'*40
            if change == 'uid':entry['runtimeProjection']['securityContext']['runAsUser'] = 0
            if change == 'hostPath':entry['runtimeProjection']['volumes'][1]['hostPath']['path'] = '/'
            if change == 'declaredPod':entry['declaredControllerPod']['object']['spec']['hostPID'] = True
            if change == 'compiledWorkflow':entry['compiledWorkflow']['spec']['podSpecPatch'] = '{}'
            if change == 'qualified':value['qualification']['liveAdmission'] = True
            if change == 'pending':value['pendingSurfaces']['hub']['status'] = 'qualified'
            value['manifestSha256'] = fixture.digest({k:v for k,v in value.items() if k != 'manifestSha256'})
            with self.subTest(change=change),self.assertRaises(ValueError):fixture.verify(value)

    def test_wrong_wheel_and_catalog_activation_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            wheel = path/'wrong.whl';wheel.write_bytes(b'wrong source')
            with self.assertRaisesRegex(ValueError,'wheel SHA256'):fixture.generate(wheel)
            catalog = json.loads(fixture.DEFAULT_CATALOG.read_bytes());catalog['gpuQualification']['qualified'] = True
            source = path/'catalog.json';source.write_text(json.dumps(catalog))
            with self.assertRaisesRegex(ValueError,'disabled/unqualified'):fixture.generate(catalog_path=source)
            catalog['gpuQualification']['qualified'] = False;catalog['profiles']['batch-shared-5']['enabled'] = True
            source.write_text(json.dumps(catalog))
            with self.assertRaisesRegex(ValueError,'disabled/unqualified'):fixture.generate(catalog_path=source)
        for namespace in ('cps-workflows','jupyterhub','cit-jhub','cit-jupyterhub','cps-compute','default','kube-system','UPPER','../other'):
            with self.subTest(namespace=namespace),self.assertRaises(ValueError):fixture.generate(namespace=namespace)

    def test_explicit_namespace_binding_and_no_network(self):
        value = fixture.generate(namespace='cps-dynamic-admission-another')
        with self.assertRaisesRegex(ValueError,'independently selected'):fixture.verify(value)
        self.assertTrue(fixture.verify(value,namespace='cps-dynamic-admission-another'))
        def denied(*args,**kwargs):raise AssertionError('Offline compiler attempted network access')
        with patch.object(socket,'create_connection',denied),patch.object(socket,'getaddrinfo',denied), \
                patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'sendto',denied):
            self.assertTrue(fixture.verify(fixture.generate()))

if __name__ == '__main__':unittest.main()
