"""Exercise the literal candidate CEL on real compiler runtime projections."""
import copy
import unittest

import cel_evaluate
import compiled_fixtures
import render_policy


ACTOR = 'system:serviceaccount:offline:declared-argo-controller'
EXECUTOR = 'registry.invalid/executor@sha256:' + '2' * 64


class DynamicAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = compiled_fixtures.generate()
        owners = [{'name': value['compiledWorkflow']['metadata']['name'],
                   'uid': value['declaredControllerPod']['object']['metadata']['ownerReferences'][0]['uid']}
                  for value in cls.fixtures['fixtures'].values()]
        cls.bundle = render_policy.build(executor_image=EXECUTOR,
            create_creators=[ACTOR], update_creators=[ACTOR], owners=owners)
        cls.params = cls.bundle['items'][1]
        cls.policy = cls.bundle['items'][2]
        cls.originals = {name: (render_policy.ROOT / name).read_bytes() for name in (
            'platform-staging/admission.yaml', 'platform-staging/admission-parameters-crd.yaml',
            'platform-staging/workload-rbac.yaml', 'compute-policy/catalog.json')}

    def inputs(self, profile='batch-shared-5', *, operation='CREATE'):
        pod = copy.deepcopy(self.fixtures['fixtures'][profile]['declaredControllerPod']['object'])
        pod['metadata']['uid'] = '11111111-1111-1111-1111-111111111111'
        return {'object': pod, 'params': copy.deepcopy(self.params),
                'request': {'namespace': compiled_fixtures.NAMESPACE, 'operation': operation,
                            'userInfo': {'username': ACTOR}},
                'oldObject': copy.deepcopy(pod) if operation == 'UPDATE' else None}

    def check(self, inputs, accepted, *, message=None):
        result = cel_evaluate.evaluate_policy(self.policy, inputs)
        diagnostics = {key: result[key] for key in ('status','compiled','evaluated','allExpressionsTrue')}
        diagnostics['failures'] = [{key: entry[key] for key in ('stage','index','failure','errorType') if key in entry}
                                  for entry in result['expressions'] if entry.get('failure')]
        self.assertTrue(result['compiled'], diagnostics)
        self.assertEqual(result['allExpressionsTrue'], accepted, diagnostics)
        if message:
            indexes = [i for i, rule in enumerate(self.policy['spec']['validations'])
                       if message in rule['message']]
            self.assertTrue(indexes, message)
            self.assertTrue(any(entry.get('failure') for entry in result['expressions']
                                if entry['stage'] == 'validation' and entry['index'] in indexes), diagnostics)
        return result

    def test_actual_compiler_three_profiles_are_accepted_as_pre_injection_shapes(self):
        for profile in self.fixtures['fixtures']:
            with self.subTest(profile=profile):
                result = self.check(self.inputs(profile), True)
                self.assertTrue(result['evaluated'])
        self.assertFalse(self.fixtures['qualification']['production'])
        self.assertFalse(self.fixtures['qualification']['argoControllerMaterialization'])

    def test_empty_registry_and_unknown_creator_deny_without_skipping(self):
        cases = ['createCreators', 'owners']
        for field in cases:
            with self.subTest(empty=field):
                value = self.inputs(); value['params'][field] = []
                self.check(value, False)
        value = self.inputs(); value['request']['userInfo']['username'] = 'ordinary-student'
        result = self.check(value, False, message='approved creator')
        self.assertTrue(result['expressions'][0]['resultBool'])
        self.assertEqual(len(result['expressions']), 1 + len(self.policy['spec']['validations']))

    def test_parent_uid_name_controller_and_owner_count_are_fenced(self):
        for field, changed in [('uid', '22222222-2222-2222-2222-222222222222'),
                               ('name', 'other-workflow'), ('kind', 'Job'),
                               ('apiVersion', 'batch/v1'), ('controller', False)]:
            with self.subTest(field=field):
                value = self.inputs(); value['object']['metadata']['ownerReferences'][0][field] = changed
                self.check(value, False, message='parent Workflow UID')
        value = self.inputs(); value['object']['metadata']['ownerReferences'].append(
            copy.deepcopy(value['object']['metadata']['ownerReferences'][0]))
        self.check(value, False)
        value = self.inputs(); del value['object']['metadata']['ownerReferences']
        self.check(value, False)

    def test_update_identity_and_parent_cannot_change(self):
        self.check(self.inputs(operation='UPDATE'), True)
        for field, changed in [('uid', '22222222-2222-2222-2222-222222222222'),
                               ('ownerReferences', [])]:
            value = self.inputs(operation='UPDATE'); value['object']['metadata'][field] = changed
            self.check(value, False, message='Updates may not replace')
        value = self.inputs(operation='UPDATE'); value['params']['updateCreators'] = []
        self.check(value, False)
        value = self.inputs(operation='UPDATE'); value['oldObject'] = None
        self.check(value, False)

    def test_cache_initializer_cannot_receive_extra_execution_or_credentials(self):
        for name, mutate in (
            ('command', lambda c: c.update(command=['sh','-c','cat /cache-root/usage.cache'])),
            ('uid', lambda c: c['args'].__setitem__(4, '0')),
            ('image', lambda c: c.update(image=EXECUTOR)),
            ('workingDir', lambda c: c.update(workingDir='/cache-root')),
            ('loader', lambda c: c['env'].append({'name':'LD_PRELOAD','value':'/evil.so'})),
            ('secret', lambda c: c.update(envFrom=[{'secretRef':{'name':'cps-artifacts'}}])),
            ('gpu', lambda c: c['volumeMounts'].append({'name':'cps-mps-pipe','mountPath':'/mps/pipe'})),
            ('secret-mount', lambda c: c['volumeMounts'].append({'name':'artifacts','mountPath':'/secrets'})),
            ('hook', lambda c: c.update(lifecycle={'postStart':{'exec':{'command':['sh']}}})),
            ('privileged', lambda c: c['securityContext'].update(privileged=True)),
            ('capability', lambda c: c['securityContext']['capabilities'].update(add=['SYS_ADMIN'])),
            ('resources', lambda c: c['resources']['limits'].update({'nvidia.com/gpu':'1'})),
            ('mount-propagation', lambda c: c['volumeMounts'][0].update(mountPropagation='Bidirectional')),
        ):
            with self.subTest(name=name):
                value = self.inputs(); mutate(value['object']['spec']['initContainers'][0])
                self.check(value, False)

    def test_gpu_mount_paths_cache_inode_and_initializer_count_are_exact(self):
        for name, mutate in (
            ('arbitrary-host', lambda p: p['volumes'].append({'name':'root','hostPath':{'path':'/','type':'Directory'}})),
            ('host-symlink-prefix', lambda p: p['volumes'][1]['hostPath'].update(path='/run/nvidia/mps/nvidia.com/gpu/pipe/../')),
            ('wrong-type', lambda p: p['volumes'][1]['hostPath'].update(type='DirectoryOrCreate')),
            ('cache-uncapped', lambda p: p['volumes'][0]['emptyDir'].pop('sizeLimit')),
            ('cache-ram', lambda p: p['volumes'][0]['emptyDir'].update(medium='Memory')),
            ('cache-path', lambda p: p['containers'][0]['volumeMounts'][0].update(mountPath='/cache-root')),
            ('cache-inode', lambda p: p['containers'][0]['volumeMounts'][0].update(subPath='usage.cache')),
            ('cache-expression', lambda p: p['containers'][0]['volumeMounts'][0].update(subPathExpr='$(EVIL)')),
            ('mount-propagation', lambda p: p['containers'][0]['volumeMounts'][1].update(mountPropagation='HostToContainer')),
            ('duplicate-initializer', lambda p: p['initContainers'].append(copy.deepcopy(p['initContainers'][0]))),
            ('other-init', lambda p: p['initContainers'].append({'name':'evil','image':compiled_fixtures.IMAGE,'command':['sh']})),
            ('missing-initializer', lambda p: p.pop('initContainers')),
            ('other-pvc', lambda p: p['volumes'].append({'name':'other-project','persistentVolumeClaim':{'claimName':'research-data'}})),
        ):
            with self.subTest(name=name):
                value = self.inputs(); mutate(value['object']['spec']); self.check(value, False)

    def test_main_policy_cannot_be_overridden(self):
        for name, mutate in (
            ('scheduler', lambda p: p.update(schedulerName='default-scheduler')),
            ('account', lambda p: p.update(serviceAccountName='default')),
            ('auto-token', lambda p: p.update(automountServiceAccountToken=True)),
            ('host-network', lambda p: p.update(hostNetwork=True)),
            ('host-pid', lambda p: p.update(hostPID=True)),
            ('host-ipc', lambda p: p.update(hostIPC=True)),
            ('shared-processes', lambda p: p.update(shareProcessNamespace=True)),
            ('root', lambda p: p['containers'][0]['securityContext'].update(runAsUser=0)),
            ('gid', lambda p: p['containers'][0]['securityContext'].update(runAsGroup=1000)),
            ('capability', lambda p: p['containers'][0]['securityContext']['capabilities'].update(add=['SYS_PTRACE'])),
            ('image', lambda p: p['containers'][0].update(image='python:latest')),
            ('executor-as-main', lambda p: p['containers'][0].update(image=EXECUTOR)),
            ('resource-override', lambda p: p['containers'][0]['resources']['limits'].update(memory='32Gi')),
            ('gpu-key', lambda p: p['containers'][0]['resources']['limits'].update({'nvidia.com/gpu':'1'})),
            ('loader-env', lambda p: p['containers'][0]['env'].append({'name':'LD_PRELOAD','value':'/evil.so'})),
            ('indexed-quota', lambda p: p['containers'][0]['env'][0].update(value='40960m')),
            ('second-quota', lambda p: p['containers'][0]['env'].append({'name':'CUDA_DEVICE_MEMORY_LIMIT_2','value':'40960m'})),
            ('duplicate-env', lambda p: p['containers'][0]['env'].append(copy.deepcopy(p['containers'][0]['env'][0]))),
            ('secret-env', lambda p: p['containers'][0]['env'].append({'name':'SECRET','valueFrom':{'secretKeyRef':{'name':'cps-artifacts','key':'key'}}})),
            ('envFrom', lambda p: p['containers'][0].update(envFrom=[{'configMapRef':{'name':'other-map'}}])),
            ('hook', lambda p: p['containers'][0].update(lifecycle={'postStart':{'exec':{'command':['sh']}}})),
            ('sidecar', lambda p: p['containers'].append({'name':'other','image':compiled_fixtures.IMAGE})),
            ('deadline', lambda p: p.update(activeDeadlineSeconds=181)),
            ('placement', lambda p: p.update(nodeName='k3s-wk-gpu2')),
            ('retry', lambda p: p.update(restartPolicy='Always')),
        ):
            with self.subTest(name=name):
                value = self.inputs(); mutate(value['object']['spec']); self.check(value, False)

    def test_post_injection_shapes_remain_denied_until_actual_transition_qualification(self):
        value = self.inputs()
        value['object']['spec']['volumes'].append({'name':'kai-vgpu',
            'hostPath':{'path':'/usr/local/vgpu','type':'DirectoryOrCreate'}})
        self.check(value, False, message='KAI injection is not yet qualified')
        value = self.inputs()
        value['object']['spec']['containers'][0]['env'].append({'name':'NVIDIA_VISIBLE_DEVICES',
            'valueFrom':{'configMapKeyRef':{'name':'copied-kai-map','key':'NVIDIA_VISIBLE_DEVICES'}}})
        self.check(value, False, message='pre-injection shape')

    def executor_inputs(self):
        # Explicit synthetic materialization: verify the credential boundary
        # without claiming that Argo produced this Pod or that tokens ran.
        value = self.inputs()
        security = copy.deepcopy(value['object']['spec']['containers'][0]['securityContext'])
        security.update(runAsUser=10001, runAsGroup=10001, readOnlyRootFilesystem=True)
        pod = value['object']['spec']
        pod['volumes'].append({'name':'artifacts','secret':{'secretName':'cps-artifacts'}})
        wait = {'name':'wait','image':EXECUTOR,
            'command':['argoexec','wait','--loglevel','info','--log-format','text','--gloglevel','0'],
            'securityContext':security,
            'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'1','memory':'256Mi'}},
            'volumeMounts':[{'name':'artifacts','mountPath':'/argo/secret/cps-artifacts','readOnly':True}]}
        pod['containers'].append(wait)
        executor_init = copy.deepcopy(wait); executor_init['name'] = 'init'
        executor_init['command'][1] = 'init'
        pod['initContainers'].insert(0, executor_init)
        return value

    def test_executor_and_cache_contracts_are_separate_and_both_credential_safe(self):
        self.check(self.executor_inputs(), True)
        for name, mutate in (
            ('executor-command', lambda p: p['containers'][1].update(command=['sh','-c','cat /argo/secret/cps-artifacts/secretKey'])),
            ('executor-init-command', lambda p: p['initContainers'][0].update(command=['sh'])),
            ('executor-environment', lambda p: p['containers'][1].update(env=[{'name':'LD_PRELOAD','value':'/evil.so'}])),
            ('executor-hook', lambda p: p['initContainers'][0].update(lifecycle={'postStart':{'exec':{'command':['sh']}}})),
            ('executor-root', lambda p: p['containers'][1]['securityContext'].update(runAsUser=0)),
            ('executor-cap', lambda p: p['containers'][1]['securityContext']['capabilities'].update(add=['SYS_ADMIN'])),
            ('executor-writable-secret', lambda p: p['containers'][1]['volumeMounts'][0].update(readOnly=False)),
            ('executor-secret-shadow', lambda p: p['containers'][1]['volumeMounts'][0].update(mountPath='/usr/local/bin')),
            ('kernel-secret', lambda p: p['containers'][0]['volumeMounts'].append(copy.deepcopy(p['containers'][1]['volumeMounts'][0]))),
            ('initializer-secret', lambda p: p['initContainers'][1]['volumeMounts'].append(copy.deepcopy(p['containers'][1]['volumeMounts'][0]))),
            ('executor-propagation', lambda p: p['containers'][1]['volumeMounts'][0].update(mountPropagation='Bidirectional')),
            ('host-port', lambda p: p['containers'][0].update(ports=[{'containerPort':8080,'hostPort':8080}])),
        ):
            with self.subTest(name=name):
                value = self.executor_inputs(); mutate(value['object']['spec']); self.check(value, False)

    def test_all_executable_and_pod_security_extras_are_closed(self):
        fields = [('procMount','Unmasked'), ('seLinuxOptions',{'type':'spc_t'}),
                  ('windowsOptions',{'hostProcess':True}), ('appArmorProfile',{'type':'Unconfined'}),
                  ('appArmorProfile',{'type':'Localhost','localhostProfile':'unreviewed'}),
                  ('capabilities',{'drop':['ALL'],'add':['NET_ADMIN']})]
        for location in ('main','wait','init','cps-gpu-cache-init'):
            for field, changed in fields:
                with self.subTest(location=location,field=field,value=changed):
                    value = self.executor_inputs()
                    containers = value['object']['spec']['containers'] + value['object']['spec']['initContainers']
                    next(c for c in containers if c['name']==location)['securityContext'][field] = changed
                    self.check(value, False)
        for field, changed in [('supplementalGroups',[0]), ('sysctls',[{'name':'net.ipv4.ip_forward','value':'1'}]),
                               ('appArmorProfile',{'type':'Unconfined'}), ('seLinuxOptions',{'type':'spc_t'}),
                               ('windowsOptions',{'hostProcess':True})]:
            with self.subTest(podfield=field):
                value = self.inputs(); value['object']['spec']['securityContext'][field] = changed
                self.check(value, False)
        for field in ('allowPrivilegeEscalation','capabilities','seccompProfile','runAsNonRoot'):
            with self.subTest(missingWaitField=field):
                value = self.executor_inputs(); value['object']['spec']['containers'][1]['securityContext'].pop(field)
                self.check(value, False)
        value = self.executor_inputs(); value['object']['spec']['containers'][1].pop('securityContext')
        self.check(value, False)

    def test_device_loader_controls_and_subresource_bypasses_are_rejected(self):
        for name in ('LD_AUDIT','CUDA_VISIBLE_DEVICES','CUDA_MPS_PINNED_DEVICE_MEM_LIMIT',
                     'HAMI_DISABLE','VGPU_DISABLE','MPS_DEBUG','NVIDIA_DRIVER_CAPABILITIES','GPU_PORTION',
                     'ld_audit','cUdA_visible_devices','hami_disable','pythonpath'):
            with self.subTest(environment=name):
                value = self.inputs(); value['object']['spec']['containers'][0]['env'].append({'name':name,'value':'1'})
                self.check(value, False, message='pre-injection shape')
        value = self.inputs(); value['object']['metadata']['annotations']['gpu-fraction-num-devices'] = '2'
        self.check(value, False)
        resources = self.policy['spec']['matchConstraints']['resourceRules'][0]['resources']
        self.assertIn('pods/ephemeralcontainers', resources)
        self.assertIn('pods/resize', resources)
        value = self.inputs(operation='UPDATE')
        value['request']['subResource'] = 'ephemeralcontainers'
        value['object']['spec']['ephemeralContainers'] = [{'name':'debug','image':compiled_fixtures.IMAGE}]
        self.check(value, False, message='Ephemeral container access')
        value = self.inputs(operation='UPDATE'); value['request']['subResource'] = 'resize'
        value['object']['spec']['containers'][0]['resources']['limits']['cpu'] = '8'
        self.check(value, False, message='CPU and memory requests')

    def test_executor_resources_dra_and_readonly_runtime_mounts_cannot_bypass_accounting(self):
        for location in ('wait','init'):
            for mutation in ('gpu','cpu','missing'):
                with self.subTest(location=location,mutation=mutation):
                    value = self.executor_inputs(); pod = value['object']['spec']
                    target = next(c for c in pod['containers']+pod['initContainers'] if c['name']==location)
                    if mutation=='gpu': target['resources']['limits']['nvidia.com/gpu'] = '8'
                    elif mutation=='cpu': target['resources']['limits']['cpu'] = '32'
                    else: target.pop('resources')
                    self.check(value, False, message='declared Argo CPU and memory limits')
        value = self.inputs(); value['object']['spec']['resourceClaims'] = [{'name':'gpu','resourceClaimName':'extra-gpu'}]
        self.check(value, False, message='DRA resource claims')
        for location in ('main','wait','init','cps-gpu-cache-init'):
            value = self.executor_inputs(); pod = value['object']['spec']
            target = next(c for c in pod['containers']+pod['initContainers'] if c['name']==location)
            target['resources']['claims'] = [{'name':'gpu'}]
            self.check(value, False, message='DRA resource claims')
        for index in range(3):
            value = self.inputs(); value['object']['spec']['containers'][0]['volumeMounts'][index]['readOnly'] = True
            self.check(value, False)

    def test_production_scope_and_existing_controls_are_preserved(self):
        for namespace in ('cps-workflows','jupyterhub','cit-jhub','cps-compute','cps-gpu-qualification'):
            with self.subTest(namespace=namespace), self.assertRaises(ValueError):
                render_policy.build(namespace=namespace, executor_image=EXECUTOR)
        for name, original in self.originals.items():
            self.assertEqual((render_policy.ROOT / name).read_bytes(), original)
        self.assertEqual(self.bundle['items'][3]['spec']['validationActions'], ['Deny'])
        self.assertEqual(self.bundle['items'][3]['spec']['paramRef']['parameterNotFoundAction'], 'Deny')
        self.assertFalse(any(item['kind'] == 'Namespace' for item in self.bundle['items']))
        self.assertNotEqual(self.bundle['items'][0]['spec']['group'], 'compute.cps.unileoben.ac.at')
        self.assertEqual([c['name'] for c in self.policy['spec']['matchConditions']], ['isolated-qualification-namespace'])
        self.assertNotIn('.split(', str(self.policy))

    def test_builder_rejects_unpinned_images_unknown_registry_and_duplicate_owners(self):
        with self.assertRaises(ValueError): render_policy.build(executor_image='argoexec:latest')
        with self.assertRaises(ValueError): render_policy.build(executor_image=EXECUTOR, create_creators=['student'])
        with self.assertRaises(ValueError): render_policy.build(executor_image=EXECUTOR,
            owners=[{'name':'a','uid':'11111111-1111-1111-1111-111111111111','extra':True}])
        with self.assertRaises(ValueError): render_policy.build(executor_image=EXECUTOR,
            owners=[{'name':'a','uid':'11111111-1111-1111-1111-111111111111'},
                    {'name':'b','uid':'11111111-1111-1111-1111-111111111111'}])


if __name__ == '__main__': unittest.main()
