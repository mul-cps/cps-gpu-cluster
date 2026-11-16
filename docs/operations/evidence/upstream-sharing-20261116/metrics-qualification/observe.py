#!/usr/bin/env python3
"""Read-only, bounded stock-exporter/Prometheus capture during GPU2 KAI holds."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.parse

PROM='/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-prometheus:9090/proxy/api/v1/'
METRICS_POD='gpu-fractioning-fractiond-sdf6w'
METRICS_UID='c9cf5712-6c7a-4d74-a6e0-09e47c05d265'

def run(args):return subprocess.check_output(['kubectl',*args],text=True,timeout=20)
def api(path):return json.loads(run(['get','--raw',PROM+path]))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=480)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();assert 1<=a.seconds<=900
    a.output.mkdir(parents=True,exist_ok=False)
    started=time.time();iterations=0;errors=0;observed=set();metric_names=set()
    while time.time()-started<a.seconds:
        stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            exporter=json.loads(run(['get','pod',METRICS_POD,'-n','gpu-fractioning','-o','json']))
            assert exporter['metadata']['uid']==METRICS_UID
            assert exporter['spec']['nodeName']=='k3s-wk-gpu2'
            body=json.loads(run(['get','pods','-A','-l','cps.unileoben.ac.at/kai-placement-run','-o','json']))
            pods=[]
            for p in body['items']:
                if p['spec'].get('nodeName') not in [None,'k3s-wk-gpu2']:continue
                observed.add(p['metadata']['uid'])
                pods.append({'namespace':p['metadata']['namespace'],'name':p['metadata']['name'],
                    'uid':p['metadata']['uid'],'labels':p['metadata'].get('labels'),
                    'annotations':p['metadata'].get('annotations'),'node':p['spec'].get('nodeName'),
                    'scheduler':p['spec'].get('schedulerName'),'phase':p['status'].get('phase'),
                    'containers':p['status'].get('containerStatuses',[])})
            raw=run(['get','--raw','/api/v1/namespaces/gpu-fractioning/pods/'+METRICS_POD+':2112/proxy/metrics'])
            for line in raw.splitlines():
                if line and not line.startswith('#'):metric_names.add(line.split('{')[0].split()[0])
            query=api('query?'+urllib.parse.urlencode({'query':'{job="gpu-fractioning/gpu-fractioning-metricsd"}'}))
            targets=api('targets?state=active')
            fractioning_targets=[t for t in targets['data']['activeTargets'] if 'gpu-fractioning' in t.get('scrapePool','')]
            row={'time':stamp,'exporter_uid':METRICS_UID,'pods':pods,'raw_metrics':raw,
                 'prometheus':query,'targets':fractioning_targets}
            with (a.output/'observations.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
            iterations+=1
        except Exception as exc:
            errors+=1
            with (a.output/'errors.jsonl').open('a') as stream:stream.write(json.dumps({'time':stamp,'error':repr(exc)})+'\n')
            if errors>=3:break
        time.sleep(min(5,max(0,a.seconds-(time.time()-started))))
    (a.output/'capture-summary.json').write_text(json.dumps({'iterations':iterations,'errors':errors,
        'pod_uids_observed':sorted(observed),'metric_names':sorted(metric_names),
        'started_at':started,'ended_at':time.time(),'read_only':True},indent=2)+'\n')

if __name__=='__main__':main()
