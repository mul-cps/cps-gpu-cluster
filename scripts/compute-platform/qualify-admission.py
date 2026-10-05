#!/usr/bin/env python3
"""Operator-only API-server admission tests; creates no running workload Pods."""
import argparse
import copy
import datetime
import json
from pathlib import Path
import subprocess
import time
import uuid
import yaml

ROOT = Path(__file__).resolve().parents[2]


def qualify(context):
    name = 'cps-admission-test-' + uuid.uuid4().hex[:12]
    user_image = 'registry.invalid/user@sha256:' + '1' * 64
    executor_image = 'registry.invalid/executor@sha256:' + '2' * 64
    group = name + '.compute.cps.unileoben.ac.at'
    crd = yaml.safe_load((ROOT / 'platform-staging/admission-parameters-crd.yaml').read_text())
    crd['spec']['group'] = group
    crd['metadata']['name'] = 'computeadmissionpolicies.' + group
    def kubectl(*args, data=None, check=True):
        return subprocess.run(['kubectl', '--context', context, *args],
                              input=data, text=True, capture_output=True, check=check)
    policy, binding = list(yaml.safe_load_all((ROOT / 'platform-staging/admission.yaml').read_text()))
    policy['metadata']['name'] = name
    policy['spec']['paramKind']['apiVersion'] = group + '/v1alpha1'
    policy['spec']['matchConditions'][0]['expression'] = f"request.namespace == '{name}'"
    policy['spec']['matchConstraints']['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name'] = name
    binding['metadata']['name'] = name
    binding['spec']['policyName'] = name
    binding['spec']['matchResources']['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name'] = name
    binding['spec']['paramRef']['namespace'] = name
    objects = [
        {'apiVersion':'v1','kind':'Namespace','metadata':{'name':name,'labels':{
            'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/enforce-version':'v1.34'}}},
        {'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':'cps-workflow','namespace':name},'automountServiceAccountToken':False},
        {'apiVersion':group+'/v1alpha1','kind':'ComputeAdmissionPolicy','metadata':{'name':'cps-admission-policy','namespace':name},
         'data':{'approved-images':user_image + ',' + executor_image,'executor-image':executor_image,
                 'artifact-secret':'cps-artifacts','artifact-ca-secret':'cps-artifacts-ca'}},
        policy, binding,
    ]
    evidence = {'context':context,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'namespace':name,'tests':[],'limitations':['Only admission requests; no images run, GPU jobs, Argo-generated Pods or executor-token isolation qualified']}
    try:
        kubectl('apply','-f','-',data=yaml.safe_dump(crd))
        kubectl('wait','--for=condition=Established','crd/'+crd['metadata']['name'],'--timeout=30s')
        kubectl('apply','-f','-',data=yaml.safe_dump_all(objects[:-2]))
        kubectl('get','computeadmissionpolicies.'+group,'cps-admission-policy','-n',name)
        kubectl('apply','-f','-',data=yaml.safe_dump_all(objects[-2:]))
        # Wait for CEL type checking; then establish a denied-request barrier so
        # admission tests cannot silently race policy propagation.
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = json.loads(kubectl('get','validatingadmissionpolicy',name,'-o','json').stdout)
            status = state.get('status',{})
            if status.get('observedGeneration') == state['metadata']['generation']:
                warnings = status.get('typeChecking',{}).get('expressionWarnings',[])
                if warnings:
                    raise RuntimeError(f'Admission CEL warnings: {warnings}')
                break
            time.sleep(1)
        else:
            raise RuntimeError('Admission type checking did not complete')
        pod = {'apiVersion':'v1','kind':'Pod','metadata':{'name':'fixture','namespace':name},'spec':{
            'schedulerName':'kai-scheduler','serviceAccountName':'cps-workflow',
            'automountServiceAccountToken':False,'restartPolicy':'Never',
            'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'seccompProfile':{'type':'RuntimeDefault'}},
            'containers':[{'name':'main','image':user_image,'securityContext':{
                'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}
        def request(value):
            return kubectl('create','--dry-run=server','-f','-',data=yaml.safe_dump(value),check=False)
        barrier = copy.deepcopy(pod)
        barrier['spec']['automountServiceAccountToken'] = True
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            result = request(barrier)
            if result.returncode and 'automatic service-account credentials' in result.stderr:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f'Admission binding did not become effective: {result.stderr}')
        cases = [('valid-credential-free-pod',pod,True),('automatic-token',barrier,False)]
        trusted = copy.deepcopy(pod)
        trusted['spec']['volumes'] = [{'name':'artifacts','secret':{'secretName':'cps-artifacts'}}]
        executor = {'name':'wait','image':executor_image,
                    'command':['argoexec','wait','--loglevel','info','--log-format','text','--gloglevel','0'],
                    'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
                    'volumeMounts':[{'name':'artifacts','mountPath':'/argo/secret/cps-artifacts','readOnly':True}]}
        trusted['spec']['containers'].append(executor)
        trusted['spec']['initContainers'] = [dict(executor,name='init')]
        trusted['spec']['initContainers'][0]['command'] = ['argoexec','init','--loglevel','info','--log-format','text','--gloglevel','0']
        cases.append(('trusted-executor-secret-mounts',trusted,True))
        overridden = copy.deepcopy(trusted)
        overridden['spec']['containers'][1]['command'] = ['sh','-c','cat /argo/secret/cps-artifacts/secretKey']
        cases.append(('approved-executor-overridden-command',overridden,False))
        loader = copy.deepcopy(trusted)
        loader['spec']['containers'][1]['env'] = [{'name':'LD_PRELOAD','value':'/tmp/rogue.so'}]
        cases.append(('executor-loader-environment',loader,False))
        binary = copy.deepcopy(trusted)
        binary['spec']['volumes'].append({'name':'rogue','emptyDir':{}})
        binary['spec']['containers'][1]['volumeMounts'].append({'name':'rogue','mountPath':'/usr/local/bin'})
        cases.append(('executor-binary-shadow-mount',binary,False))
        secret = copy.deepcopy(pod)
        secret['spec']['containers'][0]['env'] = [{'name':'SECRET','valueFrom':{'secretKeyRef':{'name':'forbidden','key':'key'}}}]
        cases.append(('user-secret-environment',secret,False))
        token = copy.deepcopy(pod)
        token['spec']['volumes'] = [{'name':'token','projected':{'sources':[{'serviceAccountToken':{'path':'token'}}]}}]
        token['spec']['containers'][0]['volumeMounts'] = [{'name':'token','mountPath':'/stolen'}]
        cases.append(('user-projected-token',token,False))
        wait = copy.deepcopy(pod)
        wait['spec']['containers'][0]['name'] = 'wait'
        cases.append(('untrusted-wait-image',wait,False))
        shared = copy.deepcopy(pod)
        shared['spec']['shareProcessNamespace'] = True
        cases.append(('shared-executor-processes',shared,False))
        for label, candidate, accepted in cases:
            result = request(candidate)
            actual = result.returncode == 0
            if actual != accepted or (not accepted and name not in result.stderr):
                raise RuntimeError(f'{label}: unexpected admission response {result.stderr}')
            evidence['tests'].append({'name':label,'accepted':actual,'passed':True})
        evidence['passed'] = True
        return evidence
    finally:
        kubectl('delete','validatingadmissionpolicybinding',name,'--ignore-not-found',check=False)
        kubectl('delete','validatingadmissionpolicy',name,'--ignore-not-found',check=False)
        kubectl('delete','namespace',name,'--ignore-not-found','--wait=false',check=False)
        kubectl('delete','crd',crd['metadata']['name'],'--ignore-not-found','--wait=false',check=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args = parser.parse_args()
    if args.evidence.exists():
        parser.error('Choose a new evidence file; existing evidence is never overwritten')
    result = qualify(args.context)
    with args.evidence.open('x') as file:
        file.write(json.dumps(result,indent=2)+'\n')
    print(f"{len(result['tests'])} isolated admission requests passed; no workload Pods created")
