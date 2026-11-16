#!/usr/bin/env python3
"""Summarize retained observations only; no cluster access or workload changes."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
rows=[json.loads(line) for line in (ROOT/'capture/observations.jsonl').read_text().splitlines()]
pods={}
for row in rows:
    for p in row.get('pods',[]):
        uid=p['uid']
        if uid not in pods:
            pods[uid]={'namespace':p['namespace'],'name':p['name'],'uid':uid,'first_observed':row['time'],'last_observed':row['time'],'observations':0,'node':p['node'],'scheduler':p['scheduler'],'annotations':p['annotations'],'labels':p['labels'],'images':p['images'],'container_identities':{},'raw':{},'prometheus':{}}
        item=pods[uid];item['last_observed']=row['time'];item['observations']+=1
        for c in p['containers']:
            if c.get('containerID'):item['container_identities'][c['containerID']]={k:c.get(k) for k in ['name','imageID','restartCount','state']}

def record(kind,stamp,name,labels,value):
    uid=labels.get('pod_uuid')
    if uid not in pods:return
    key=json.dumps({'metric':name,'labels':labels},sort_keys=True)
    series=pods[uid][kind]
    if key not in series:series[key]={'metric':name,'labels':labels,'first_observed':stamp,'last_observed':stamp,'observations':0,'nonzero_observations':0,'max':value}
    item=series[key];item['last_observed']=stamp;item['observations']+=1;item['nonzero_observations']+=int(value>0);item['max']=max(item['max'],value)

for row in rows:
    for line in row.get('raw_metrics','').splitlines():
        match=re.match(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)\{(.*)\}\s+(\S+)',line)
        if not match:continue
        name,body,value=match.groups()
        labels={k:json.loads('"'+v+'"') for k,v in re.findall(r'(\w+)="((?:[^"\\]|\\.)*)"',body)}
        record('raw',row['time'],name,labels,float(value))
    for result in row.get('prometheus',{}).get('data',{}).get('result',[]):
        labels=dict(result['metric']);name=labels.pop('__name__')
        record('prometheus',row['time'],name,labels,float(result['value'][1]))

for item in pods.values():
    for kind in ['raw','prometheus']:item[kind]=list(item[kind].values())
    item['coverage']={}
    for kind in ['raw','prometheus']:
        for family in ['memory','sm']:
            matching=[s for s in item[kind] if family in s['metric'].lower()]
            item['coverage'][kind+'_'+family]={'series':len(matching),'nonzero_series':sum(s['nonzero_observations']>0 for s in matching)}

last=rows[-1]
summary={'first_observation':rows[0]['time'],'last_observation':last['time'],'observations':len(rows),'read_errors':sum(len(r.get('errors',{})) for r in rows),'pods':list(pods.values()),'last_observed_pod_uids':[p['uid'] for p in last.get('pods',[])],'last_raw_pod_series_lines':[line for line in last.get('raw_metrics','').splitlines() if 'pod_uuid=' in line],'last_targets':[{k:t.get(k) for k in ['scrapeUrl','health','lastError']} for t in last.get('targets',[])],'limitations':['Pod assignment and readiness do not establish actual GPU usage.','Short activity can fall between Prometheus scrapes; absent nonzero SM is not a failed kernel.','Prometheus instant-query samples may outlive Pod deletion until staleness processing.','Lease/kernel-leaf witness joins require separately retained workspace-agent evidence.']}
(ROOT/'coverage.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'observations':summary['observations'],'read_errors':summary['read_errors'],'pods':[{'uid':p['uid'],'namespace':p['namespace'],'coverage':p['coverage']} for p in summary['pods']]},indent=2))
