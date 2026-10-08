"""Regression contracts exposed by Kubernetes v1.34 server qualification."""
import copy
import unittest

import injected_policy
import quota_policy
import render_policy
import compiled_fixtures


class ServerContractTests(unittest.TestCase):
    def test_only_exact_api_server_default_tolerations_are_allowed(self):
        from celpy import Environment
        from celpy.adapter import json_to_cel
        policy = render_policy.build(executor_image='quay.io/argoproj/argoexec@sha256:' + '0' * 64)['items'][2]
        rule = next(x['expression'] for x in policy['spec']['validations']
            if x['message'] == 'The reviewed runtime image, 180-second maximum and scheduler placement cannot be replaced')
        environment = Environment()
        program = environment.program(environment.compile(rule))
        pod = copy.deepcopy(compiled_fixtures.generate()['fixtures']['batch-shared-5']['declaredControllerPod']['object'])
        pod['spec']['tolerations'] = [
            {'key': 'node.kubernetes.io/' + key, 'operator': 'Exists', 'effect': 'NoExecute', 'tolerationSeconds': 300}
            for key in ('not-ready', 'unreachable')]
        def allowed(value):
            return program.evaluate(json_to_cel({'object': value, 'request': {'operation': 'CREATE'}}))
        self.assertTrue(allowed(pod))
        for field, value in [('key', 'nvidia.com/gpu'), ('effect', 'NoSchedule'), ('tolerationSeconds', 301), ('value', 'unreviewed')]:
            candidate = copy.deepcopy(pod)
            candidate['spec']['tolerations'][0][field] = value
            self.assertFalse(allowed(candidate))
        candidate = copy.deepcopy(pod)
        candidate['spec']['tolerations'][1] = candidate['spec']['tolerations'][0]
        self.assertFalse(allowed(candidate))

    def test_pod_binding_references_the_rendered_policy(self):
        namespace = 'cps-dynamic-admission-server-regression'
        for builder in (render_policy.build, injected_policy.build):
            crd, params, policy, binding = builder(namespace=namespace,
                executor_image='quay.io/argoproj/argoexec@sha256:' + '0' * 64)['items']
            self.assertEqual(binding['spec']['policyName'], policy['metadata']['name'])
            self.assertEqual(binding['metadata']['name'], namespace + '-boundary')

    def test_quantity_maps_keep_runtime_keys_and_cardinality(self):
        expression = render_policy.required_tree('c.resources', {'requests': {'cpu': '10m', 'memory': '32Mi'}},
            map_fields=('c.resources.requests',))
        self.assertIn('dyn(c.resources).requests.cpu == "10m"', expression)
        self.assertIn('size(dyn(c.resources).requests) == 2', expression)

    def test_quota_cel_strings_have_finite_cost_bounds(self):
        crd = quota_policy.build()['items'][0]
        schema = crd['spec']['versions'][0]['schema']['openAPIV3Schema']
        properties = schema['properties']['records']['items']['properties']
        for name, field in properties.items():
            with self.subTest(field=name):
                self.assertIsInstance(field.get('maxLength'), int)
                self.assertGreater(field['maxLength'], 0)
        self.assertEqual(properties['gpuPortion']['maxLength'], 10)
        self.assertEqual(properties['physicalGpuMemoryMiB']['maxLength'], 6)
        self.assertEqual(properties['cudaDeviceMemoryLimit']['maxLength'], 6)

    def test_secret_allowlists_compile_without_dyn_string_list_literals(self):
        kwargs = {'executor_image': 'quay.io/argoproj/argoexec@sha256:' + '0' * 64}
        for build in (render_policy.build, injected_policy.build):
            with self.subTest(builder=build.__module__):
                policy = build(**kwargs)['items'][2]
                for entry in policy['spec']['validations']:
                    self.assertNotIn("secretName in [params.data", entry['expression'])


if __name__ == '__main__':
    unittest.main()
