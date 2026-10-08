#!/usr/bin/env python3
"""Summarize private actual receipts offline; no Kubernetes or GPU operations."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def events(path):
    rows=[]
    for line in path.read_text().splitlines():
        try:rows.append(json.loads(line.split(' ',1)[1]))
        except (json.JSONDecodeError,IndexError):pass
    return rows


def summarize(evidence,main_name,peer_name,physical=None):
    cm=json.loads((evidence/'configmap.json').read_text());cmsha=hashlib.sha256(json.dumps(cm['data'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if not cm['immutable'] or cmsha!=cm['metadata']['annotations']['source.data.sha256']:raise ValueError('Exact immutable source bytes required')
    mains=events(evidence/(main_name+'-main.log'));peers=events(evidence/(peer_name+'-main.log'))
    ticks=[r for r in peers if r.get('kind')=='independent-guard-peer-heartbeat'];times=[r['parent']['observed_ns'] for r in ticks]
    if times!=sorted(times) or len(times)!=len(set(times)):raise ValueError('Ordered unique actual heartbeat samples required')
    result={'schemaVersion':1,'evidenceKind':'actual-trusted-global-guard-canary','sourceDataSha256':cmsha,
      'configmap':{k:cm['metadata'][k] for k in ('name','uid','resourceVersion')},'productionQualified':False,
      'hostileIsolationQualified':False,'automaticKaiOrchestratorQualified':False,
      'capApplication':'root native operator CLI and sealed first-init receipt; automatic helper unqualified',
      'pods':{},'mainRecords':mains,'peer':{'ticks':len(ticks),'allCudaResultsZero':bool(ticks) and all(t['tick']['cuda_result']==0 for t in ticks),
        'firstObservedNs':min(times) if times else None,'lastObservedNs':max(times) if times else None,
        'maxGapMs':max((b-a for a,b in zip(times,times[1:])),default=0)/1e6},'phaseCoverage':[],'evidenceFiles':{}}
    if (evidence/'namespace.json').exists():
        namespace=json.loads((evidence/'namespace.json').read_text())
        result['namespace']={k:namespace['metadata'][k] for k in ('name','uid')}
    for name in (main_name,peer_name):
        pod=json.loads((evidence/(name+'.json')).read_text())
        if pod['metadata']['annotations']['source.data.sha256']!=cmsha or pod['spec']['nodeName']!='k3s-wk-gpu2':raise ValueError('Actual Pod source/node mismatch')
        result['pods'][name]={'uid':pod['metadata']['uid'],'resourceVersion':pod['metadata']['resourceVersion'],'phase':pod['status']['phase'],
          'mainSecurityContext':pod['spec']['containers'][0]['securityContext'],
          'hostPaths':[v['hostPath']['path'] for v in pod['spec']['volumes'] if 'hostPath' in v],
          'automountServiceAccountToken':pod['spec'].get('automountServiceAccountToken'),
          'containers':[{k:s.get(k) for k in ('name','containerID','imageID','state','restartCount')} for s in
            pod['status'].get('initContainerStatuses',[])+pod['status'].get('containerStatuses',[])]}
        for container in ('cps-driver-cap-gate','main'):
            path=evidence/(name+'-'+container+'.log');result['evidenceFiles'][path.name]={'sha256':digest(path),'bytes':path.stat().st_size}
    for row in mains:
        if 'started_ns' not in row or 'finished_ns' not in row:continue
        start,end=row['started_ns'],row['finished_ns'];left=[t for t in times if t<=start];right=[t for t in times if t>=end]
        selected=[t for t in times if start<=t<=end]
        bracketed=bool(left and right) and start-left[-1]<=1000000000 and right[0]-end<=1000000000
        result['phaseCoverage'].append({'mode':row.get('mode'),'launch':row.get('launch'),'startedNs':start,'finishedNs':end,
          'ticksInside':len(selected),'bracketedWithinOneSecond':bracketed,
          'leftGapMs':(start-left[-1])/1e6 if left else None,'rightGapMs':(right[0]-end)/1e6 if right else None})
    peer_final=next((row for row in reversed(peers) if row.get('status')=='peer-completed'),None)
    peer_status=result['pods'][peer_name]
    result['peer']['terminalSucceeded']=peer_status['phase']=='Succeeded' and all(
        row.get('state',{}).get('terminated',{}).get('exitCode')==0 for row in peer_status['containers'])
    result['peer']['reportedDurationSeconds']=(peer_final['finished_ns']-peer_final['started_ns'])/1e9 if peer_final else None
    result['completePeerCoverage']=result['peer']['terminalSucceeded'] and peer_final is not None and result['peer']['reportedDurationSeconds']>=120 and bool(result['phaseCoverage']) and result['peer']['allCudaResultsZero'] and all(r['bracketedWithinOneSecond'] for r in result['phaseCoverage']) and result['peer']['maxGapMs']<=1000
    native=evidence/'native-operator'
    result['rootNativeCapProofs']=[]
    if native.exists():
        for proof_file in sorted(native.glob('*manual-cap-and-release.json')):
            proof=json.loads(proof_file.read_text());name=next((name for name,entry in result['pods'].items() if entry['uid']==proof['pod_uid']),None)
            if name is None:raise ValueError('Foreign native cap proof')
            pod=json.loads((evidence/(name+'.json')).read_text())
            spec_sha=hashlib.sha256(json.dumps(pod['spec'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
            gate=next(row for row in result['pods'][name]['containers'] if row['name']=='cps-driver-cap-gate')
            if spec_sha!=proof['spec_sha256'] or gate['containerID'].split('://',1)[1]!=proof['container_id'] or proof['state']!='applied-before-main':
                raise ValueError('Actual native Pod spec/gate generation mismatch')
            if proof['readback']['soft']!=proof['cap_bytes'] or proof['readback']['hard']!=proof['cap_bytes']:raise ValueError('Native cap/readback mismatch')
            result['rootNativeCapProofs'].append(dict(proof,evidenceSha256=digest(proof_file)))
    if physical:
        samples=[json.loads(line) for line in physical.read_text().splitlines() if line.strip()];gpus={}
        for sample in samples:
            if 'gpu_rows' in sample:rows=sample['gpu_rows'];kind='uuid-used-util'
            else:
                if sample.get('exit_code')!=0 or sample.get('stderr'):raise ValueError('Physical query failed')
                rows=sample['raw'].splitlines();kind='index-uuid-used-total'
            for raw in rows:
                fields=[f.strip() for f in raw.split(',')]
                if kind=='uuid-used-util':gpu,used,util=fields
                else:index,gpu,used,total=fields;util=None
                values=gpus.setdefault(gpu,{'usedMiB':[],'utilPercent':[]});values['usedMiB'].append(int(used))
                if util is not None:values['utilPercent'].append(int(util))
        result['physicalMemory']={'sourceSha256':digest(physical),'samples':len(samples),
           'firstObservedNs':samples[0].get('observed_ns',samples[0].get('started_ns')),
           'lastObservedNs':samples[-1].get('observed_ns',samples[-1].get('finished_ns')),
           'gpus':{gpu:{'minUsedMiB':min(v['usedMiB']),'maxUsedMiB':max(v['usedMiB']),
                         'maxUtilPercent':max(v['utilPercent']) if v['utilPercent'] else None} for gpu,v in gpus.items()},
           'scope':'physical trace covers main phase, not entire120s peer interval'}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--main',required=True);parser.add_argument('--peer',required=True);parser.add_argument('--physical',type=Path)
    args=parser.parse_args();print(json.dumps(summarize(args.evidence,args.main,args.peer,args.physical),indent=2))
