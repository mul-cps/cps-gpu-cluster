#!/usr/bin/env python3
"""Offline only: exact paired v2 cutover and separate operator10 proposal."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:8c2c456b90330622645d509f94882a11a465ac208a6fa7fc824900d6320e5c0b'
BASE_DIGEST = 'sha256:5079458fe0fcb3c11231b21f1bbc1f4c12ad3ac578799932aa0bc9f46d5510c7'
APPROVAL_FLAGS = ('--approval-reference', '--approval-template', '--approval-process', '--approval-acknowledgment')


def need(ok, text):
    if not ok:
        raise ValueError(text)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def guard(obj, kind):
    meta = obj.get('metadata', {})
    need(obj.get('kind') == kind and all(isinstance(meta.get(k), str) and meta[k]
         for k in ('name', 'namespace', 'uid', 'resourceVersion'))
         and not meta.get('deletionTimestamp'), 'Actual current owned object required')
    return meta


def patch(deployment, expected, replacement):
    meta = guard(deployment, 'Deployment')
    return [{'op': 'test', 'path': '/metadata/uid', 'value': meta['uid']},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': meta['resourceVersion']},
            {'op': 'test', 'path': '/spec', 'value': expected},
            {'op': 'replace', 'path': '/spec', 'value': replacement}]


def inverse(current, receipt):
    guard(current, 'Deployment')
    need(current['metadata']['uid'] == receipt['deployment_uid']
         and current['spec'] == receipt['after_spec'], 'Fresh exact prospective spec required for inverse')
    return patch(current, current['spec'], receipt['before_spec'])


def v2(deployment, code, bootstrap):
    meta = guard(deployment, 'Deployment'); guard(code, 'ConfigMap'); guard(bootstrap, 'ConfigMap')
    need(meta['namespace'] == 'cps-native-system' and meta['name'] == 'cps-native-node-agent', 'Exact Node controller required')
    need(code.get('immutable') is True and bootstrap.get('immutable') is True
         and not code.get('binaryData') and not bootstrap.get('binaryData')
         and not code['metadata'].get('ownerReferences') and not bootstrap['metadata'].get('ownerReferences'),
         'Retained immutable code/bootstrap required')
    before = copy.deepcopy(deployment['spec']); after = copy.deepcopy(before)
    pod = after['template']['spec']; containers = pod['containers']
    need(len(containers) == 1 and containers[0]['name'] == 'node-agent', 'One exact existing Node container required')
    container = containers[0]
    need(container['image'].endswith('@' + BASE_DIGEST)
         and container['command'] == ['python3', '/opt/native/node_agent.py']
         and all(container['args'].count(flag) == 1 for flag in APPROVAL_FLAGS)
         and '--operator-epoch-config' not in container['args'], 'Current exact507 v2 route required')
    mounts = [m for m in container['volumeMounts'] if m['name'] == 'code']
    volumes = [v for v in pod['volumes'] if v['name'] == 'code']
    need(len(mounts) == len(volumes) == 1 and mounts[0]['mountPath'] == '/opt/native'
         and mounts[0].get('readOnly') is True
         and volumes[0]['configMap']['name'] == code['metadata']['name'], 'Exact masking code projection required')
    need(hashlib.sha256(code['data']['node_agent.py'].encode()).hexdigest()
         == 'b1deccd3e48b8c38ec0c87416dc04d9ae860e260910ff929f697be5d17e14429', 'Actual reviewed source preimage required')
    bundle = Path(__file__).parent / 'bundle'
    need(set(code['data']) == {p.name for p in bundle.iterdir()} - {'native_operator_epoch.py'}
         and all(v.encode() == (bundle / k).read_bytes() for k, v in code['data'].items() if k != 'node_agent.py'),
         'Every retained original helper must match tested image bytes')
    old_process = json.loads(bootstrap['data']['process.json'])
    need(old_process['image'] == container['image'] and old_process['uid'] == meta['uid']
         and old_process['name'] == meta['name'] and old_process['namespace'] == meta['namespace']
         and old_process['service_account'] == pod['serviceAccountName'], 'Actual old signed process pin must match controller')
    data = copy.deepcopy(bootstrap['data']); process = dict(old_process, image=IMAGE)
    data['process.json'] = encoded(process)
    name = 'cps-native-approval-bootstrap-' + digest(data)[:16]
    proposal = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name, 'namespace': meta['namespace']},
                'immutable': True, 'data': data}
    references = [v for v in pod['volumes'] if v.get('configMap', {}).get('name') == bootstrap['metadata']['name']]
    need(len(references) == 1, 'One exact bootstrap reference required')
    references[0]['configMap']['name'] = name
    container['image'] = IMAGE
    container['volumeMounts'] = [m for m in container['volumeMounts'] if m['name'] != 'code']
    pod['volumes'] = [v for v in pod['volumes'] if v['name'] != 'code']
    return {'version': 1, 'enabled': False, 'live_applied': False, 'kind': 'retained-v2-image-code-bootstrap-cutover',
            'deployment_uid': meta['uid'], 'before_spec': before, 'after_spec': after,
            'before_spec_sha256': digest(before), 'after_spec_sha256': digest(after),
            'create_bootstrap': proposal, 'patch': patch(deployment, before, after),
            'retained_configmap_refs': [v['configMap']['name'] for v in pod['volumes'] if 'configMap' in v],
            'required_gates': ['normal Source closed and no active native/scheduled/unmanaged GPU consumers',
                'fresh ledger empty/terminal history/reservation and enrollment custody reconciled',
                'new immutable bootstrap CREATE UID/RV/full-data readback matches proposal',
                'actual new Pod/ReplicaSet readback then exact-name existing Role UID/RV/full-rules CAS',
                'controller Ready exact image/UID/current generation and fresh actual v2 node ACK',
                'all four actual approval ACKs current; no fabricated generation or expiry release'],
            'operator_enabled': False, 'hardware_qualified': False}


def operator(deployment, node_config, settings, target, service_account, old_config):
    """Requires genuine CREATE readbacks; never manufactures UID/RV authority."""
    meta = guard(deployment, 'Deployment')
    for obj, kind in ((node_config, 'ConfigMap'), (settings, 'ConfigMap'), (target, 'ConfigMap'),
                      (service_account, 'ServiceAccount'), (old_config, 'ConfigMap')):
        guard(obj, kind)
    need(node_config.get('immutable') is True and settings.get('immutable') is True
         and target.get('immutable') in (None, False) and target['data'] == {'epoch.json': '{}'}
         and target['metadata']['name'] == 'cps-native-kai-epoch-node', 'Dedicated actual empty operator ACK required')
    config = json.loads(node_config['data']['config.json']); old = json.loads(old_config['data']['config.json'])
    need(set(config) == {'version','enabled','mode','authority_namespace','policy_hash','pool','workspaces','terminal_history'}
         and config['version'] == 2 and config['enabled'] is True and config['mode'] == 'operator-qualification'
         and config['authority_namespace'] == meta['namespace'] and config['pool'] == old['pool']
         and config['terminal_history'] == old['terminal_history']
         and config['workspaces'] == {'cit:native-group-a': {'profile': 'interactive-native-qualification-10','cap_mib': 10240}},
         'Only exact controlled10 with complete retained current epoch/history required')
    cfg = json.loads(settings['data']['settings.json']); process = cfg['process']
    need(set(cfg) == {'enabled','version','target','node_configuration','process','ttlSeconds'}
         and cfg['enabled'] is True and cfg['version'] == 1 and type(cfg['ttlSeconds']) is int and cfg['ttlSeconds'] == 30,
         'Closed thirty-second private operator settings required')
    need(cfg['node_configuration'] == {**{k: node_config['metadata'][k] for k in ('name','namespace','uid','resourceVersion')},
         'data_sha256': 'sha256:' + digest(node_config['data'])}
         and cfg['target'] == {k: target['metadata'][k] for k in ('name','namespace','uid')}, 'Actual created target/config UID/RV/data required')
    before = copy.deepcopy(deployment['spec']); after = copy.deepcopy(before); pod = after['template']['spec']; container = pod['containers'][0]
    need(len(pod['containers']) == 1 and container['image'] == IMAGE
         and not any(m['mountPath'] == '/opt/native' for m in container['volumeMounts'])
         and not pod.get('initContainers') and '--operator-epoch-config' not in container['args'], 'Tested unmasked retained-v2 prerequisite required')
    need(process == {'kind':'Deployment','name':meta['name'],'namespace':meta['namespace'],'uid':meta['uid'],
          'container':container['name'],'image':IMAGE,'service_account':pod['serviceAccountName'],
          'service_account_uid':service_account['metadata']['uid']}
         and service_account['metadata']['name'] == pod['serviceAccountName']
         and service_account['metadata']['namespace'] == meta['namespace'], 'Actual signed current Node SA and controller required')
    remove_names = {m['name'] for m in container['volumeMounts'] if m['mountPath'].startswith('/var/run/cps-native-approvals/')}
    args = list(container['args'])
    for flag in APPROVAL_FLAGS:
        need(args.count(flag) == 1, 'Every previous dynamic v2 flag required'); i = args.index(flag); del args[i:i+2]
    args += ['--operator-epoch-config', '/var/run/cps-native-operator/settings.json']; container['args'] = args
    container['volumeMounts'] = [m for m in container['volumeMounts'] if m['name'] not in remove_names]
    pod['volumes'] = [v for v in pod['volumes'] if v['name'] not in remove_names]
    refs = [v for v in pod['volumes'] if v['name'] == 'config']
    need(len(refs) == 1 and refs[0]['configMap']['name'] == old_config['metadata']['name'], 'Exact old node configuration reference required')
    refs[0]['configMap']['name'] = node_config['metadata']['name']
    env = container.setdefault('env', [])
    need(not any(v['name'].startswith('CPS_NATIVE_OPERATOR_') for v in env), 'No prior operator identity overrides allowed')
    for suffix, field in [('NAME','metadata.name'), ('UID','metadata.uid'), ('NAMESPACE','metadata.namespace')]:
        env.append({'name':'CPS_NATIVE_OPERATOR_POD_'+suffix, 'valueFrom':{'fieldRef':{'fieldPath':field}}})
    raw = settings['data']['settings.json']; raw_sha = hashlib.sha256(raw.encode()).hexdigest()
    copy_code = ("import hashlib,os,pathlib; p=pathlib.Path('/operator-input/settings.json'); b=p.read_bytes(); "
                 "assert hashlib.sha256(b).hexdigest()=="+repr(raw_sha)+"; os.chmod('/operator-private',0o700); "
                 "f=os.open('/operator-private/settings.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600); "
                 "os.write(f,b); os.fsync(f); os.close(f)")
    pod['volumes'] += [{'name':'operator-settings-input','configMap':{'name':settings['metadata']['name'],'defaultMode':256}},
                      {'name':'operator-settings-private','emptyDir':{'medium':'Memory','sizeLimit':'1Mi'}}]
    container['volumeMounts'].append({'name':'operator-settings-private','mountPath':'/var/run/cps-native-operator','readOnly':True})
    pod['initContainers'] = [{'name':'materialize-operator-settings','image':IMAGE,'command':['python3','-c',copy_code],
        'securityContext':{'runAsUser':0,'runAsGroup':0,'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
        'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'cpu':'100m','memory':'64Mi'}},
        'volumeMounts':[{'name':'operator-settings-input','mountPath':'/operator-input','readOnly':True},
                        {'name':'operator-settings-private','mountPath':'/operator-private'}]}]
    return {'version':1,'enabled':False,'live_applied':False,'kind':'mutually-exclusive-operator10-cutover',
        'deployment_uid':meta['uid'],'before_spec':before,'after_spec':after,'patch':patch(deployment,before,after),
        'settings_raw_sha256':raw_sha,'materialize_command':copy_code,'operator_profile':'interactive-native-qualification-10',
        'required_gates':['approved coordinated whole-catalog compiler/policy/inverse and current policy hash',
           'Gateway/Hub pending58 consumer reconciled with current7d CPU/neutral fixes',
           'maintenance no-writers and native-zero/current no-Pod/no-reservation/enrollment custody',
           'all desired ConfigMaps actual CREATE readback and reviewed exact node SA RBAC patch',
           'fresh operator node ACK observed by reconciled Gateway; existing v2 ACK explicitly retired only during fence',
           'normal audited Source Start/Close with measured post-Bind NodeUID/CRI/cgroup/CDI/cap-before-CUDA',
           'normal exact cleanup/native-zero then fresh inverse and all four original v2 ACKs'],
        'hardware_qualified':False}


def operator_creates(old_config, qualification):
    """Use the single reviewed764 qualification catalog; retain current history."""
    meta=guard(old_config,'ConfigMap');old=json.loads(old_config['data']['config.json'])
    packet=Path(__file__).parent.parent/'native-kai-v1-qualification'/'operator-qualification.json'
    need(qualification==json.loads(packet.read_text()),'Exact single-authority reviewed764 qualification document required')
    need(qualification['version']==1 and qualification['operator_only'] is True
         and qualification['profile_caps']=={'interactive-native-qualification-10':10240}
         and set(qualification['workspaces'])=={'cit:native-group-a'}
         and qualification['node_pool']==old['pool'],'Frozen qualification epoch/pool must match actual retained node config')
    config=copy.deepcopy(old);config.update(version=2,mode='operator-qualification',
        policy_hash=qualification['policy_hash'],workspaces={'cit:native-group-a':{
            'profile':'interactive-native-qualification-10','cap_mib':10240}})
    need(config['enabled'] is True and config['authority_namespace']==meta['namespace'],'Current enabled exact authority required')
    data={'config.json':encoded(config)}
    return {'version':1,'enabled':False,'live_applied':False,'qualification_sha256':digest(qualification),
        'retained_terminal_history_sha256':digest(old['terminal_history']),
        'create_node_config':{'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'cps-native-kai-node-config-'+digest(data)[:16],
            'namespace':meta['namespace']},'immutable':True,'data':data},
        'create_epoch_target':{'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'cps-native-kai-epoch-node',
            'namespace':meta['namespace']},'data':{'epoch.json':'{}'}},
        'required_before_create':'fresh no-custody maintenance fence and approved whole-catalog compiler/policy/inverse'}


def operator_settings(deployment,node_config,target,service_account):
    dm=guard(deployment,'Deployment');nm=guard(node_config,'ConfigMap');tm=guard(target,'ConfigMap');sm=guard(service_account,'ServiceAccount')
    need(node_config.get('immutable') is True and target.get('immutable') in (None,False)
         and target['data']=={'epoch.json':'{}'} and tm['name']=='cps-native-kai-epoch-node'
         and all(m['namespace']==dm['namespace'] for m in (nm,tm,sm)), 'Actual created dedicated operator objects required')
    p=deployment['spec']['template']['spec'];c=p['containers'][0]
    need(c['image']==IMAGE and c['name']=='node-agent' and sm['name']==p['serviceAccountName'],'Actual candidate controller/SA required')
    config={'enabled':True,'version':1,'ttlSeconds':30,
        'target':{k:tm[k] for k in ('namespace','name','uid')},
        'node_configuration':{**{k:nm[k] for k in ('namespace','name','uid','resourceVersion')},'data_sha256':'sha256:'+digest(node_config['data'])},
        'process':{'kind':'Deployment','name':dm['name'],'namespace':dm['namespace'],'uid':dm['uid'],
            'container':c['name'],'image':IMAGE,'service_account':sm['name'],'service_account_uid':sm['uid']}}
    data={'settings.json':encoded(config)}
    return {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'cps-native-kai-node-settings-'+digest(data)[:16],
        'namespace':dm['namespace']},'immutable':True,'data':data}


def process_rbac(deployment, role, pod, replica_set, operator_mode=False):
    """Stage after genuine controller-created Pod/RS readback, no guessed names."""
    dm=guard(deployment,'Deployment'); rm=guard(role,'Role'); pm=guard(pod,'Pod'); sm=guard(replica_set,'ReplicaSet')
    need(rm['name']=='cps-native-approval-node' and all(m['namespace']==dm['namespace'] for m in (rm,pm,sm)),
         'Exact existing namespace Role required')
    def owner(meta,kind,uid):
        refs=meta.get('ownerReferences',[])
        return len(refs)==1 and refs[0].get('kind')==kind and refs[0].get('uid')==uid and refs[0].get('controller') is True
    need(owner(pm,'ReplicaSet',sm['uid']) and owner(sm,'Deployment',dm['uid'])
         and replica_set['spec']['template']==deployment['spec']['template'], 'Actual current controller ownership/template required')
    dc=deployment['spec']['template']['spec'];pc=pod['spec']
    need(len(pc['containers'])==1 and pc['containers'][0]['name']=='node-agent'
         and pc['containers'][0]['image']==IMAGE and dc['containers'][0]['image']==IMAGE
         and pc['serviceAccountName']==dc['serviceAccountName'], 'Actual exact candidate process required')
    before=copy.deepcopy(role['rules']);after=copy.deepcopy(before)
    for group,resource,name in [('', 'pods',pm['name']),('apps','replicasets',sm['name'])]:
        matches=[r for r in after if r.get('apiGroups')==[group] and r.get('resources')==[resource] and r.get('verbs')==['get']]
        need(len(matches)==1 and len(matches[0].get('resourceNames',[]))==1,'One existing exact-name process permission required')
        matches[0]['resourceNames']=[name]
    if operator_mode:
        matches=[r for r in after if r.get('apiGroups')==[''] and r.get('resources')==['configmaps'] and r.get('verbs')==['patch']]
        need(len(matches)==1 and matches[0].get('resourceNames')==['cps-native-approval-ack-node'], 'Exact old v2 ACK writer required')
        matches[0]['resourceNames']=['cps-native-kai-epoch-node']
        need(not any('serviceaccounts' in r.get('resources',[]) for r in after), 'No prior SA permission adoption')
        after.append({'apiGroups':[''],'resources':['serviceaccounts'],'resourceNames':[dc['serviceAccountName']],'verbs':['get']})
    return {'version':1,'enabled':False,'live_applied':False,'role_uid':rm['uid'],'before_rules':before,'after_rules':after,
        'observed_pod':{k:pm[k] for k in ('name','namespace','uid','resourceVersion')},
        'observed_replica_set':{k:sm[k] for k in ('name','namespace','uid','resourceVersion')},
        'patch':[{'op':'test','path':'/metadata/uid','value':rm['uid']},
                 {'op':'test','path':'/metadata/resourceVersion','value':rm['resourceVersion']},
                 {'op':'test','path':'/rules','value':before},{'op':'replace','path':'/rules','value':after}],
        'inverse_requires_fresh_role_rv_and_exact_after_rules':True,'no_broad_pod_rs_get':True}


def main():
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['v2','operator','inverse','process-rbac','operator-creates','operator-settings'])
    p.add_argument('--inputs', required=True); p.add_argument('--output', required=True); args=p.parse_args()
    data=json.loads(Path(args.inputs).read_text())
    functions={'v2':v2,'operator':operator,'inverse':inverse,'process-rbac':process_rbac,
        'operator-creates':operator_creates,'operator-settings':operator_settings}
    result=functions[args.mode](**data)
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
