"""Regression checks against rendered Helm configuration, not values text alone."""
import pathlib
import subprocess
import unittest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
OBS = ROOT / 'cluster-maintenance/clusters/cit-cps-gpu/system/observability'

class MonitoringConfig(unittest.TestCase):
    def test_loki_retention_is_in_effective_config(self):
        docs = list(yaml.safe_load_all(subprocess.check_output([
            'helm', 'template', 'loki', '/tmp/cps-platform-charts/loki-7.0.0.tgz',
            '-n', 'loki', '-f', str(OBS / 'loki/values-loki.yaml')], text=True)))
        configs = [d for d in docs if d and d['kind'] in ('Secret', 'ConfigMap') and
                   any('config.yaml' in k for k in d.get('data', {}))]
        import base64
        configs = [yaml.safe_load(base64.b64decode(v) if d['kind']=='Secret' else v)
                   for d in configs for k,v in d['data'].items() if k == 'config.yaml']
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config['limits_config'].get('retention_period'), '336h')
        self.assertTrue(config['compactor']['retention_enabled'])
        self.assertEqual(config['compactor']['delete_request_store'], 'filesystem')
        stateful=next(d for d in docs if d and d['kind']=='StatefulSet' and d['metadata']['name']=='loki')
        self.assertEqual(stateful['spec']['persistentVolumeClaimRetentionPolicy'],{'whenDeleted':'Retain','whenScaled':'Retain'})

    def test_alloy_discovers_only_local_node(self):
        values = yaml.safe_load((OBS / 'alloy/values-alloy.yaml').read_text())
        config = values['alloy']['configMap']['content']
        self.assertIn('field = "spec.nodeName=" + sys.env("HOSTNAME")', config)
        envs = {e['name']: e for e in values['alloy']['extraEnv']}
        self.assertEqual(envs['HOSTNAME']['valueFrom']['fieldRef']['fieldPath'], 'spec.nodeName')

if __name__ == '__main__':
    unittest.main()
