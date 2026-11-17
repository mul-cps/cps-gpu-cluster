"""Offline rejection cases for the bounded placement adapter; no cluster access."""
import copy
from contextlib import redirect_stderr
import io
import unittest
from urllib.parse import urlsplit, parse_qs
import kai_placement_render as renderer
import kai_placement_run as runner
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


class AcceptedPeers(unittest.TestCase):
    def setUp(self):
        self.selected = 'k3s-wk-gpu3'
        self.selected_uid = '33333333-3333-4333-8333-333333333333'
        self.peer = 'k3s-wk-gpu2'
        self.peer_uid = '22222222-2222-4222-8222-222222222222'
        self.args = ['--node', self.selected, '--operator-selected-worker', self.selected,
                     '--node-ip', '192.0.2.3', '--gpu-a', 'GPU-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
                     '--gpu-b', 'GPU-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
                     '--expected-boot-id', '44444444-4444-4444-8444-444444444444',
                     '--expected-module-srcversion', '10301D70B8ED1758BC717E9',
                     '--output', '/unused-offline-render', '--run-id', 'kai-peer-offline']

    def node(self, name, uid, ready='True'):
        return {'metadata': {'name': name, 'uid': uid, 'labels': {
                    'cps.unileoben.ac.at/upstream-gpu-sharing': 'qualified'}},
                'status': {'conditions': [{'type': 'Ready', 'status': ready}]}}

    def test_peer_cli_records_identity_without_widening_any_fixture_selector(self):
        try:
            with redirect_stderr(io.StringIO()):
                a = renderer.arguments(self.args + ['--accepted-qualified-peer', self.peer+'='+self.peer_uid])
        except SystemExit:
            self.fail('Explicit accepted peer identity must be accepted by the offline CLI')
        self.assertEqual(a.accepted_qualified_peers, {self.peer: self.peer_uid})
        _, pods, summary = renderer.render(a)
        self.assertEqual(summary['accepted_qualified_peers'], {self.peer: self.peer_uid})
        self.assertEqual(len(pods), 15)
        for pod in pods.values():
            self.assertEqual(pod['spec']['nodeSelector'], {
                'kubernetes.io/hostname': self.selected,
                'cps.unileoben.ac.at/upstream-gpu-sharing': 'qualified'})
            self.assertNotIn('nodeName', pod['spec'])

    def test_empty_default_retains_single_qualified_worker_guard(self):
        a = renderer.arguments(self.args)
        self.assertEqual(a.accepted_qualified_peers, {})
        selected = self.node(self.selected, self.selected_uid)
        runner.validate_qualified_nodes([selected], self.selected, self.selected_uid, {})
        with self.assertRaises(RuntimeError):
            runner.validate_qualified_nodes([selected, self.node(self.peer, self.peer_uid)],
                                            self.selected, self.selected_uid, {})

    def test_accepts_only_exact_ready_identity_matched_peer_set_independent_of_list_order(self):
        nodes = [self.node(self.peer, self.peer_uid), self.node(self.selected, self.selected_uid)]
        self.assertEqual(runner.validate_qualified_nodes(nodes, self.selected, self.selected_uid,
                         {self.peer: self.peer_uid}), [
                             {'name': self.peer, 'uid': self.peer_uid, 'ready': True},
                             {'name': self.selected, 'uid': self.selected_uid, 'ready': True}])

    def test_rejects_ready_peer_being_deleted(self):
        peer = self.node(self.peer, self.peer_uid)
        peer['metadata']['deletionTimestamp'] = '2026-11-17T00:00:00Z'
        with self.assertRaises(RuntimeError):
            runner.validate_qualified_nodes([self.node(self.selected, self.selected_uid), peer],
                                            self.selected, self.selected_uid, {self.peer: self.peer_uid})

    def test_rejects_unexpected_missing_replaced_unready_and_unqualified_inventory(self):
        for change in ('unexpected', 'missing-peer', 'missing-selected', 'peer-uid', 'selected-uid',
                       'false', 'unknown', 'no-ready', 'unqualified', 'duplicate'):
            with self.subTest(change=change):
                nodes = [self.node(self.selected, self.selected_uid), self.node(self.peer, self.peer_uid)]
                if change == 'unexpected': nodes.append(self.node('k3s-wk-gpu4', 'other'))
                if change == 'missing-peer': nodes.pop()
                if change == 'missing-selected': nodes.pop(0)
                if change == 'peer-uid': nodes[1]['metadata']['uid'] = 'replacement'
                if change == 'selected-uid': nodes[0]['metadata']['uid'] = 'replacement'
                if change == 'false': nodes[1]['status']['conditions'][0]['status'] = 'False'
                if change == 'unknown': nodes[1]['status']['conditions'][0]['status'] = 'Unknown'
                if change == 'no-ready': nodes[1]['status']['conditions'] = []
                if change == 'unqualified': nodes[1]['metadata']['labels'] = {}
                if change == 'duplicate': nodes.append(copy.deepcopy(nodes[1]))
                with self.assertRaises(RuntimeError):
                    runner.validate_qualified_nodes(nodes, self.selected, self.selected_uid,
                                                    {self.peer: self.peer_uid})

    def test_peer_cli_rejects_selected_duplicate_malformed_and_unknown_worker_entries(self):
        entries = [[self.selected+'='+self.selected_uid], [self.peer+'=not-a-uid'],
                   [self.peer], ['k3s-wk-gpu9='+self.peer_uid],
                   [self.peer+'='+self.peer_uid, self.peer+'='+self.peer_uid]]
        for values in entries:
            with self.subTest(values=values), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                renderer.arguments(self.args + [part for value in values
                                                for part in ['--accepted-qualified-peer', value]])


if __name__ == '__main__': unittest.main()
