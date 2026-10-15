import json
import unittest
import yaml
from test_staging import Staging, ROOT

class MetricsMonitor(Staging):
    def values(self):
        policy=json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        image='registry.invalid/test@sha256:'+'1'*64
        return {'enabled':True,'policyJson':json.dumps(policy),'policyHash':policy['policyHash'],
                'gateway':{'image':image},'consoles':{'cps':{'image':image},'cit':{'image':image,'publicCallbackUrl':'https://example.invalid/callback'}},
                'metrics':{'enabled':True,'credentials':{'cps':{'name':'metrics','key':'cps'},'cit':{'name':'metrics','key':'cit'}}}}
    def test_authenticated_tls_scrapes_and_scoped_ingress(self):
        result=self.render(self.values());self.assertEqual(result.returncode,0,result.stderr)
        docs=[d for d in yaml.safe_load_all(result.stdout) if d]
        monitors=[d for d in docs if d['kind']=='ServiceMonitor'];self.assertEqual(len(monitors),2)
        for monitor in monitors:
            source=monitor['metadata']['name'].rsplit('-',1)[-1]
            endpoint=monitor['spec']['endpoints'][0]
            self.assertEqual(endpoint['path'],'/internal/v1/metrics')
            self.assertEqual(endpoint['scheme'],'https')
            self.assertEqual(endpoint['authorization']['credentials'],{'name':'metrics','key':source})
            self.assertFalse(endpoint['tlsConfig']['insecureSkipVerify'])
            self.assertEqual(endpoint['tlsConfig']['serverName'],'compute-gateway.cps-compute.svc.cluster.local')
        ingress=next(d for d in docs if d['kind']=='NetworkPolicy' and d['metadata']['name']=='compute-metrics-ingress')['spec']
        self.assertEqual(ingress['podSelector']['matchLabels'],{'app':'compute-gateway'})
        peer=ingress['ingress'][0]['from'][0]
        self.assertEqual(peer['namespaceSelector']['matchLabels'],{'kubernetes.io/metadata.name':'cattle-monitoring-system'})
        self.assertEqual(peer['podSelector']['matchLabels'],{'app.kubernetes.io/name':'prometheus'})
    def test_disabled_emits_no_metrics_resources(self):
        values=self.values();values['metrics']['enabled']=False
        result=self.render(values);self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('kind: ServiceMonitor',result.stdout)
        self.assertNotIn('name: compute-metrics-ingress',result.stdout)
    def test_missing_credential_ref_rejected(self):
        values=self.values();values['metrics']['credentials']['cit']['key']=''
        self.assertNotEqual(self.render(values).returncode,0)
