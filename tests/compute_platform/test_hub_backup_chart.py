from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / 'platform-staging/hub-backups/chart'


class HubBackupChart(unittest.TestCase):
    def render(self, owner, override=None):
        values = yaml.safe_load((CHART.parent / (owner + '-values.yaml')).read_text())
        values.update(override or {})
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as f:
            yaml.safe_dump(values, f); f.flush()
            return subprocess.run(['helm', 'template', 'test', str(CHART), '-f', f.name],
                                  capture_output=True, text=True)

    def test_both_jobs_are_suspended_scoped_and_use_existing_secrets(self):
        for owner in ['cps', 'cit']:
            with self.subTest(owner=owner):
                result = self.render(owner, {"suspend": True})
                self.assertEqual(result.returncode, 0, result.stderr)
                resources = list(yaml.safe_load_all(result.stdout))
                cron = next(r for r in resources if r['kind'] == 'CronJob')
                self.assertTrue(cron['spec']['suspend'])
                self.assertEqual(cron['spec']['concurrencyPolicy'], 'Forbid')
                pod = cron['spec']['jobTemplate']['spec']['template']['spec']
                self.assertFalse(pod['automountServiceAccountToken'])
                c = pod['containers'][0]
                self.assertIn('@sha256:', c['image'])
                self.assertTrue(c['securityContext']['readOnlyRootFilesystem'])
                self.assertFalse(c['securityContext']['allowPrivilegeEscalation'])
                password = next(e for e in c['env'] if e['name'] == 'PGPASSWORD')
                self.assertNotIn('value', password)
                self.assertIn('secretKeyRef', password['valueFrom'])
                self.assertFalse(any(r['kind'] in ['Secret','Role','ClusterRole'] for r in resources))
                policy = next(r for r in resources if r['kind'] == 'NetworkPolicy')
                self.assertEqual(policy['spec']['ingress'], [])
                self.assertEqual({p['port'] for rule in policy['spec']['egress'] for p in rule['ports']}, {53,5432})

    def test_mutable_images_and_unknown_owner_are_rejected(self):
        for override in [{'image': 'postgres:15'}, {'owner': 'unknown'}, {'databasePodLabels': {}}]:
            self.assertNotEqual(self.render('cps', override).returncode, 0)

    def test_default_chart_is_disabled(self):
        result = subprocess.run(['helm','template','test',str(CHART)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.stdout.strip())

    def test_shell_syntax(self):
        subprocess.run(['sh','-n',str(CHART/'files/backup.sh')],check=True)
