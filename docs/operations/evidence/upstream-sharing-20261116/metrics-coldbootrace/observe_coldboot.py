#!/usr/bin/env python3
"""Bounded read-only GPU2 marker/container/metrics capture across a root-owned reboot."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.parse

PROM='/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-prometheus:9090/proxy/api/v1/'
HOST_CODE='''import json,pathlib,os,hashlib,time
marker=pathlib.Path('/run/nvidia/validations/driver-ready')
wrapper=pathlib.Path('/usr/local/nvidia/toolkit/nvidia-container-runtime')
result={'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'host_time_ns':time.time_ns(),'nvidia_module_present':any(x.startswith('nvidia ') for x in pathlib.Path('/proc/modules').read_text().splitlines()),'marker_exists':marker.exists()}
if marker.exists():
 s=marker.stat();result['marker']={'mtime_ns':s.st_mtime_ns,'inode':s.st_ino,'uid':s.st_uid,'mode':oct(s.st_mode),'size':s.st_size}
if wrapper.exists():
 b=wrapper.read_bytes();result['runtime_wrapper_sha256']=hashlib.sha256(b).hexdigest();result['runtime_wrapper']=b.decode()
print(json.dumps(result))
'''

def command(args,stdin=None):
    return subprocess.check_output(args,input=stdin,text=True,stderr=subprocess.PIPE,timeout=12)

def kube(args):return command(['kubectl','--request-timeout=8s',*args])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=900)
    a=parser.parse_args();assert 1<=a.seconds<=900
    a.output.mkdir(exist_ok=False,parents=True)
    deadline=time.monotonic()+a.seconds;iterations=0;errors=0;boots=set()
    while time.monotonic()<deadline:
        row={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'errors':{}}
        def collect(key,fn):
            nonlocal errors
            try:row[key]=fn();return row[key]
            except (subprocess.SubprocessError,OSError,ValueError,KeyError) as exc:
                errors+=1;row['errors'][key]=str(exc)[:1000];return None
        host=collect('host',lambda:json.loads(command(['ssh','-i','/home/bjoern/.ssh/id_ed25519','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','ubuntu@10.21.0.43','python3 -'],HOST_CODE)))
        if host:boots.add(host['boot_id'])
        pods=collect('pods',lambda:json.loads(kube(['get','pods','-n','gpu-fractioning','--field-selector','spec.nodeName=k3s-wk-gpu2','-o','json']))['items'])
        if pods:
            row['pods']=[{'name':p['metadata']['name'],'uid':p['metadata']['uid'],'created':p['metadata']['creationTimestamp'],'status':p.get('status'),'volumes':p['spec'].get('volumes'),'runtimeClassName':p['spec'].get('runtimeClassName')} for p in pods]
            for p in pods:
                if p['metadata']['labels'].get('app.kubernetes.io/component')!='fractiond':continue
                name=p['metadata']['name']
                collect('metricsd_log_'+name,lambda:kube(['logs','-n','gpu-fractioning',name,'-c','metricsd','--timestamps','--tail=100']))
                collect('raw_metrics_'+name,lambda:kube(['get','--raw','/api/v1/namespaces/gpu-fractioning/pods/'+name+':2112/proxy/metrics']))
        collect('gf_status',lambda:json.loads(kube(['get','gpufractioningconfig','default','-o','json']))['status'])
        collect('fleet_status',lambda:json.loads(kube(['get','bundle','gpu-fractioning','-n','fleet-local','-o','json']))['status'])
        collect('targets',lambda:[t for t in json.loads(kube(['get','--raw',PROM+'targets?state=active']))['data']['activeTargets'] if 'gpu-fractioning' in t.get('scrapePool','')])
        collect('prometheus',lambda:json.loads(kube(['get','--raw',PROM+'query?'+urllib.parse.urlencode({'query':'{job="gpu-fractioning/gpu-fractioning-metricsd"}'})])))
        with (a.output/'observations.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        iterations+=1
        time.sleep(min(5,max(0,deadline-time.monotonic())))
    (a.output/'capture-summary.json').write_text(json.dumps({'iterations':iterations,'read_errors_including_expected_boot_outage':errors,'boot_ids':sorted(boots),'read_only':True,'bounded_seconds':a.seconds,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')

if __name__=='__main__':main()
