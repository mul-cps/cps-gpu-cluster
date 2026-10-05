#!/usr/bin/env python3
"""Generate the four Git-owned compute dashboards. Missing data stays unknown."""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring'
DASHBOARDS={
'compute-overview': ('Compute Overview', [
 ('Running servers by Hub', 'jupyterhub_running_servers', 'short'),
 ('Physical GPU devices observed', 'count(count by (UUID) (DCGM_FI_DEV_FB_FREE))', 'short'),
 ('Placement-eligible physical free GPUs (controller required)', 'cps_compute_physical_free_gpus', 'short'),
 ('Hub spawn p95 seconds', 'histogram_quantile(0.95, sum by (le, namespace) (rate(jupyterhub_server_spawn_duration_seconds_bucket[10m])))', 's'),
 ('Hub scrape availability', 'up{namespace=~"jupyterhub|cit-jhub",service="hub"}', 'short'),
]),
'gpu-packing': ('GPU Packing', [
 ('Unused VRAM per physical device (not free GPUs)', 'DCGM_FI_DEV_FB_FREE', 'decmbytes'),
 ('Used VRAM per physical device', 'DCGM_FI_DEV_FB_USED', 'decmbytes'),
 ('Runtime GPU utilization', 'DCGM_FI_DEV_GPU_UTIL', 'percent'),
 ('Placement-eligible free devices (controller required)', 'cps_compute_physical_free_gpus', 'short'),
 ('Enforced memory cap (isolator required)', 'cps_compute_gpu_memory_limit_bytes', 'bytes'),
]),
'kai-fairness': ('KAI Scheduling/Fairness', [
 ('Queue GPU fair share', 'kai_queue_fair_share_gpu', 'short'),
 ('Queue GPU usage (upstream UsageDB units)', 'kai_queue_gpu_usage', 'short'),
 ('Evicted pods per PodGroup', 'increase(kai_pod_group_evicted_pods_total[10m])', 'short'),
 ('Scheduling algorithm latency (not full startup)', 'kai_e2e_scheduling_latency_milliseconds', 'ms'),
 ('KAI scheduler availability', 'up{namespace="kai-scheduler"}', 'short'),
]),
' teaching-readiness'.strip(): ('Teaching/Exam Readiness', [
 ('Spawn p95, target 180s', 'histogram_quantile(0.95, sum by (le, namespace) (rate(jupyterhub_server_spawn_duration_seconds_bucket[10m])))', 's'),
 ('Protected sessions (policy controller required)', 'cps_compute_protected_sessions', 'short'),
 ('Reservation conflicts (gateway required)', 'increase(cps_compute_reservation_conflicts_total[10m])', 'short'),
 ('Physical free GPUs (controller required)', 'cps_compute_physical_free_gpus', 'short'),
 ('Current protection class (controller required)', 'cps_compute_teaching_priority', 'short'),
]),
}
for slug,(title,items) in DASHBOARDS.items():
    panels=[{'id':1,'type':'text','title':'Evidence boundary','gridPos':{'h':4,'w':24,'x':0,'y':0},
             'options':{'mode':'markdown','content':'Missing or stale series mean **unavailable**, never zero. Physical free GPUs require placement/UUID accounting; VRAM and utilization are separate. Panels naming a required controller/isolator stay unknown until that exporter is deployed. Spawn histogram does not prove a representative pre-pulled burst qualification. Operational viewers only; students use the addon.'}}]
    for idx,(name,expr,unit) in enumerate(items,2):
        panels.append({'id':idx,'type':'timeseries','title':name,'datasource':{'type':'prometheus','uid':'${DS_PROMETHEUS}'},
                       'gridPos':{'h':8,'w':12,'x':12*((idx-2)%2),'y':4+8*((idx-2)//2)},
                       'targets':[{'refId':'A','expr':expr,'legendFormat':'{{namespace}} {{queue}} {{UUID}}'}],
                       'fieldConfig':{'defaults':{'unit':unit,'noValue':'Unavailable / stale','custom':{'spanNulls':False}},'overrides':[]}})
    for metric in ('DCGM_FI_DEV_FB_FREE', 'jupyterhub_running_servers', 'cps_compute_physical_free_gpus'):
        idx=len(panels)+1
        panels.append({'id':idx,'type':'stat','title':f'Telemetry missing/stale: {metric}',
                       'datasource':{'type':'prometheus','uid':'${DS_PROMETHEUS}'},
                       'gridPos':{'h':4,'w':8,'x':8*((idx-2)%3),'y':28},
                       'targets':[{'refId':'A','expr':f'(time() - max(timestamp({metric})) > bool 120) or absent({metric})'}],
                       'fieldConfig':{'defaults':{'noValue':'Unavailable','mappings':[{'type':'value','options':{'0':{'text':'Fresh'},'1':{'text':'Unavailable / stale'}}}],
                                                'thresholds':{'mode':'absolute','steps':[{'color':'green','value':None},{'color':'red','value':1}]}},'overrides':[]}})
    dashboard={'uid':f'cps-{slug}','title':f'CPS / CIT — {title}','schemaVersion':39,'version':1,'refresh':'30s',
               'tags':['cps-compute','gitops'],'time':{'from':'now-1h','to':'now'},'panels':panels,
               'templating':{'list':[{'name':'DS_PROMETHEUS','type':'datasource','query':'prometheus','current':{}}]},
               'links':[{'title':'CPS Hub','url':'https://jupyterhub.dshl.unileoben.ac.at','targetBlank':True},
                        {'title':'CIT Hub','url':'https://jhub.dshl.unileoben.ac.at','targetBlank':True},
                        {'title':'Rancher','url':'https://rancher.dshl.unileoben.ac.at','targetBlank':True}]}
    cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':f'cps-{slug}-dashboard','namespace':'cattle-monitoring-system',
        'labels':{'grafana_dashboard':'1'},'annotations':{'k8s-sidecar-target-directory':'/tmp/dashboards/Compute'}},
        'data':{f'{slug}.json':json.dumps(dashboard,sort_keys=True,indent=2)}}
    (DEST/f'cps-{slug}-dashboard.yaml').write_text(yaml.safe_dump(cm,sort_keys=False,width=120))
