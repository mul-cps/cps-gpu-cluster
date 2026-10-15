import importlib.util
from pathlib import Path
import unittest

class NasEgressTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[2]/'scripts/compute-platform/restrict-nas-egress.py'
        spec=importlib.util.spec_from_file_location('nas_egress',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def test_additive_public_and_private_rules_all_exclude_the_nas(self):
        m=self.module();policy={'spec':{'egress':[{'to':[{'ipBlock':{'cidr':'0.0.0.0/0','except':['10.0.0.0/8']}}]},{'to':[{'ipBlock':{'cidr':'10.0.0.0/8'}}]}]}}
        r=m.restrict(policy,['193.170.30.58/32','10.71.1.55/32'])
        self.assertIn('193.170.30.58/32',r['spec']['egress'][0]['to'][0]['ipBlock']['except'])
        self.assertIn('10.71.1.55/32',r['spec']['egress'][1]['to'][0]['ipBlock']['except'])
        self.assertNotIn('except',policy['spec']['egress'][1]['to'][0]['ipBlock'])
    def test_unscoped_and_dns_rules_cannot_leave_a_port_exception(self):
        m=self.module();r=m.restrict({'spec':{'egress':[{}, {'ports':[{'port':53,'protocol':'UDP'}]}]}},['193.170.30.58/32'])
        for rule in r['spec']['egress']:self.assertEqual(rule['to'][0]['ipBlock']['except'],['193.170.30.58/32'])
        self.assertEqual(r['spec']['egress'][1]['ports'],[{'port':53,'protocol':'UDP'}])
    def test_peer_selectors_and_unrelated_ranges_survive_idempotently(self):
        m=self.module();policy={'spec':{'egress':[{'to':[{'namespaceSelector':{'matchLabels':{'name':'kube-system'}}}], 'ports':[{'port':53}]},{'to':[{'ipBlock':{'cidr':'172.16.0.0/12'}}]}]}}
        r=m.restrict(policy,['193.170.30.58/32']);self.assertEqual(r['spec']['egress'][0],policy['spec']['egress'][0]);self.assertEqual(r,m.restrict(r,['193.170.30.58/32']))
    def test_existing_deny_all_is_not_broadened(self):
        m=self.module();p={'spec':{'policyTypes':['Egress'],'egress':[]}}
        self.assertEqual(m.restrict(p,['193.170.30.58/32']),p)
    def test_ingress_only_policy_gains_egress_without_changing_ingress(self):
        m=self.module();p={'spec':{'policyTypes':['Ingress'],'ingress':[{'ports':[{'port':8080}]}]}}
        r=m.restrict(p,['193.170.30.58/32']);self.assertEqual(r['spec']['ingress'],p['spec']['ingress']);self.assertIn('Egress',r['spec']['policyTypes']);self.assertEqual(r['spec']['egress'][0]['to'][0]['ipBlock']['except'],['193.170.30.58/32'])
    def test_catalog_covers_relay_nas_destinations_in_public_and_mesh_ranges(self):
        import json,ipaddress,re
        root=Path(__file__).resolve().parents[2]
        targets=json.loads((root/'platform-staging/network/nas-endpoints.json').read_text())['blockedPodDestinations']
        networks=[ipaddress.ip_network(t,strict=True) for t in targets]
        destinations={ipaddress.ip_address(ip) for ip in re.findall(r'^\s*server nas ([0-9.]+):', (root/'platform-staging/relay/haproxy.cfg').read_text(),re.M)}
        self.assertTrue(destinations,'Relay NAS destination inventory must not be empty')
        for destination in destinations:
            self.assertTrue(any(destination in n for n in networks),f'Unexcluded relay NAS destination: {destination}')
        policy={'spec':{'policyTypes':['Egress'],'egress':[{'to':[{'ipBlock':{'cidr':'0.0.0.0/0'}}]},{'to':[{'ipBlock':{'cidr':'100.64.0.0/10'}}]}]}}
        compiled=self.module().restrict(policy,targets)
        for rule in compiled['spec']['egress']:
            block=rule['to'][0]['ipBlock'];cidr=ipaddress.ip_network(block['cidr'])
            for destination in destinations:
                if destination in cidr:
                    self.assertTrue(any(destination in ipaddress.ip_network(n) for n in block.get('except',[])))
