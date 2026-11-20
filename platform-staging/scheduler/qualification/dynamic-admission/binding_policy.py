#!/usr/bin/env python3
"""Render a separate, disabled offline Pod-binding admission candidate.

Approval records are protected operator attestations, not cross-object proofs.
This builder emits no namespace, RBAC, controller, workload or deployment.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

KAI_COMMIT='bdf434e5e9201cccf4e05fad04d814363653f692'
KAI_TAG='v0.18.1'
SOURCE_FILES={
    'pkg/binder/binding/binder.go':'f7828478d782299e1636182d593ccced4e79f0dd03bc06b5d1e7d6b50e884a4b',
    'pkg/binder/controllers/bindrequest_controller.go':'5cd40ad9aee6ee762322a385a7e3f4502fce1698d9168ba89e2a3aa7d20099d6',
    'pkg/binder/plugins/gpusharing/gpu_sharing.go':'c878c833d8f2785ddfd89eccafb22c08c1d8d92e12ac9a43e41da26f10c89e88',
}
UID_PATTERN='[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
DNS_PATTERN='[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*'
NAMESPACE_PATTERN='cps-dynamic-admission-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?'
ACTOR_PATTERN='system:serviceaccount:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?:'+DNS_PATTERN
RV_PATTERN='[1-9][0-9]{0,19}'
SHA_PATTERN='[0-9a-f]{64}'
FIELDS={'podName','podUid','nodeName','capabilitiesName','capabilitiesUid','capabilitiesResourceVersion',
        'evarName','evarUid','evarResourceVersion','compiledWorkflowSha256','registryReviewSha256'}
NAMES={'podName','nodeName','capabilitiesName','evarName'}
UIDS={'podUid','capabilitiesUid','evarUid'}
RVS={'capabilitiesResourceVersion','evarResourceVersion'}
SHAS={'compiledWorkflowSha256','registryReviewSha256'}
LIMITATIONS=[
    'Disabled offline candidate only; no API-server type checking, admission request, binding or production qualification was performed',
    'Approval records are operator-attested prerequisites; canonical names, hashes, UIDs and resourceVersions are not proof of trust',
    'CEL compares only Binding namespace/name/Pod UID/target node and reviewed binder username; it performs no live cross-object ConfigMap or Workflow lookup',
    'The operator must independently validate the compiled Workflow bytes, full current Pod and complete capabilities/evar maps, then protect and update the registry',
    'No registry writer RBAC, synchronization controller, freshness deadline, revocation or API-server cache propagation is deployed',
    'Binder rollback deletes capabilities and evar maps; an asynchronous post-CREATE registry update can race binding, deletion and recreation with new ConfigMap UIDs',
    'A stale approval record does not prove its referenced ConfigMaps still exist or retain their reviewed resourceVersions; binding synchronization and invalidation remain live gates',
    'Retries are not a proved bounded backoff: the cached controller skips persisting repeated Failed-phase attempt increments; scheduler handling is unavailable in this source subset',
    'Namespace selectors scope this candidate to one isolated namespace; other namespaces and non-CREATE operations are out of scope at admission matching',
    'Literal CEL tests do not establish Kubernetes type checking, defaulting, cost budgets, authenticated creator attribution, retries or rollback correctness',
]


def literal(value):return json.dumps(value,separators=(',',':'),allow_nan=False)


def verify_source_trace(directory):
    root=Path(directory);raw=(root/'source-manifest.json').read_bytes();manifest=json.loads(raw)
    if manifest['repositories']['kai']['commit'] != KAI_COMMIT:raise ValueError('Reviewed KAI source commit required')
    receipts={entry['path']:entry for entry in manifest['files']}
    for filename,expected in SOURCE_FILES.items():
        path='kai/'+filename
        if (hashlib.sha256((root/path).read_bytes()).hexdigest() != expected
                or receipts[path]['sha256'] != expected or receipts[path]['treeShaMatch'] is not True):
            raise ValueError('Reviewed source bytes/tree receipt changed')
    return hashlib.sha256(raw).hexdigest()


def reviewed_records(records):
    if not isinstance(records,(list,tuple)) or len(records)>32:raise ValueError('At most 32 reviewed binding records required')
    result=[];pod_names=set();pod_uids=set();cm_names=set();cm_uids=set()
    for record in records:
        if not isinstance(record,dict) or set(record) != FIELDS:raise ValueError('Exact operator-attested binding record fields required')
        for field in FIELDS:
            value=record[field]
            pattern=DNS_PATTERN if field in NAMES else UID_PATTERN if field in UIDS else RV_PATTERN if field in RVS else SHA_PATTERN
            limit=253 if field in NAMES else 36 if field in UIDS else 20 if field in RVS else 64
            if not isinstance(value,str) or len(value)>limit or not re.fullmatch(pattern,value):
                raise ValueError('Canonical reviewed name/UID, positive numeric resourceVersion and SHA256 strings required')
        if (record['podName'] in pod_names or record['podUid'] in pod_uids
                or record['capabilitiesName']==record['evarName'] or record['capabilitiesUid']==record['evarUid']
                or record['podUid'] in (record['capabilitiesUid'],record['evarUid'])
                or any(record[field] in cm_names for field in ('capabilitiesName','evarName'))
                or any(record[field] in cm_uids for field in ('capabilitiesUid','evarUid'))):
            raise ValueError('Distinct Pod identities and independent ConfigMap generations required')
        pod_names.add(record['podName']);pod_uids.add(record['podUid'])
        cm_names.update(record[field] for field in ('capabilitiesName','evarName'))
        cm_uids.update(record[field] for field in ('capabilitiesUid','evarUid'))
        result.append(copy.deepcopy(record))
    return result


def build(*,namespace='cps-dynamic-admission-review',writers=(),records=()):
    if not isinstance(namespace,str) or len(namespace)>63 or not re.fullmatch(NAMESPACE_PATTERN,namespace):
        raise ValueError('Only a separate cps-dynamic-admission-* namespace is permitted')
    if (not isinstance(writers,(list,tuple)) or len(writers)>8
            or any(not isinstance(actor,str) or len(actor)>343 or not re.fullmatch(ACTOR_PATTERN,actor) for actor in writers)
            or len(set(writers)) != len(writers)):
        raise ValueError('At most eight distinct explicitly reviewed service-account usernames required')
    records=reviewed_records(records);group=namespace+'.compute.cps.unileoben.ac.at';name=namespace+'-binding'
    annotations={'compute.cps.unileoben.ac.at/qualification-state':'disabled-offline-candidate',
        'compute.cps.unileoben.ac.at/kai-source':KAI_COMMIT,
        'compute.cps.unileoben.ac.at/source-files-sha256':hashlib.sha256(literal(SOURCE_FILES).encode()).hexdigest()}
    selector={'matchLabels':{'kubernetes.io/metadata.name':namespace}}
    variables=[{'name':'records','expression':
        'has(object.metadata) && has(object.metadata.name) && has(object.metadata.uid) ? '
        'params.records.filter(r, r.podName == object.metadata.name && r.podUid == object.metadata.uid) : []'},
        {'name':'record','expression':'size(variables.records) == 1 ? variables.records[0] : {}'}]
    validations=[]
    def rule(expression,message):validations.append({'expression':expression,'message':message})
    rule('has(request.namespace) && request.namespace == '+literal(namespace),'The isolated namespace must match exactly')
    rule("has(request.operation) && request.operation == 'CREATE'",'Only a pods/binding CREATE is modelled')
    # Never place actor checks in matchConditions: unauthorized actors must deny.
    rule('has(request.userInfo) && has(request.userInfo.username) && request.userInfo.username in params.writers',
         'The authenticated binder username must be explicitly observed and approved')
    rule("has(object.apiVersion) && object.apiVersion == 'v1' && has(object.kind) && object.kind == 'Binding'",
         'Only the exact v1 Binding object is allowed')
    rule('has(object.metadata) && has(object.metadata.namespace) && object.metadata.namespace == request.namespace && '
         'has(object.metadata.name) && has(object.metadata.uid) && size(variables.records) == 1',
         'The exact reviewed namespace/name/Pod UID generation must be registered once')
    rule("has(object.target) && has(object.target.kind) && object.target.kind == 'Node' && "
         'has(object.target.name) && has(variables.record.nodeName) && object.target.name == variables.record.nodeName && '
         "(!has(object.target.apiVersion) || object.target.apiVersion == 'v1')",
         'Only the reviewed target Node name and absent-or-v1 target API version are permitted')
    prerequisite=[]
    for field in sorted(FIELDS):
        pattern=DNS_PATTERN if field in NAMES else UID_PATTERN if field in UIDS else RV_PATTERN if field in RVS else SHA_PATTERN
        limit=253 if field in NAMES else 36 if field in UIDS else 20 if field in RVS else 64
        prerequisite.extend(['has(variables.record.'+field+')','size(variables.record.'+field+') <= '+str(limit),
                             'variables.record.'+field+'.matches('+literal('^'+pattern+'$')+')'])
    prerequisite.extend(['variables.record.capabilitiesName != variables.record.evarName',
        'variables.record.capabilitiesUid != variables.record.evarUid',
        'variables.record.podUid != variables.record.capabilitiesUid','variables.record.podUid != variables.record.evarUid'])
    rule(' && '.join('('+clause+')' for clause in prerequisite),
         'A complete operator-attested ConfigMap UID/resourceVersion and Workflow/review digest record is a prerequisite, not a live lookup')
    policy={'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicy',
        'metadata':{'name':name,'annotations':copy.deepcopy(annotations)},'spec':{'failurePolicy':'Fail',
        'paramKind':{'apiVersion':group+'/v1alpha1','kind':'DynamicGpuBindingPolicy'},
        'matchConstraints':{'matchPolicy':'Exact','namespaceSelector':copy.deepcopy(selector),
            'resourceRules':[{'apiGroups':[''],'apiVersions':['v1'],'resources':['pods/binding'],
                              'operations':['CREATE'],'scope':'Namespaced'}]},
        'variables':variables,'validations':validations}}
    properties={}
    for field in FIELDS:
        pattern=DNS_PATTERN if field in NAMES else UID_PATTERN if field in UIDS else RV_PATTERN if field in RVS else SHA_PATTERN
        limit=253 if field in NAMES else 36 if field in UIDS else 20 if field in RVS else 64
        properties[field]={'type':'string','pattern':'^'+pattern+'$','maxLength':limit}
    record_schema={'type':'object','required':sorted(FIELDS),'properties':properties,'x-kubernetes-validations':[
        {'rule':'self.capabilitiesName != self.evarName','message':'Independent ConfigMap names required'},
        {'rule':'self.capabilitiesUid != self.evarUid && self.podUid != self.capabilitiesUid && self.podUid != self.evarUid',
         'message':'Independent Pod and ConfigMap UID generations required'}]}
    crd={'apiVersion':'apiextensions.k8s.io/v1','kind':'CustomResourceDefinition',
        'metadata':{'name':'dynamicgpubindingpolicies.'+group,'annotations':copy.deepcopy(annotations)},
        'spec':{'group':group,'scope':'Namespaced','names':{'kind':'DynamicGpuBindingPolicy',
            'plural':'dynamicgpubindingpolicies','singular':'dynamicgpubindingpolicy'},'versions':[{
            'name':'v1alpha1','served':True,'storage':True,'schema':{'openAPIV3Schema':{
                'type':'object','required':['writers','records'],'properties':{
                    'writers':{'type':'array','maxItems':8,'x-kubernetes-list-type':'set',
                        'items':{'type':'string','maxLength':343,'pattern':'^'+ACTOR_PATTERN+'$'}},
                    'records':{'type':'array','maxItems':32,'x-kubernetes-list-type':'map',
                        'x-kubernetes-list-map-keys':['podName','podUid'],'items':record_schema}}}}}]}}
    params={'apiVersion':group+'/v1alpha1','kind':'DynamicGpuBindingPolicy',
        'metadata':{'name':'reviewed-bindings','namespace':namespace,'annotations':copy.deepcopy(annotations)},
        'writers':list(writers),'records':records}
    binding={'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicyBinding',
        'metadata':{'name':name,'annotations':copy.deepcopy(annotations)},'spec':{'policyName':name,
            'validationActions':['Deny'],'matchResources':{'namespaceSelector':copy.deepcopy(selector)},
            'paramRef':{'name':'reviewed-bindings','namespace':namespace,'parameterNotFoundAction':'Deny'}}}
    return {'apiVersion':'v1','kind':'List','items':[crd,params,policy,binding]}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--namespace',default='cps-dynamic-admission-review')
    parser.add_argument('--registry',type=Path,help='Explicit operator-attested JSON writers/records; omitted denies all')
    parser.add_argument('--source-trace',type=Path,help='Optionally verify reviewed cached upstream source receipts')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();registry=json.loads(args.registry.read_text()) if args.registry else {}
    if not isinstance(registry,dict) or set(registry)-{'writers','records'}:parser.error('Only writers/records registry fields are allowed')
    source_sha=verify_source_trace(args.source_trace) if args.source_trace else None
    manifest=build(namespace=args.namespace,writers=registry.get('writers',[]),records=registry.get('records',[]))
    import yaml
    with args.output.open('x') as output:yaml.safe_dump_all(manifest['items'],output,sort_keys=False)
    print(json.dumps({'status':'offline-candidate-rendered','applied':False,'liveBindingQualified':False,
        'liveRegistryFreshnessQualified':False,'liveRetryRollbackQualified':False,'productionQualified':False,
        'kaiSourceCommit':KAI_COMMIT,'sourceTraceSha256':source_sha,
        'manifestSha256':hashlib.sha256(literal(manifest).encode()).hexdigest(),'limitations':LIMITATIONS}))
