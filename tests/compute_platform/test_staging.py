import json
import pathlib
import subprocess
import tempfile
import unittest
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]
class Staging(unittest.TestCase):
    def render(self,extra):
        with tempfile.NamedTemporaryFile('w',suffix='.yaml') as file:
            yaml.safe_dump(extra,file);file.flush()
            return subprocess.run(['helm','template','compute',str(ROOT/'platform-staging/chart'),'-f',file.name],text=True,capture_output=True)
    def test_disabled_has_no_workloads(self):
        result=self.render({})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(list(yaml.safe_load_all(result.stdout)),[])
    def test_enabling_without_released_artifacts_fails(self):
        result=self.render({'enabled':True})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('compiled shared catalog',result.stderr)
    def test_separate_consoles_single_global_store_and_backups(self):
        policy=json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        image='registry.invalid/test@sha256:'+'1'*64 # schema fixture only, never a qualification artifact
        result=self.render({'enabled':True,'policyJson':json.dumps(policy),'policyHash':policy['policyHash'],
                            'gateway':{'image':image},'consoles':{'cps':{'image':image},'cit':{'image':image,'publicCallbackUrl':'https://example.invalid/cit/callback'}}})
        self.assertEqual(result.returncode,0,result.stderr)
        docs=[d for d in yaml.safe_load_all(result.stdout) if d]
        deployments={d['metadata']['name']:d for d in docs if d['kind']=='Deployment'}
        self.assertEqual(set(deployments),{'cps-admin','cit-admin','compute-gateway'})
        claims=[]
        for name,deployment in deployments.items():
            self.assertEqual(deployment['spec']['replicas'],1)
            self.assertEqual(deployment['spec']['strategy']['type'],'Recreate')
            pod=deployment['spec']['template']['spec']
            self.assertFalse(pod['automountServiceAccountToken'])
            self.assertTrue(pod['securityContext']['runAsNonRoot'])
            claims += [v['persistentVolumeClaim']['claimName'] for v in pod['volumes'] if 'persistentVolumeClaim' in v]
            if name != 'compute-gateway':
                env = pod['containers'][0]['env']
                self.assertIn({'name':'SSL_CERT_FILE','value':'/trust/ca.crt'},env)
        config = next(d for d in docs if d['kind']=='ConfigMap' and d['metadata']['name']=='cps-admin-config')
        self.assertIn('https://compute-gateway.cps-compute.svc.cluster.local:8000',config['data']['config.py'])
        gateway = deployments['compute-gateway']['spec']['template']['spec']['containers'][0]
        self.assertIn('--ssl-certfile',gateway['command'])
        self.assertEqual(len(claims),len(set(claims)))
        backups=[d for d in docs if d['kind']=='CronJob']
        self.assertEqual({d['metadata']['name'] for d in backups},{'cps-admin-backup','cit-admin-backup','compute-state-backup'})
        for backup in backups:
            self.assertEqual(backup['spec']['concurrencyPolicy'],'Forbid')
            pod=backup['spec']['jobTemplate']['spec']['template']['spec']
            self.assertIn('podAffinity',pod['affinity'])
            if backup['metadata']['name'] != 'compute-state-backup':
                self.assertIn('source.backup(target)',pod['containers'][0]['args'][0])
                self.assertIn('mode=ro',pod['containers'][0]['args'][0])
    def test_mismatched_policy_cannot_render(self):
        policy=json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        result=self.render({'enabled':True,'policyJson':json.dumps(policy),'policyHash':'sha256:'+'0'*64})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('differs',result.stderr)
    def test_plaintext_gateway_rejected(self):
        policy=json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        result=self.render({'enabled':True,'policyJson':json.dumps(policy),'policyHash':policy['policyHash'],
                            'gateway':{'url':'http://compute-gateway:8000'}})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('HTTPS',result.stderr)
if __name__=='__main__':unittest.main()
