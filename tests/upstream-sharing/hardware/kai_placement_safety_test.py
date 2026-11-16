"""Offline rejection cases for the bounded placement adapter; no cluster access."""
import copy
import unittest
from urllib.parse import urlsplit, parse_qs
from kai_placement_run import validate_assignment, require_uid, watch_command


class Safety(unittest.TestCase):
    def setUp(self):
        self.pod = {'metadata': {'name': 'run-r0-a-5', 'uid': 'original', 'annotations': {
            'nvidia.com/container.main.gpus.devices': 'k8s.device-plugin.nvidia.com/gpu=GPU-a'}},
            'spec': {'nodeName': 'worker'}}
        self.br = {'metadata': {'ownerReferences': [{'kind': 'Pod', 'uid': 'original'}]},
                   'spec': {'podName': 'run-r0-a-5', 'selectedNode': 'worker',
                            'receivedResourceType': 'Fraction', 'receivedGPU': {'count': 1, 'portion': '0.125'}}}

    def test_accepts_actual_scheduler_binding(self):
        self.assertEqual(validate_assignment(self.pod, self.br, 'worker', ['GPU-a', 'GPU-b'], 'GPU-a'), 'GPU-a')

    def test_rejects_wrong_slot_node_owner_and_extra_device(self):
        for target in ('slot', 'node', 'owner', 'extra'):
            with self.subTest(target=target):
                p, b = copy.deepcopy(self.pod), copy.deepcopy(self.br)
                if target == 'slot': p['metadata']['annotations']['nvidia.com/container.main.gpus.devices'] = 'k8s.device-plugin.nvidia.com/gpu=GPU-b'
                if target == 'node': b['spec']['selectedNode'] = 'other'
                if target == 'owner': b['metadata']['ownerReferences'][0]['uid'] = 'replacement'
                if target == 'extra': p['metadata']['annotations']['nvidia.com/container.main.gpus.devices'] += ',k8s.device-plugin.nvidia.com/gpu=GPU-b'
                with self.assertRaises(RuntimeError): validate_assignment(p, b, 'worker', ['GPU-a', 'GPU-b'], 'GPU-a')

    def test_raw_watch_encodes_namespace_and_resource_version_without_unsupported_flag(self):
        cmd=watch_command('gpu/operator', '123+456&x=1')
        self.assertEqual(cmd[:4], ['kubectl', '--request-timeout=650s', 'get', '--raw'])
        self.assertEqual(len(cmd), 5)
        self.assertNotIn('--resource-version', cmd)
        url=urlsplit(cmd[4])
        self.assertEqual(url.path, '/apis/scheduling.run.ai/v1alpha2/namespaces/gpu%2Foperator/bindrequests')
        self.assertEqual(parse_qs(url.query), {'watch':['true'], 'resourceVersion':['123+456&x=1'],
            'allowWatchBookmarks':['true'], 'timeoutSeconds':['640']})

    def test_cleanup_refuses_same_name_replacement(self):
        with self.assertRaises(RuntimeError): require_uid(self.pod, 'replacement')
        require_uid(self.pod, 'original')


if __name__ == '__main__': unittest.main()
