"""Evaluate the UNION of actual Helm-rendered selecting policies, not values text.

Use the released chart archive: helm pull jupyterhub/jupyterhub --version 4.4.2
--destination ~/.cache/helm. Override JUPYTERHUB_CHART for an offline chart copy.
No API, packet probes, or storage operations are performed by these tests.
"""
import ipaddress
import os
from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2] if Path(__file__).parent.name == 'compute_platform' else Path(__file__).resolve().parents[1]
CPS = (ROOT / 'cluster-maintenance').exists()
VALUES = ROOT / ('cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml' if CPS else 'bundles/20-jupyterhub/values/jupyterhub-values.yaml')
RELEASE, NAMESPACE = ('jupyterhub', 'jupyterhub') if CPS else ('cit-jupyterhub', 'cit-jhub')


def matches(selector, labels):
    if any(labels.get(k) != v for k, v in selector.get('matchLabels', {}).items()):
        return False
    for item in selector.get('matchExpressions', []):
        key, op, values = item['key'], item['operator'], item.get('values', [])
        if op == 'In' and labels.get(key) not in values:
            return False
        if op == 'NotIn' and labels.get(key) in values:
            return False
        if op == 'Exists' and key not in labels:
            return False
        if op == 'DoesNotExist' and key in labels:
            return False
    return True


def allowed(policies, labels, destination, protocol, port, peer_labels=None, peer_namespace=None):
    selected = [p for p in policies if p.get('metadata', {}).get('namespace', NAMESPACE) == NAMESPACE
                and 'Egress' in p['spec'].get('policyTypes', [])
                and matches(p['spec']['podSelector'], labels)]
    if not selected:
        return True
    address = ipaddress.ip_address(destination)
    for policy in selected:
        for rule in policy['spec'].get('egress', []):
            ports = rule.get('ports', [])
            if ports and not any(x.get('protocol', 'TCP') == protocol and isinstance(x.get('port'), int)
                                 and x['port'] <= port <= x.get('endPort', x['port']) for x in ports):
                continue
            peers = rule.get('to', [])
            if not peers:
                return True
            for peer in peers:
                if 'ipBlock' in peer:
                    block = peer['ipBlock']
                    if address in ipaddress.ip_network(block['cidr']) and not any(address in ipaddress.ip_network(x) for x in block.get('except', [])):
                        return True
                elif peer_labels is not None:
                    if 'podSelector' in peer and not matches(peer['podSelector'], peer_labels):
                        continue
                    namespace = peer_namespace or {'kubernetes.io/metadata.name': NAMESPACE}
                    if 'namespaceSelector' in peer:
                        if not matches(peer['namespaceSelector'], namespace):
                            continue
                    elif namespace.get('kubernetes.io/metadata.name') != NAMESPACE:
                        continue
                    return True
    return False


class NotebookNFSEgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chart = Path(os.environ.get('JUPYTERHUB_CHART', Path.home() / '.cache/helm/jupyterhub-4.4.2.tgz'))
        result = subprocess.run(['helm', 'template', RELEASE, str(chart), '--namespace', NAMESPACE,
                                 '-f', str(VALUES)], capture_output=True, text=True, check=True)
        cls.policies = [x for x in yaml.safe_load_all(result.stdout) if x and x['kind'] == 'NetworkPolicy']
        cls.labels = {'app': 'jupyterhub', 'component': 'singleuser-server', 'release': RELEASE,
                      'hub.jupyter.org/network-access-hub': 'true', 'hub.jupyter.org/username': 'student'}

    def test_all_selecting_policy_union_blocks_nfs_rpc_at_public_private_mesh_and_unlisted_aliases(self):
        for ip in ('193.170.30.58', '10.71.1.55', '100.65.233.45', '203.0.113.77', '10.99.1.2', '2001:db8::55'):
            for protocol in ('TCP', 'UDP'):
                for port in (111, 2049):
                    with self.subTest(ip=ip, protocol=protocol, port=port):
                        self.assertFalse(allowed(self.policies, self.labels, ip, protocol, port))

    def test_ordinary_internet_private_services_dns_hub_gateway_are_preserved(self):
        for ip in ('1.1.1.1', '10.43.0.10', '172.16.1.2', '192.168.1.2', '100.65.233.45'):
            for protocol in ('TCP', 'UDP'):
                for port in (22, 53, 80, 110, 112, 443, 8000, 8081, 8888, 2048, 2050, 65535):
                    with self.subTest(ip=ip, protocol=protocol, port=port):
                        expected = CPS or port == 53 or ip not in ('10.43.0.10', '172.16.1.2', '192.168.1.2')
                        self.assertEqual(allowed(self.policies, self.labels, ip, protocol, port), expected)
        for ip, port, component in (('10.42.0.3', 8081, 'hub'), ('10.42.0.4', 8000, 'proxy')):
            self.assertTrue(allowed(self.policies, self.labels, ip, 'TCP', port,
                                    {'app': 'jupyterhub', 'component': component, 'release': RELEASE}))
        # Preserve pre-existing metadata DNS permission without granting metadata HTTP.
        self.assertTrue(allowed(self.policies, self.labels, '169.254.169.254', 'UDP', 53))
        self.assertFalse(allowed(self.policies, self.labels, '169.254.169.254', 'TCP', 80))
        self.assertTrue(allowed(self.policies, self.labels, '1.1.1.1', 'SCTP', 2049))

    def test_only_notebooks_are_changed_not_node_kubelet_mount_traffic(self):
        for labels in ({'component': 'node'}, {'component': 'unrelated'}):
            self.assertTrue(allowed(self.policies, labels, '193.170.30.58', 'TCP', 2049))
        # The chart selectors must cover both default human and neutral named notebook Pods.
        for username, server in (('student', ''), ('neutral-workspace', 'rtc')):
            labels = {**self.labels, 'hub.jupyter.org/username': username, 'hub.jupyter.org/servername': server}
            self.assertFalse(allowed(self.policies, labels, '193.170.30.58', 'TCP', 2049))

    def test_another_selecting_allow_policy_would_reopen_the_port(self):
        # A standalone restrictive policy cannot subtract this additional allow.
        broad = {'kind': 'NetworkPolicy', 'metadata': {'namespace': NAMESPACE}, 'spec': {
            'podSelector': {'matchLabels': {'component': 'singleuser-server'}},
            'policyTypes': ['Egress'], 'egress': [{}]}}
        self.assertTrue(allowed(self.policies + [broad], self.labels, '193.170.30.58', 'TCP', 2049))

    def test_preserves_explicit_ingress_and_uses_supported_numeric_endports(self):
        singleuser = next(p for p in self.policies if p['metadata']['name'] == 'singleuser')
        self.assertTrue(singleuser['spec']['ingress'])
        ranges = [x for r in singleuser['spec']['egress'] for x in r.get('ports', []) if 'endPort' in x]
        self.assertTrue(ranges, 'Actual rendered chart must retain port ranges')
        self.assertTrue(all(type(x['port']) is int and type(x['endPort']) is int
                            and 1 <= x['port'] <= x['endPort'] <= 65535 for x in ranges))


if __name__ == '__main__':
    unittest.main()
