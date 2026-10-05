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
        hub_access=[d for d in docs if d['kind']=='NetworkPolicy' and d['metadata']['name']=='cps-compute-hub-api']
        self.assertEqual({d['metadata']['namespace'] for d in hub_access},{'jupyterhub','cit-jhub'})
        for rule in hub_access:
            ingress=rule['spec']['ingress'][0]
            self.assertEqual(ingress['ports'],[{'protocol':'TCP','port':8081}])
            peer=ingress['from'][0]
            self.assertEqual(peer['namespaceSelector']['matchLabels'],{'kubernetes.io/metadata.name':'cps-compute'})
            source='cps' if rule['metadata']['namespace']=='jupyterhub' else 'cit'
            self.assertEqual(peer['podSelector']['matchExpressions'][0]['values'],['compute-gateway',source+'-admin'])
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
                self.assertIn({'name':'JUPYTERHUB_CLIENT_ID','value':'service-'+name},env)
                self.assertIn({'name':'JUPYTERHUB_SERVICE_NAME','value':name},env)
                self.assertFalse(any(item['name']=='JUPYTERHUB_OAUTH_CLIENT_ID' for item in env))
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
                self.assertEqual(pod['containers'][0]['command'],['python','/scripts/backup-console.py'])
                env={item['name']:item['value'] for item in pod['containers'][0]['env']}
                self.assertEqual(env['BACKUP_POLICY_HASH'],policy['policyHash'])
                self.assertEqual(env['BACKUP_IMAGE'],image)
                self.assertIn(env['BACKUP_OWNER'],('cps','cit'))
                self.assertTrue(next(v for v in pod['containers'][0]['volumeMounts'] if v['name']=='source')['readOnly'])
    def test_controller_credentials_and_permissions_are_explicit(self):
        policy=json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        image='registry.invalid/test@sha256:'+'1'*64
        result=self.render({'enabled':True,'policyJson':json.dumps(policy),'policyHash':policy['policyHash'],
                            'gateway':{'image':image,'kubernetes':{'enabled':True},'storageBridgeSecretRef':'restricted-nas-key'},
                            'consoles':{'cps':{'image':image},'cit':{'image':image,'publicCallbackUrl':'https://example.invalid/callback'}}})
        self.assertEqual(result.returncode,0,result.stderr)
        docs=[d for d in yaml.safe_load_all(result.stdout) if d]
        gateway=next(d for d in docs if d['kind']=='Deployment' and d['metadata']['name']=='compute-gateway')['spec']['template']['spec']
        self.assertEqual(gateway['serviceAccountName'],'cps-compute-controller')
        self.assertFalse(gateway['automountServiceAccountToken'])
        self.assertEqual(gateway['securityContext']['runAsUser'],10001)
        self.assertTrue(any('projected' in v for v in gateway['volumes']))
        cluster_role=next(d for d in docs if d['kind']=='ClusterRole')
        for rule in cluster_role['rules']:
            self.assertNotIn('secrets',rule['resources'])
            self.assertNotIn('delete',rule['verbs'])
        policies=[d for d in docs if d['kind']=='ValidatingAdmissionPolicy']
        self.assertEqual(len(policies),3)
        for deployment in [d for d in docs if d['kind']=='Deployment' and d['metadata']['name']!='compute-gateway']:
            pod=deployment['spec']['template']['spec']
            self.assertFalse(any('projected' in v for v in pod['volumes']))
            self.assertFalse(any(v.get('secret',{}).get('secretName')=='restricted-nas-key' for v in pod['volumes']))
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
