import unittest

import incluster_probe


class InClusterProbeTests(unittest.TestCase):
    def test_request_routes_are_limited_to_qualification_namespace(self):
        for kind, resource in [('Pod', 'pods'), ('ConfigMap', 'configmaps'), ('Binding', 'pods/fixture/binding')]:
            obj = {'kind': kind, 'metadata': {'name': 'fixture', 'namespace': incluster_probe.NAMESPACE}}
            self.assertEqual(incluster_probe.request_path(obj),
                '/api/v1/namespaces/' + incluster_probe.NAMESPACE + '/' + resource)
            obj['metadata']['namespace'] = 'production'
            with self.assertRaises(ValueError):
                incluster_probe.request_path(obj)

    def test_unsupported_kind_and_binding_path_traversal_denied(self):
        for kind, name in [('Deployment', 'fixture'), ('Binding', '../production')]:
            with self.assertRaises(ValueError):
                incluster_probe.request_path({'kind': kind,
                    'metadata': {'name': name, 'namespace': incluster_probe.NAMESPACE}})


if __name__ == '__main__':
    unittest.main()
