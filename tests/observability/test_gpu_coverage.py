"""Evaluate the actual per-node GPU telemetry alert with promtool."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / 'cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/compute-rules.yaml'
PROMTOOL = os.environ.get('CPS_PROMTOOL', '/tmp/cps-monitoring-promtool/prometheus-3.5.0.linux-amd64/promtool')
SUMMARY = 'GPU telemetry device coverage is below advertised node inventory'
DESCRIPTION = 'Node {{ $labels.node }} advertises {{ $value }} GPU devices but fresh distinct DCGM UUID coverage is lower or missing. This is telemetry coverage, not placement eligibility or physical free GPUs.'


def series(metric, values='1+0x20'):
    return {'series': metric, 'values': values}


def dcgm(node, uuid, instance='a', values='100+0x20'):
    return series(f'DCGM_FI_DEV_FB_FREE{{Hostname="{node}",UUID="{uuid}",instance="{instance}"}}', values)


class GPUCoverage(unittest.TestCase):
    def test_actual_coverage_alert(self):
        inventory = [series('kube_node_status_capacity{resource="nvidia_com_gpu",job="kube-state-metrics",node="node1"}', '2+0x20'),
                     series('kube_node_status_capacity{resource="nvidia_com_gpu",job="kube-state-metrics",node="node2"}'),
                     series('up{job="kube-state-metrics",namespace="cattle-monitoring-system"}')]
        complete = [dcgm('node1', 'gpu1'), dcgm('node1', 'gpu2'), dcgm('node2', 'gpu3')]
        cases = [
            ('missing entire exporter node', inventory + complete[:2], ['node2']),
            ('partial device coverage', inventory + [complete[0], complete[2]], ['node1']),
            ('stale DCGM device', inventory + complete[:2] + [dcgm('node2', 'gpu3', values='100 _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _')], ['node2']),
            ('duplicate UUID scrape is not another device', inventory + complete + [dcgm('node1', 'gpu1', instance='b')], []),
            ('duplicate UUID cannot hide missing device', inventory + [complete[0], dcgm('node1', 'gpu1', instance='b'), complete[2]], ['node1']),
            ('complete coverage', inventory + complete, []),
            ('extra physical UUID beyond advertised inventory is allowed', inventory + complete + [dcgm('node2', 'gpu4')], []),
            ('stale KSM capacity is unknown', [series(x['series'], '2 _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _') for x in inventory[:2]] + inventory[2:] + complete[:2], []),
            ('missing KSM capacity is unknown', inventory[2:] + complete[:2], []),
            ('down KSM is unknown', inventory[:2] + [series(inventory[2]['series'], '0+0x20')] + complete[:2], []),
            ('stale KSM scrape is unknown', inventory[:2] + [series(inventory[2]['series'], '1 _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _')] + complete[:2], []),
        ]
        tests = []
        for name, inputs, nodes in cases:
            tests.append({'name': name, 'interval': '30s', 'input_series': inputs,
                          'alert_rule_test': [{'eval_time': '8m', 'alertname': 'ComputeGPUCollectorCoverageIncomplete',
                                               'exp_alerts': [{'exp_labels': {'node': node, 'severity': 'warning'},
                                                               'exp_annotations': {'summary': SUMMARY, 'description': DESCRIPTION.replace('{{ $labels.node }}', node).replace('{{ $value }}', '2' if node == 'node1' else '1')}} for node in nodes]}]})
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'rules.yaml').write_text(yaml.safe_dump(yaml.safe_load(RULES.read_text())['spec']))
            (directory / 'cases.yaml').write_text(yaml.safe_dump({'rule_files': ['rules.yaml'], 'evaluation_interval': '30s', 'tests': tests}))
            result = subprocess.run([PROMTOOL, 'test', 'rules', str(directory / 'cases.yaml')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
