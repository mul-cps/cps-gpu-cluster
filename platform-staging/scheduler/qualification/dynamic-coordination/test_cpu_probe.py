import copy
import json
import unittest
from unittest.mock import patch

import cpu_probe
import live_cpu


class CPUProbeTests(unittest.TestCase):
    def test_live_plan_scope_has_no_gpu_access_or_node_mutation(self):
        items, webhook = live_cpu.bundle(b'reviewed-test-ca')
        self.assertEqual(webhook['webhooks'][0]['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name'], cpu_probe.NAMESPACE)
        self.assertEqual(webhook['webhooks'][0]['matchConditions'][0]['expression'], "request.name in ['kai-cpu-deny', 'unregistered-map']")
        quota = next(item for item in items if item['kind'] == 'ResourceQuota')
        self.assertEqual(quota['spec']['hard']['requests.nvidia.com/gpu'], '0')
        roles = [item for item in items if item['kind'] == 'ClusterRole']
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]['rules'], [{'apiGroups': [''], 'resources': ['nodes'], 'resourceNames': [cpu_probe.NODE], 'verbs': ['get']}])
        for name in cpu_probe.PODS:
            pod = cpu_probe.cpu_pod(name, kai=name.startswith('kai'))
            self.assertFalse(pod['spec']['automountServiceAccountToken'])
            self.assertNotIn('runtimeClassName', pod['spec'])
            self.assertNotIn('volumes', pod['spec'])
            self.assertNotIn('gpu-memory', pod['metadata'].get('annotations', {}))
            for container in pod['spec']['containers']:
                self.assertFalse(any('gpu' in key for key in container['resources']['requests']))
        service = next(item for item in items if item['kind'] == 'Deployment')
        self.assertEqual(service['spec']['template']['spec']['serviceAccountName'], 'generation-fence')
        self.assertEqual(live_cpu.runner()['spec']['backoffLimit'], 0)
    def test_unreviewed_native_name_is_refused_and_seal_has_both_cas_tests(self):
        with self.assertRaises(ValueError): cpu_probe.cpu_pod('production')
        obj = {'metadata': {'uid': 'actual-uid', 'resourceVersion': '42'}}
        self.assertEqual(cpu_probe.seal_patch(obj)[:2], [
            {'op': 'test', 'path': '/metadata/uid', 'value': 'actual-uid'},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '42'}])
        self.assertEqual(cpu_probe.binding({'metadata': {'name': 'native-bind', 'uid': 'u', 'resourceVersion': '2'}})['metadata']['uid'], 'u')


if __name__ == '__main__': unittest.main()
