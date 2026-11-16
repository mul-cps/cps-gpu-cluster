#!/usr/bin/env python3
"""Read-only bounded current Source QA Pod/Prometheus attribution capture."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.parse

PROM='/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-prometheus:9090/proxy/api/v1/'
EXPORTER='gpu-fractioning-fractiond-p57lq'
EXPORTER_UID='9e2e3161-2b79-43d9-89cd-f959e107abc1'
OWNERS=('cps-ws-2114b8e3a15e8913cb98083bd5673e45','cit-ws-4f8bebfab68c2dc3f8cea6df357d874c')

def run(args):
    return subprocess.check_output(['kubectl','--request-timeout=8s',*args],text=True,stderr=subprocess.PIPE,timeout=12)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=900)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();assert 1<=a.seconds<=900
    a.output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();iterations=0;errors=0;seen=set()
    while time.monotonic()-start<a.seconds:
        row={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'errors':{}}
        def collect(key,fn):
            nonlocal errors
            try:row[key]=fn();return row[key]
            except (subprocess.SubprocessError,OSError,ValueError,KeyError) as exc:
                errors+=1;row['errors'][key]=str(exc)[:1200];return None
        exporter=collect('exporter',lambda:json.loads(run(['get','pod',EXPORTER,'-n','gpu-fractioning','-o','json'])))
        if exporter:
            assert exporter['metadata']['uid']==EXPORTER_UID,'Exporter replaced; stop attribution'
            assert exporter['spec']['nodeName']=='k3s-wk-gpu2'
            row['exporter']={'name':EXPORTER,'uid':EXPORTER_UID,'containers':exporter['status'].get('containerStatuses',[])}
        pods=collect('pods',lambda:json.loads(run(['get','pods','-A','-o','json']))['items'])
        if pods is not None:
            selected=[]
            for p in pods:
                meta=p['metadata'];identity=json.dumps({'name':meta['name'],'labels':meta.get('labels',{}),'annotations':meta.get('annotations',{})})
                if not any(owner in identity for owner in OWNERS):continue
                seen.add(meta['uid'])
                annotations={k:v for k,v in meta.get('annotations',{}).items() if any(s in k.lower() for s in ['gpu','nri','profile','lease','workspace','source','share','attempt','policy'])}
                selected.append({'namespace':meta['namespace'],'name':meta['name'],'uid':meta['uid'],'created':meta['creationTimestamp'],'deleted':meta.get('deletionTimestamp'),'labels':meta.get('labels',{}),'annotations':annotations,'node':p['spec'].get('nodeName'),'scheduler':p['spec'].get('schedulerName'),'containers':p['status'].get('containerStatuses',[]),'phase':p['status']['phase'],'images':[{'name':c['name'],'image':c['image'],'resources':c.get('resources',{})} for c in p['spec']['containers']]})
            row['pods']=selected
        collect('raw_metrics',lambda:run(['get','--raw','/api/v1/namespaces/gpu-fractioning/pods/'+EXPORTER+':2112/proxy/metrics']))
        collect('prometheus',lambda:json.loads(run(['get','--raw',PROM+'query?'+urllib.parse.urlencode({'query':'{job="gpu-fractioning/gpu-fractioning-metricsd"}'})])))
        collect('targets',lambda:[t for t in json.loads(run(['get','--raw',PROM+'targets?state=active']))['data']['activeTargets'] if 'gpu-fractioning' in t.get('scrapePool','')])
        with (a.output/'observations.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        iterations+=1
        if errors>=10:break
        time.sleep(min(5,max(0,a.seconds-(time.monotonic()-start))))
    (a.output/'capture-summary.json').write_text(json.dumps({'iterations':iterations,'read_errors':errors,'read_only':True,'bounded_seconds':a.seconds,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pod_uids_seen':sorted(seen),'owners':OWNERS,'exporter_uid':EXPORTER_UID},indent=2)+'\n')

if __name__=='__main__':main()
