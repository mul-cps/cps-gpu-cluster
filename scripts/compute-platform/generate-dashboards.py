#!/usr/bin/env python3
"""Generate the four Git-owned compute dashboards. Missing data stays unknown."""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring'
FRESH_SECONDS=120

def fresh(selector):
    return f'({selector} and (time() - timestamp({selector}) <= {FRESH_SECONDS}))'

def fresh_rate(metric,operation='rate'):
    return f'({operation}({metric}[10m]) and (time() - timestamp({metric}) <= {FRESH_SECONDS}))'

SPAWN_P95='histogram_quantile(0.95, sum by (le, namespace) ('+fresh_rate('jupyterhub_server_spawn_duration_seconds_bucket')+'))'

DASHBOARDS={
'compute-overview': ('Compute Overview', [
 ('Running servers by Hub', fresh('jupyterhub_running_servers{namespace=~"jupyterhub|cit-jhub"}'), 'short'),
 ('Physical GPU devices observed', 'count(count by (UUID) ('+fresh('DCGM_FI_DEV_FB_FREE')+'))', 'short'),
 ('Placement-eligible physical free GPUs (controller required)', fresh('cps_compute_physical_free_gpus'), 'short'),
 ('Hub spawn p95 seconds', SPAWN_P95, 's'),
 ('Hub scrape availability', fresh('up{namespace=~"jupyterhub|cit-jhub",service="hub"}'), 'short'),
]),
'gpu-packing': ('GPU Packing', [
 ('Unused VRAM per physical device (not free GPUs)', fresh('DCGM_FI_DEV_FB_FREE'), 'decmbytes'),
 ('Used VRAM per physical device', fresh('DCGM_FI_DEV_FB_USED'), 'decmbytes'),
 ('Runtime GPU utilization', fresh('DCGM_FI_DEV_GPU_UTIL'), 'percent'),
 ('Placement-eligible free devices (controller required)', fresh('cps_compute_physical_free_gpus'), 'short'),
 ('Enforced memory cap (isolator required)', fresh('cps_compute_gpu_memory_limit_bytes'), 'bytes'),
]),
'kai-fairness': ('KAI Scheduling/Fairness', [
 ('Queue GPU fair share', fresh('kai_queue_fair_share_gpu'), 'short'),
 ('Queue GPU usage (upstream UsageDB units)', fresh('kai_queue_gpu_usage'), 'short'),
 ('Preemption attempts (not evicted pods)', fresh_rate('kai_total_preemption_attempts','increase'), 'short'),
 ('KAI scheduling + binding latency (not full startup)', fresh('kai_e2e_scheduling_latency_milliseconds'), 'ms'),
 ('KAI scheduler availability', fresh('up{namespace="kai-scheduler"}'), 'short'),
]),
' teaching-readiness'.strip(): ('Teaching/Exam Readiness', [
 ('Spawn p95, target 180s', SPAWN_P95, 's'),
 ('Protected sessions (policy controller required)', fresh('cps_compute_protected_sessions'), 'short'),
 ('Reservation conflicts (gateway required)', fresh_rate('cps_compute_reservation_conflicts_total','increase'), 'short'),
 ('Physical free GPUs (controller required)', fresh('cps_compute_physical_free_gpus'), 'short'),
 ('Current protection class (controller required)', fresh('cps_compute_teaching_priority'), 'short'),
]),
}
for slug,(title,items) in DASHBOARDS.items():
    panels=[{'id':1,'type':'text','title':'Evidence boundary','gridPos':{'h':4,'w':24,'x':0,'y':0},
             'options':{'mode':'markdown','content':'Missing or stale series mean **unavailable**, never zero. Physical free GPUs require placement/UUID accounting; VRAM and utilization are separate. Panels naming a required controller/isolator stay unknown until that exporter is deployed. Spawn histogram does not prove a representative pre-pulled burst qualification. Operational viewers only; students use the addon.'}}]
    for idx,(name,expr,unit) in enumerate(items,2):
        panels.append({'id':idx,'type':'timeseries','title':name,'description':'Planned telemetry contract; no qualified exporter is deployed for this series. Unavailable means unknown, never zero.' if 'cps_compute_' in expr else 'Observed upstream telemetry; samples older than 120 seconds are unavailable.','datasource':{'type':'prometheus','uid':'${DS_PROMETHEUS}'},
                       'gridPos':{'h':8,'w':12,'x':12*((idx-2)%2),'y':4+8*((idx-2)//2)},
                       'targets':[{'refId':'A','expr':expr,'legendFormat':'{{namespace}} {{queue_name}} {{UUID}}'}],
                       'fieldConfig':{'defaults':{'unit':unit,'noValue':'Unavailable / stale','custom':{'spanNulls':False}},'overrides':[]}})
    health_metrics=('DCGM_FI_DEV_FB_FREE', 'up{namespace="jupyterhub",service="hub"}', 'up{namespace="cit-jhub",service="hub"}', 'up{namespace="kai-scheduler",service="kai-scheduler-default"}', 'cps_compute_physical_free_gpus')
    for health_index,metric in enumerate(health_metrics):
        idx=len(panels)+1
        panels.append({'id':idx,'type':'stat','title':f'Telemetry availability: {metric}','description':'Planned controller contract; no qualified exporter is deployed. This panel must remain unavailable until qualification.' if metric.startswith('cps_compute_') else 'Instant target/series freshness; missing, failed or samples older than 120 seconds are unavailable.',
                       'datasource':{'type':'prometheus','uid':'${DS_PROMETHEUS}'},
                       'gridPos':{'h':4,'w':8,'x':8*(health_index%3),'y':4+8*((len(items)+1)//2)+4*(health_index//3)},
                       'targets':[{'refId':'A','instant':True,'expr':f'(time() - max(timestamp({metric})) > bool 120) or absent({metric})' if not metric.startswith('up{') else f'clamp_max((1 - min({metric})) + (time() - max(timestamp({metric})) > bool 120), 1) or absent({metric})'}],
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
