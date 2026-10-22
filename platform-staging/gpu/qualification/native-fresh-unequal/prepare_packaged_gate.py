#!/usr/bin/env python3
"""Default-inert fresh fixed5/10 fixture using the published installed147 SDK gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import types
import uuid

HERE=Path(__file__).resolve().parent
PRODUCER_SHA='a35c0778bba76b0ca840216d585ef850cefb2313af7d1ca2ad6fb3c2688a019b'
OLD_COHORT='a9fc091b-f388-4f21-8771-b6ae7b4734dc'
GATE_IMAGE='ghcr.io/mul-cps/cps-native-node@sha256:81aac20157965ed5503b0d208b0326fef1ba10d71089d9e635128cea48dafe82'
POLICY='sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281'
RUNTIME_SHA='035fa64027c09965fcb7557f4346b449b637aa39de804a94565deffe067b0e74'
HEALTH_SHA='fc9dd634b8a31c15939cf6ddf3b18e84b9fa5a60d21424831a410a5ba4322fe8'


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def replace(source,old,new,count=1):
    require(source.count(old)==count,'Exact reviewed packaged-gate adaptation span changed: '+old[:80])
    return source.replace(old,new)


def unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate JSON key denied');result[key]=value
    return result


def load(name,raw):
    module=types.ModuleType('packaged_'+name.replace('.','_'));module.__file__=str(HERE/name)
    exec(compile(raw,module.__file__,'exec'),module.__dict__);return module


def build_sources(cohort):
    require(type(cohort)is str and str(uuid.UUID(cohort))==cohort and uuid.UUID(cohort).int>0
            and cohort!=OLD_COHORT,'Distinct reviewed canonical new packaged cohort required')
    raw=(HERE/'prepare.py').read_bytes()
    require(sha(raw)==PRODUCER_SHA,'Exact frozen unequal producer required before execution')
    original=load('prepare.py',raw).build_sources('5-10')
    out={name:content.decode() for name,content in original.items()}
    for name in ('render_fixture.py','controller.py','fresh_preflight.py'):
        out[name]=replace(out[name],OLD_COHORT,cohort)
    r=out['render_fixture.py']
    r=replace(r,"    data = sources()\n    state = qa_state(request)\n    cm_name = 'cps-native-qa-gate-' + hashlib.sha256(encoded(data)).hexdigest()[:16]\n    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,\n          'metadata': {'namespace': NAMESPACE, 'name': cm_name}, 'data': data}",
        "    sources()  # Local compiler pins; the Pod imports only its installed SDK.\n    require(request['gate_image']=="+repr(GATE_IMAGE)+" and request['policy_hash']=="+repr(POLICY)+", 'Exact published147 gate and actual Source332 policy required')\n    state = qa_state(request)\n    cm = None")
    r=replace(r,"        pod['spec']['volumes'].append({'name': 'qa-gate-package', 'configMap': {'name': cm_name, 'defaultMode': 0o444,\n            'items': [{'key': name, 'path': 'cps_compute/' + name} for name in data]}})\n        gate = pod['spec']['initContainers'][0]\n        gate['command'] = ['python', '-I', '-S', '-c', GATE_LAUNCH]\n        gate['volumeMounts'].append({'name': 'qa-gate-package', 'mountPath': '/opt/cps-qa', 'readOnly': True})\n",'')
    r=replace(r,"    if args.prepare:\n        documents.update({'gate-source.configmap.json': result['source_configmap'],\n                          **{key + '.proposed.json': value for key, value in result['pods'].items()}})",
        "    if args.prepare:\n        documents.update({key + '.proposed.json': value for key, value in result['pods'].items()})")
    out['render_fixture.py']=r
    c=out['controller.py']
    c=replace(c,'record.intent.gpu_uuid==GPU and record.intent.cap_mib==5120',
        'record.intent.gpu_uuid==GPU and record.intent.cap_mib in (5120,10240)')
    out['controller.py']=c
    out['observe.py']=replace(out['observe.py'],sha(original['controller.py']),sha(c.encode()))
    result={name:content.encode() for name,content in out.items()}
    for name,content in result.items():compile(content,name,'exec')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--inputs',type=Path);p.add_argument('--inputs-sha256');p.add_argument('--output',type=Path)
    p.add_argument('--approve-qa-hostpaths',action='store_true');args=p.parse_args(argv)
    if not args.prepare:print(json.dumps({'inert':True,'api_calls':False,'gpu_calls':False}));return
    require(args.inputs and args.inputs_sha256 and args.output and args.approve_qa_hostpaths,
            'Pinned request, exclusive output and explicit Root QA hostpath approval required')
    raw=args.inputs.read_bytes();require(0<len(raw)<=65536 and sha(raw)==args.inputs_sha256,'Reviewed exact request raw bytes required')
    request=json.loads(raw,object_pairs_hook=unique)
    require(type(request)is dict,'Closed request required')
    sources=build_sources(request.get('cohort_uid'));renderer=load('render_fixture.py',sources['render_fixture.py'])
    review=renderer.render(request,approve_qa_hostpaths=True)
    receipt={'version':1,'state':'prepared-awaiting-Root-execution','producer_sha256':PRODUCER_SHA,
        'generated_sha256':{name:sha(content) for name,content in sources.items()},'request_raw_sha256':sha(raw),
        'gate_image':GATE_IMAGE,'installed_runtime_sha256':RUNTIME_SHA,'installed_health_sha256':HEALTH_SHA,
        'policy_hash':POLICY,'cohort_uid':request['cohort_uid'],'pair':'5-10',
        'profile_caps':{'a':5120,'b':10240},'budget_mib':15360,'hardware_qualified':False,'production_qualified':False}
    documents={'preparation.json':receipt,'review.json':review,'inputs.json':request,
        **{key+'.proposed.json':pod for key,pod in review['pods'].items()}}
    args.output.mkdir(mode=0o700)
    for name,content in {**sources,**{name:(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
                                    for name,value in documents.items()}}.items():
        fd=os.open(args.output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(content)
    print(json.dumps({'prepared':True,'output':str(args.output),'api_calls':False,'gpu_calls':False}))


if __name__=='__main__':main()
