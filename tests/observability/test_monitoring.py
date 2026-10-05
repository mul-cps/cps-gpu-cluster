"""Validate rendered dashboards and real PromQL absent/stale behavior."""
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[2]
MON=ROOT/'cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring'
PROMTOOL=os.environ.get('CPS_PROMTOOL','/tmp/cps-monitoring-promtool/prometheus-3.5.0.linux-amd64/promtool')

class ComputeMonitoring(unittest.TestCase):
    def dashboards(self):
        return [json.loads(next(iter(yaml.safe_load(p.read_text())['data'].values()))) for p in sorted(MON.glob('cps-*-dashboard.yaml'))]
    def test_dashboards_freshness_and_per_hub_availability(self):
        dashboards=self.dashboards();self.assertEqual(len(dashboards),4)
        for d in dashboards:
            values=[p for p in d['panels'] if p['type']=='timeseries']
            for panel in values:
                self.assertIn('timestamp(',panel['targets'][0]['expr'])
                self.assertEqual(panel['fieldConfig']['defaults']['noValue'],'Unavailable / stale')
                self.assertFalse(panel['fieldConfig']['defaults']['custom']['spanNulls'])
                self.assertNotIn('or vector(0)',panel['targets'][0]['expr'])
                if 'cps_compute_' in panel['targets'][0]['expr']:self.assertIn('Planned telemetry contract',panel['description'])
            status=[p for p in d['panels'] if p['type']=='stat']
            expressions=[p['targets'][0]['expr'] for p in status]
            for ns in ('jupyterhub','cit-jhub'):
                self.assertTrue(any(f'namespace="{ns}"' in expr and 'absent(' in expr and 'min(up{' in expr for expr in expressions))
            self.assertTrue(all(p['targets'][0].get('instant') is True for p in status))
            for i,p in enumerate(d['panels']):
                a=p['gridPos']
                for q in d['panels'][i+1:]:
                    b=q['gridPos']
                    self.assertFalse(a['x']<b['x']+b['w'] and b['x']<a['x']+a['w'] and a['y']<b['y']+b['h'] and b['y']<a['y']+a['h'],'Overlapping panels')
    def test_real_promql_missing_stale_and_duplicate_targets(self):
        rule=yaml.safe_load((MON/'compute-rules.yaml').read_text())['spec']
        cases=yaml.safe_load((ROOT/'tests/observability/promtool-cases.yaml').read_text())
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);(directory/'rules.yaml').write_text(yaml.safe_dump(rule))
            # Evaluate the actual dashboard queries, not a mirrored helper.
            for dashboard in self.dashboards():
                for panel in dashboard['panels']:
                    if panel['type']=='text':continue
                    target=panel['targets'][0]
                    expected=[]
                    if panel['type']=='stat':
                        expr=target['expr']
                        labels='{}'
                        if 'namespace="jupyterhub"' in expr:labels='{namespace="jupyterhub",service="hub"}'
                        elif 'namespace="cit-jhub"' in expr:labels='{namespace="cit-jhub",service="hub"}'
                        elif 'namespace="kai-scheduler"' in expr:labels='{namespace="kai-scheduler",service="kai-scheduler-default"}'
                        expected=[{'labels':labels,'value':1}]
                    cases['tests'].append({'name':panel['title']+' missing is unknown','interval':'30s','input_series':[],
                        'promql_expr_test':[{'expr':target['expr'],'eval_time':'3m','exp_samples':expected}]})
                    selector=re.search(r'\b(?:jupyterhub|DCGM|kai|cps_compute|up)[A-Za-z0-9_]*(?:\{[^}]*\})?',target['expr']).group()
                    selector=selector.replace('namespace=~"jupyterhub|cit-jhub"','namespace="jupyterhub"')
                    stale_expected=[{'labels':'{}','value':1}] if panel['type']=='stat' else []
                    cases['tests'].append({'name':panel['title']+' stale is unavailable','interval':'30s',
                        'input_series':[{'series':selector,'values':'1 _ _ _ _ _ _'}],
                        'promql_expr_test':[{'expr':target['expr'],'eval_time':'3m','exp_samples':stale_expected}]})
            (directory/'cases.yaml').write_text(yaml.safe_dump(cases))
            subprocess.run([PROMTOOL,'check','rules',str(directory/'rules.yaml')],check=True,capture_output=True,text=True)
            result=subprocess.run([PROMTOOL,'test','rules',str(directory/'cases.yaml')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_rendered_alloy_is_local_node_daemonset(self):
        obs=MON.parent
        documents=list(yaml.safe_load_all(subprocess.check_output(['helm','template','alloy','/tmp/cps-platform-charts/alloy-1.10.0.tgz','-n','alloy','-f',str(obs/'alloy/values-alloy.yaml')],text=True)))
        daemonsets=[d for d in documents if d and d['kind']=='DaemonSet']
        self.assertEqual(len(daemonsets),1)
        containers=daemonsets[0]['spec']['template']['spec']['containers']
        alloy=next(c for c in containers if c['name']=='alloy')
        self.assertIn({'operator':'Exists'},daemonsets[0]['spec']['template']['spec']['tolerations'])
        self.assertEqual(alloy['resources']['limits']['memory'],'512Mi')
        self.assertEqual(alloy['resources']['requests'],{'cpu':'100m','memory':'256Mi'})
        env={e['name']:e for e in alloy['env']}
        self.assertEqual(env['HOSTNAME']['valueFrom']['fieldRef']['fieldPath'],'spec.nodeName')
        configs=[v for d in documents if d and d['kind']=='ConfigMap' for v in d.get('data',{}).values() if 'discovery.kubernetes' in v]
        self.assertEqual(len(configs),1)
        self.assertIn('field = "spec.nodeName=" + sys.env("HOSTNAME")',configs[0])

    def test_kai_monitors_have_fixed_inspected_namespaces_ports(self):
        monitors=list(yaml.safe_load_all((MON/'compute-servicemonitors.yaml').read_text()))
        self.assertEqual(len(monitors),2)
        for monitor in monitors:
            spec=monitor['spec'];self.assertEqual(spec['namespaceSelector'],{'matchNames':['kai-scheduler']})
            self.assertIn(spec['endpoints'][0]['port'],('http-metrics','metrics'))
            self.assertEqual(spec['endpoints'][0]['path'],'/metrics')
            self.assertEqual(spec['endpoints'][0]['scrapeTimeout'],'10s')
            self.assertEqual(spec['sampleLimit'],10000)
        # CIT credential deployment remains an explicit separate gate.
        self.assertFalse(any(m['spec']['namespaceSelector']=={'matchNames':['cit-jhub']} for m in monitors))

    def test_workflow_metrics_have_a_scoped_network_boundary(self):
        docs=list(yaml.safe_load_all((MON/'workflow-isolation-metrics.yaml').read_text()))
        argo=next(d for d in docs if d['kind']=='PodMonitor')
        self.assertEqual(argo['spec']['namespaceSelector'],{'matchNames':['cps-argo']})
        self.assertEqual(argo['spec']['podMetricsEndpoints'][0]['port'],'metrics')
        policy=next(d for d in docs if d['kind']=='NetworkPolicy')
        self.assertEqual(policy['spec']['podSelector']['matchLabels'],argo['spec']['selector']['matchLabels'])
        self.assertEqual(len(policy['spec']['ingress']),1)
        rule=policy['spec']['ingress'][0]
        self.assertEqual(rule['ports'],[{'port':9090,'protocol':'TCP'}])
        self.assertEqual(rule['from'],[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'cattle-monitoring-system'}},'podSelector':{'matchLabels':{'app.kubernetes.io/name':'prometheus'}}}])
        isolator=next(d for d in docs if d['kind']=='ServiceMonitor')
        self.assertEqual(isolator['spec']['namespaceSelector'],{'matchNames':['kai-resource-isolator']})
        self.assertEqual(isolator['spec']['selector']['matchLabels']['app.kubernetes.io/component'],'kai-vgpu-monitor')

if __name__=='__main__':unittest.main()
