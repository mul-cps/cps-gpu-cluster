#!/usr/bin/env python3
"""Read-only live admission checks; never changes parameters or executes Pods."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[2]
NAME = 'cps-compute-workload-boundary'


def normalized(spec):
    spec = copy.deepcopy(spec)
    for key in ('matchConstraints', 'matchResources'):
        if key in spec:
            spec[key].setdefault('matchPolicy', 'Equivalent')
            spec[key].setdefault('objectSelector', {})
            for rule in spec[key].get('resourceRules', []):
                rule.setdefault('scope', '*')
    return spec


def qualify(context):
    def kubectl(*args, data=None):
        return subprocess.run(['kubectl', '--context', context, '--request-timeout=30s', *args],
                              input=data, text=True, capture_output=True, timeout=60)
    def read(kind, name, namespace=None):
        args = ['get',kind,name,'-o','json'] + (['-n',namespace] if namespace else [])
        result = kubectl(*args)
        if result.returncode: raise RuntimeError('Cannot read live admission configuration')
        return json.loads(result.stdout)
    candidates = list(yaml.safe_load_all((ROOT/'platform-staging/admission.yaml').read_text()))
    live = [read('validatingadmissionpolicy',NAME), read('validatingadmissionpolicybinding',NAME)]
    if any(normalized(a['spec']) != normalized(b['spec']) for a,b in zip(candidates,live)):
        raise RuntimeError('Live policy differs from candidate beyond API defaults')
    status=live[0].get('status',{})
    if status.get('observedGeneration') != live[0]['metadata']['generation'] or status.get('typeChecking',{}).get('expressionWarnings'):
        raise RuntimeError('Live policy type checking is incomplete or has warnings')
    params=read('computeadmissionpolicy','cps-admission-policy','cps-compute')['data']
    executor=params['executor-image']
    if executor not in params['approved-images'].split(','):
        raise RuntimeError('Live executor image is not approved')
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'admission-live-qualification','namespace':'cps-workflows'},'spec':{
        'schedulerName':'kai-scheduler','serviceAccountName':'cps-workflow','automountServiceAccountToken':False,'restartPolicy':'Never',
        'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'seccompProfile':{'type':'RuntimeDefault'}},
        'containers':[{'name':'main','image':executor,'resources':{'requests':{'cpu':'50m','memory':'64Mi'},'limits':{'cpu':'250m','memory':'128Mi'}},'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}
    cases=[('approved-credential-free-shape',pod,True)]
    missing=copy.deepcopy(pod);missing['spec']['containers'][0].pop('resources')
    cases.append(('quota-resources-required',missing,False,'cps-workflow-ceiling'))
    for label,field,value in [('scheduler-override','schedulerName','default-scheduler'),('service-account-override','serviceAccountName','default'),('automatic-token','automountServiceAccountToken',True),('shared-processes','shareProcessNamespace',True)]:
        p=copy.deepcopy(pod);p['spec'][field]=value;cases.append((label,p,False))
    for label,image in [('unapproved-digest','registry.invalid/user@sha256:'+'3'*64),('mutable-tag','registry.invalid/user:latest')]:
        p=copy.deepcopy(pod);p['spec']['containers'][0]['image']=image;cases.append((label,p,False))
    p=copy.deepcopy(pod);p['spec']['containers'][0]['env']=[{'name':'FORBIDDEN','valueFrom':{'secretKeyRef':{'name':'forbidden','key':'key'}}}];cases.append(('user-secret-environment',p,False))
    p=copy.deepcopy(pod);p['spec']['containers'][0]['envFrom']=[{'secretRef':{'name':'forbidden'}}];cases.append(('user-secret-envfrom',p,False))
    p=copy.deepcopy(pod);p['spec']['volumes']=[{'name':'token','projected':{'sources':[{'serviceAccountToken':{'path':'token'}}]}}];p['spec']['containers'][0]['volumeMounts']=[{'name':'token','mountPath':'/stolen'}];cases.append(('user-projected-token',p,False))
    report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'context':context,'tests':[],
            'policy_matches_candidate':True,'live_policy_generation':live[0]['metadata']['generation'],
            'parameter_sha256':hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest(),
            'limitations':['Server-side dry-run only; no controller-generated Pods or runtime qualification',
                           'Positive shape uses the already approved executor; no user image approvals are added']}
    for case in cases:
        label,p,expected=case[:3]
        rejection_source=case[3] if len(case)>3 else NAME
        result=kubectl('create','--dry-run=server','-f','-',data=yaml.safe_dump(p))
        actual=result.returncode==0
        if actual!=expected or (not expected and rejection_source not in result.stderr):
            raise RuntimeError(label+': unexpected live admission response')
        report['tests'].append({'name':label,'accepted':actual,'passed':True,'enforcement':rejection_source if not expected else 'live policy and quota'})
    # Detect parameter changes during the audit; no write or cleanup is needed.
    for before, kind in zip(live, ('validatingadmissionpolicy','validatingadmissionpolicybinding')):
        after = read(kind, NAME)
        if after['metadata']['uid'] != before['metadata']['uid'] or after['spec'] != before['spec']:
            raise RuntimeError('Live admission policy or binding changed during qualification')
    if read('computeadmissionpolicy','cps-admission-policy','cps-compute')['data'] != params:
        raise RuntimeError('Admission parameters changed during qualification')
    report['passed']=True
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    if args.evidence.exists():parser.error('Choose a new evidence file')
    report=qualify(args.context)
    with args.evidence.open('x') as output:json.dump(report,output,indent=2);output.write('\n')
    print(f"{len(report['tests'])} live admission dry-run requests passed; no configuration changes or Pods created")
