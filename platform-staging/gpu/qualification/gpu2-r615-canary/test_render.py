import copy
import unittest

import render


class RenderSafetyTest(unittest.TestCase):
    def setUp(self):
        self.current = {'kind': 'DaemonSet', 'metadata': {
            'name': 'nvidia-driver-daemonset', 'uid': 'source-uid',
            'resourceVersion': 'original-rv', 'ownerReferences': [{'uid': 'operator'}]},
            'spec': {'updateStrategy': {'type': 'OnDelete'},
                     'selector': {'matchLabels': {'app': 'old-driver'}},
                     'template': {'metadata': {'labels': {'app': 'old-driver'}},
                                  'spec': {'nodeSelector': {'nvidia.com/gpu.deploy.driver': 'true'},
                                           'containers': [{'name': 'nvidia-driver-ctr', 'image': 'old',
                                                           'volumeMounts': [{'name': 'nv-firmware', 'mountPath': '/lib/firmware'}]}],
                                           'initContainers': [{'name': 'k8s-driver-manager', 'image': 'manager'},
                                                              {'name': 'other-prerequisite', 'image': 'other'}],
                                           'volumes': [{'name': 'host-driver-root'},
                                                       {'name': 'nv-firmware', 'hostPath': {'path': '/run/nvidia/driver/lib/firmware', 'type': 'DirectoryOrCreate'}},
                                                       {'name': 'firmware-search-path', 'hostPath': {'path': '/sys/module/firmware_class/parameters/path'}}]}}}}
        self.node = {'metadata': {'uid': 'gpu2-uid'}}
        self.expected = {'sourceDaemonSetUID': 'source-uid',
                         'sourceDaemonSetSpecSHA256': render.spec_digest(self.current),
                         'gpu2': {'uid': 'gpu2-uid'}}

    def test_resource_version_and_status_only_updates_are_allowed(self):
        self.current['metadata']['resourceVersion'] = 'new-rv'
        self.current['status'] = {'numberReady': 3}
        render.verify_source(self.current, self.expected, self.node)

    def test_source_spec_change_is_rejected(self):
        self.current['spec']['template']['spec']['containers'][0]['image'] = 'unreviewed'
        with self.assertRaises(AssertionError):
            render.verify_source(self.current, self.expected, self.node)

    def test_replaced_source_or_node_is_rejected(self):
        for obj in (self.current, self.node):
            old = obj['metadata']['uid']
            obj['metadata']['uid'] = 'replaced'
            with self.assertRaises(AssertionError):
                render.verify_source(self.current, self.expected, self.node)
            obj['metadata']['uid'] = old

    def test_only_gpu2_no_manager_or_owner_adoption_source_unchanged(self):
        before = copy.deepcopy(self.current)
        result = render.candidate(self.current)
        pod = result['spec']['template']['spec']
        self.assertEqual(pod['nodeSelector'], {'kubernetes.io/hostname': render.NODE})
        self.assertNotIn('ownerReferences', result['metadata'])
        self.assertEqual(result['spec']['selector']['matchLabels'], {'app': render.NAME})
        self.assertEqual([c['name'] for c in pod['initContainers']], ['other-prerequisite', 'gpu2-firmware-search-path'])
        self.assertEqual(pod['containers'][0]['image'], render.IMAGE)
        self.assertEqual(pod['volumes'][0], before['spec']['template']['spec']['volumes'][0])
        self.assertEqual(pod['volumes'][1]['hostPath'], {'path': render.FIRMWARE, 'type': 'DirectoryOrCreate'})
        self.assertFalse(render.FIRMWARE.startswith('/run/nvidia/driver/'))
        self.assertEqual(pod['initContainers'][-1]['volumeMounts'],
                         [{'name': 'firmware-search-path', 'mountPath': '/sys/module/firmware_class/parameters/path'}])
        self.assertEqual(pod['initContainers'][-1]['image'], render.IMAGE)
        self.assertNotIn('kubectl', pod['initContainers'][-1]['args'][0])
        self.assertEqual(self.current, before)

    def test_unexpected_source_firmware_mount_is_rejected(self):
        self.current['spec']['template']['spec']['volumes'][1]['hostPath']['path'] = '/unexpected'
        with self.assertRaises(AssertionError):
            render.candidate(self.current)


if __name__ == '__main__':
    unittest.main()
