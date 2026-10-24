"""Effective additive egress of the deployed workload bundle and compute chart."""
import copy
import ipaddress
import json
import pathlib
import subprocess
import unittest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def selects(selector, labels):
    if any(labels.get(k) != v for k, v in selector.get('matchLabels', {}).items()):
        return False
    for item in selector.get('matchExpressions', []):
        key, op, values = item['key'], item['operator'], item.get('values', [])
        if op == 'In' and labels.get(key) not in values: return False
        if op == 'NotIn' and labels.get(key) in values: return False
        if op == 'Exists' and key not in labels: return False
        if op == 'DoesNotExist' and key in labels: return False
        if op not in ('In', 'NotIn', 'Exists', 'DoesNotExist'): raise AssertionError(op)
    return True


def allowed(policies, namespace, labels, address, port, protocol):
    selected = [p for p in policies if p['metadata']['namespace'] == namespace
                and selects(p['spec']['podSelector'], labels)
                and 'Egress' in p['spec'].get('policyTypes', ['Ingress'] +
                    (['Egress'] if 'egress' in p['spec'] else []))]
    if not selected:
        return True
    for policy in selected:
        for rule in policy['spec'].get('egress', []):
            def peer_matches(peer):
                # These probes address external IPs, not Kubernetes destination Pods.
                if 'ipBlock' not in peer: return not peer
                block = peer['ipBlock']
                ip = ipaddress.ip_address(address)
                return ip in ipaddress.ip_network(block['cidr']) and not any(
                    ip in ipaddress.ip_network(n) for n in block.get('except', []))
            peers = rule.get('to')
            if peers and not any(peer_matches(p) for p in peers): continue
            ports = rule.get('ports')
            if not ports: return True
            for item in ports:
                if item.get('protocol', 'TCP') != protocol: continue
                if 'port' not in item: return True
                if isinstance(item['port'], str): raise AssertionError('named port unsupported for external probe')
                if item['port'] <= port <= item.get('endPort', item['port']): return True
    return False


class WorkflowEgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        objects = list(yaml.safe_load_all((ROOT/'platform-staging/workload-rbac.yaml').read_text()))
        policy = json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        image = 'registry.invalid/test@sha256:' + '1'*64
        values = {'enabled': True, 'policyJson': json.dumps(policy), 'policyHash': policy['policyHash'],
                  'gateway': {'image': image, 'kubernetes': {'enabled': True}},
                  'consoles': {'cps': {'image': image}, 'cit': {'image': image, 'publicCallbackUrl': 'https://example.invalid/callback'}}}
        rendered = subprocess.run(['helm', 'template', 'compute', str(ROOT/'platform-staging/chart'), '-f', '-'],
                                  input=yaml.safe_dump(values), text=True, capture_output=True, check=True)
        objects += list(yaml.safe_load_all(rendered.stdout))
        objects += list(yaml.safe_load_all((ROOT/'platform-staging/argo/network-policy.yaml').read_text()))
        cls.policies = [o for o in objects if o and o['kind'] == 'NetworkPolicy']

    def test_standard_rpc_nfs_denied_for_current_and_future_workflow_pods(self):
        for labels in ({}, {'workflows.argoproj.io/workflow': 'example'}, {'future': 'user-pod'}):
            for address in ('193.170.30.58', '10.21.0.44', '2001:db8::58'):
                for protocol in ('TCP', 'UDP'):
                    for port in (111, 2049):
                        with self.subTest(labels=labels, address=address, protocol=protocol, port=port):
                            self.assertFalse(allowed(self.policies, 'cps-workflows', labels, address, port, protocol))

    def test_normal_ports_preserved_including_range_boundaries(self):
        for address in ('193.170.30.58', '10.21.0.44', '1.1.1.1', '2001:db8::58'):
            for protocol in ('TCP', 'UDP'):
                for port in (1, 53, 80, 110, 112, 443, 2048, 2050, 8000, 8333, 29500, 65535):
                    with self.subTest(address=address, protocol=protocol, port=port):
                        self.assertTrue(allowed(self.policies, 'cps-workflows', {}, address, port, protocol))

    def test_policy_scope_and_additive_broad_allow_detection(self):
        restricted = [p for p in self.policies if p['metadata']['namespace'] == 'cps-workflows'
                      and 'Egress' in p['spec'].get('policyTypes', [])]
        self.assertEqual(len(restricted), 1)
        self.assertEqual(restricted[0]['spec']['podSelector'], {})
        for namespace in ('cps-argo', 'jupyterhub', 'cit-jhub', 'kube-system'):
            self.assertTrue(allowed(restricted, namespace, {}, '193.170.30.58', 2049, 'TCP'))
        broad = copy.deepcopy(restricted[0])
        for rule in ({}, {'to': [], 'ports': []}, {'ports': [{'protocol': 'TCP'}]},
                     {'ports': [{'protocol': 'UDP', 'port': 1, 'endPort': 65535}]}):
            broad['spec']['egress'] = [rule]
            protocol = rule.get('ports', [{}])[0].get('protocol', 'TCP') if rule.get('ports') else 'TCP'
            self.assertTrue(allowed(self.policies + [broad], 'cps-workflows', {}, '193.170.30.58', 2049, protocol))


if __name__ == '__main__': unittest.main()
