"""Fresh QA-only manifest and read brackets. Transport vectors require independent Root review."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import uuid

GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
BOOT='a464df41-e391-4443-b8e8-ad7ecd052318'
GENERATION='4ebffc96-e25e-4583-a3b8-0d853fd90efd'
NAMESPACE='cps-native-qa147-20261022'
NAMESPACE_UID='1f7d941a-872d-4453-a1ba-fd489d8aff14'
NOTEBOOK_IMAGE='ghcr.io/mul-cps/cps-jupyter-notebook@sha256:5427088986bc06ad0713875d1aa2f31439f0bd1fbe6099d4669570fcf3e85be4'

def require(value,message):
    if not value:raise ValueError(message)

def unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate JSON key denied');result[key]=value
    return result

def validate_targets(value):
    require(type(value) is dict and set(value)=={'version','cohort_uid','namespace_uid','pods','observer_argv','physical_argv'}
            and type(value['version']) is int and value['version']==1
            and value['namespace_uid']==NAMESPACE_UID,'Closed fresh actual QA manifest required')
    cohort=value['cohort_uid']
    require(type(cohort) is str and str(uuid.UUID(cohort))==cohort and uuid.UUID(cohort).int>0,
            'Reviewed canonical fresh cohort UUID required')
    require(type(value['pods']) is dict and set(value['pods'])=={'a','b'},'Two exact current Pods required')
    for key,row in value['pods'].items():
        require(type(row) is dict and set(row)=={'namespace','name','uid','cap_mib','spec_sha256'}
                and row['namespace']==NAMESPACE and row['name']=='native-qa147-'+key+'-'+cohort[:8]
                and type(row['cap_mib']) is int and row['cap_mib']==5120
                and type(row['spec_sha256']) is str and re.fullmatch('[a-f0-9]{64}',row['spec_sha256']),
                'Exact fresh cohort Pod/spec/cap required')
        require(type(row['uid']) is str and str(uuid.UUID(row['uid']))==row['uid'] and uuid.UUID(row['uid']).int>0,
                'Actual nonzero Pod UID required')
    require(len({row['uid'] for row in value['pods'].values()})==2,'Independent actual Pod UIDs required')
    for key,script in (('observer_argv','observe.py'),('physical_argv','physical_samples.py')):
        argv=value[key]
        require(type(argv) is list and 3<=len(argv)<=128 and all(type(s) is str and 0<len(s)<=4096
                and not any(c in s for c in '\x00\r\n') for s in argv)
                and Path(argv[0]).name in ('ssh','kubectl') and '--execute' in argv
                and any(Path(s).name==script for s in argv),'Independently reviewed bounded Root transport argv required')
    argv=value['observer_argv']
    require(argv.count('--cohort-uid')==1 and argv.index('--cohort-uid')+1<len(argv)
            and argv[argv.index('--cohort-uid')+1]==cohort,'Host observer must bind this exact cohort')
    return value

def read_targets(path,pin):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,65537);after=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
                and stat.S_IMODE(before.st_mode)==0o600 and 0<len(raw)<=65536
                and all(getattr(before,k)==getattr(after,k) for k in
                    ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Stable private actual manifest required')
        require(hashlib.sha256(raw).hexdigest()==pin,'Independently reviewed complete manifest raw hash required')
        return validate_targets(json.loads(raw,object_pairs_hook=unique))
    finally:os.close(fd)

def command(argv):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
    require(result.returncode==0 and len(result.stdout)<=4*1024*1024,'Bounded actual Root observation failed')
    return json.loads(result.stdout,object_pairs_hook=unique)

def pod(row):return command(['kubectl','-n',row['namespace'],'get','pod',row['name'],'-o','json'])

def checked_pod(actual,row):
    meta,spec,status=actual['metadata'],actual['spec'],actual['status']
    require(all(meta.get(k)==row[k] for k in ('namespace','name','uid')) and not meta.get('deletionTimestamp')
            and spec.get('nodeName')=='k3s-wk-gpu2' and status.get('phase')=='Running'
            and hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':')).encode()).hexdigest()==row['spec_sha256'],
            'Exact actual live UID and full admitted QA Pod spec required')
    containers=[c for c in spec['containers'] if c['name']=='notebook']
    statuses=[c for c in status['containerStatuses'] if c['name']=='notebook']
    require(len(containers)==len(statuses)==1 and containers[0]['image']==NOTEBOOK_IMAGE,'Exact notebook542 image required')
    current=statuses[0]
    require(current['ready'] is True and current['restartCount']==0 and 'running' in current['state']
            and current['imageID'].split('@')[-1]==NOTEBOOK_IMAGE.split('@')[-1],
            'Actual ready un-restarted current notebook required')
    return {'uid':row['uid'],'spec':spec,'status':current}

def preflight(config):
    targets=validate_targets(config['manifest'])
    before=[checked_pod(pod(targets['pods'][key]),targets['pods'][key]) for key in ('a','b')]
    host=command(targets['observer_argv'])
    require(type(host) is dict and host.get('pods')==before and host.get('hardware_qualified') is False
            and type(host.get('targets')) is list and len(host['targets'])==2
            and [r.get('pod_uid') for r in host['targets']]==[r['uid'] for r in before],
            'Fresh exact reviewed host observer proof must match API bracket')
    require(before==[checked_pod(pod(targets['pods'][key]),targets['pods'][key]) for key in ('a','b')],
            'Actual QA Pod changed during host observation')
    # Keep full original host proof as evidence; old packaged Node/head is deliberately not an authority here.
    return {'pods':before,'host':host}
