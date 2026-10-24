"""Render exact chart 4.4.2 and test additive destination/port semantics.
Run: JUPYTERHUB_CHART=/path/jupyterhub-4.4.2.tgz python3 -m unittest discover -s tests -p test_notebook_nfs_egress.py
"""
import hashlib, ipaddress, os, subprocess, unittest
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
VALUES = ROOT / "cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml"
PRIVATE = True
def allowed(rules, address, port, protocol):
    for rule in rules:
        peers = rule.get("to") or [{}]
        dest = any(not peer or ("ipBlock" in peer and ipaddress.ip_address(address) in ipaddress.ip_network(peer["ipBlock"]["cidr"]) and not any(ipaddress.ip_address(address) in ipaddress.ip_network(x) for x in peer["ipBlock"].get("except", []))) for peer in peers)
        ports = rule.get("ports")
        if dest and (not ports or any(p.get("protocol", "TCP") == protocol and isinstance(p["port"], int) and p["port"] <= port <= p.get("endPort", p["port"]) for p in ports)):
            return True
    return False

class NotebookEgress(unittest.TestCase):
    def test_broad_allow_mutations_reopen_nfs(self):
        # NetworkPolicy rules union: any broad grant defeats a restrictive rule.
        restrictive = {"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}],
                       "ports": [{"port": 443}]}
        for mutation in [{}, {"to": [], "ports": []}, {"to": []}, {"ports": []},
                         {"ports": [{"port": 111}, {"port": 2049}]},
                         {"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}], "ports": []}]:
            for port in [111, 2049]:
                self.assertFalse(allowed([restrictive], "193.170.30.58", port, "TCP"))
                self.assertTrue(allowed([restrictive, mutation], "193.170.30.58", port, "TCP"))

    def test_rendered_destinations_and_ports(self):
        chart = os.environ["JUPYTERHUB_CHART"]
        self.assertEqual(hashlib.sha256(Path(chart).read_bytes()).hexdigest(),
                         "0ddfa517050d16f2e1b50c62b5b6377b12574f9a2b88f3b352bd211ef3173c3e")
        metadata = yaml.safe_load(subprocess.check_output(["helm", "show", "chart", chart]))
        self.assertEqual(metadata["version"], "4.4.2")
        docs = yaml.safe_load_all(subprocess.check_output(["helm", "template", "audit", chart, "-f", str(VALUES)]))
        policy = next(d for d in docs if d and d.get("kind") == "NetworkPolicy" and d["metadata"]["name"] == "singleuser")
        rules = policy["spec"]["egress"]
        for protocol in ["TCP", "UDP"]:
            for address in ["193.170.30.58", "10.71.1.55", "10.21.0.44", "8.8.8.8"]:
                for port in [111, 2049]:
                    self.assertFalse(allowed(rules, address, port, protocol), (address, port, protocol))
            for port in [1, 110, 112, 2048, 2050, 65535]:
                self.assertTrue(allowed(rules, "8.8.8.8", port, protocol))
            for address in ["10.71.1.55", "172.16.0.1", "192.168.1.1"]:
                self.assertEqual(allowed(rules, address, 9000, protocol), PRIVATE)
            self.assertFalse(allowed(rules, "169.254.169.254", 9000, protocol))
        self.assertTrue(allowed(rules, "193.170.30.58", 9000, "TCP"))
        self.assertTrue(allowed(rules, "8.8.8.8", 443, "TCP"))
        self.assertTrue(allowed(rules, "10.42.0.10", 53, "UDP"))
if __name__ == "__main__": unittest.main()
