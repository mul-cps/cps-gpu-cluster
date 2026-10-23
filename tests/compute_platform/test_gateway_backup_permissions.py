"""Backup mounts must preserve the live gateway's private lock permissions."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]

class GatewayBackupPermissions(unittest.TestCase):
    def test_backup_skips_recursive_permission_changes_on_owned_volume(self):
        policy = json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        image = 'registry.invalid/compute@sha256:'+'2'*64
        values = {'enabled': True, 'policyJson': json.dumps(policy), 'policyHash': policy['policyHash'],
            'gateway': {'image': image}, 'consoles': {'cps': {'image': image}, 'cit': {'image': image, 'publicCallbackUrl': 'https://cit.example.invalid/services/cit-admin/oauth_callback'}}}
        with tempfile.NamedTemporaryFile('w', suffix='.yaml') as source:
            yaml.safe_dump(values, source); source.flush()
            result = subprocess.run(['helm','template','test',str(ROOT/'platform-staging/chart'),'-f',source.name],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        documents = [d for d in yaml.safe_load_all(result.stdout) if d]
        gateway = next(d for d in documents if d['kind']=='Deployment' and d['metadata']['name']=='compute-gateway')
        self.assertEqual(gateway['spec']['template']['spec']['securityContext'].get('fsGroupChangePolicy'),'OnRootMismatch')
        cron = next(d for d in documents if d and d['kind']=='CronJob'and d['metadata']['name']=='compute-state-backup')
        pod = cron['spec']['jobTemplate']['spec']['template']['spec']
        self.assertEqual(pod['securityContext'].get('fsGroupChangePolicy'),'OnRootMismatch')
        self.assertEqual(pod['securityContext']['fsGroup'],10001)
        self.assertEqual(next(v['persistentVolumeClaim']['claimName'] for v in pod['volumes'] if v['name']=='source'),'compute-state')
