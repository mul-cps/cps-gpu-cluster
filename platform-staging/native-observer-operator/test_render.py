"""Pure synthetic release rendering; no Kubernetes/GPU/network operations."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE=Path(__file__).resolve().parent


def module():
    spec=importlib.util.spec_from_file_location('observer_render',HERE/'render.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def fixture():
    pytest.importorskip('cps_compute.native_observer_permissions')
    return json.loads((HERE/'synthetic-fixture.json').read_text())


def render(value=None,**kwargs):
    mod=module();v=value or fixture()
    return mod.render(v['release'],mod.digest(v['release']),v['policy'],v['capture'],
                      'registry.example/operator@sha256:'+'b'*64,**kwargs)


def test_default_cli_is_inert_without_sdk_or_file_reads():
    result=subprocess.run([sys.executable,'-I',str(HERE/'render.py')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'state':'inert','api_writes':False,'files_written':False}


def test_manifest_default_is_inert_and_dedicated_nonroot_inputs_are_regular_subpaths():
    docs=render();dep=next(x for x in docs if x['kind']=='Deployment')
    spec=dep['spec']['template']['spec'];container=spec['containers'][0]
    assert dep['spec']['replicas']==0 and '--execute' not in container['args']
    assert spec['securityContext']=={'runAsUser':10001,'runAsGroup':10001,'runAsNonRoot':True}
    assert container['securityContext']['readOnlyRootFilesystem'] is True
    assert container['securityContext']['allowPrivilegeEscalation'] is False
    assert all(x['subPath'] in ('release.json','policy.json') and x['readOnly'] for x in container['volumeMounts'])
    assert spec['volumes'][0]['configMap']['defaultMode']==0o444
    cm=next(x for x in docs if x['kind']=='ConfigMap')
    assert cm['immutable'] is True and set(cm['data'])=={'release.json','policy.json'}
    assert len([x for x in docs if x['kind']=='ServiceAccount'])==1
    assert render(activate=True)[-1]['spec']['replicas']==1
    assert '--execute' in render(activate=True)[-1]['spec']['template']['spec']['containers'][0]['args']


def test_only_seven_named_role_privileges_and_controller_namespace_reads():
    f=fixture();docs=render(f)
    roles=[x for x in docs if x['kind']=='Role'];assert len(roles)==4
    targets=set()
    for role in roles:
        ns=role['metadata']['namespace']
        assert ns in {x['namespace'] for x in f['release']['roles']}
        for row in role['rules']:
            assert '*' not in json.dumps(row)
            assert 'secrets' not in row['resources']
            if row['resources']==['roles']:
                assert row['verbs']==['get','patch','escalate']
                targets.update((ns,n) for n in row['resourceNames'])
            else:
                assert set(row['verbs']) <= {'get','list'}
                if row['resources']==['pods']:assert row['verbs']==['get','list'] and 'resourceNames' not in row
                elif row['resources']==['replicasets']:assert row['verbs']==['get'] and 'resourceNames' not in row
                else:assert row['resourceNames']
    assert targets=={(r['namespace'],r['name']) for r in f['release']['roles']}
    for binding in [x for x in docs if x['kind']=='RoleBinding']:
        assert binding['subjects']==[{'kind':'ServiceAccount','name':'cps-native-observer-operator',
                                      'namespace':f['release']['node_configuration']['namespace']}]


@pytest.mark.parametrize('change',['hash','image','target','uid','write','ref','deployment_uid','template_pin','extra_capture'])
def test_tampering_cannot_produce_manifest(change):
    f=fixture();m=module();expected=m.digest(f['release']);image='registry.example/operator@sha256:'+'b'*64
    if change=='hash':expected='sha256:'+'c'*64
    elif change=='image':image='registry.example/operator:latest'
    elif change=='target':f['release']['roles'][0]['name']='unexpected';expected=m.digest(f['release'])
    elif change=='uid':f['capture']['roles'][0]['metadata']['uid']='44444444-4444-4444-8444-444444444444'
    elif change=='write':f['release']['roles'][0]['rules'][0]['verbs']=['create'];expected=m.digest(f['release'])
    elif change=='ref':f['release']['node_configuration']['resourceVersion']='999';expected=m.digest(f['release'])
    elif change=='deployment_uid':f['capture']['deployments'][0]['metadata']['uid']='44444444-4444-4444-8444-444444444444'
    elif change=='template_pin':f['release']['held_node_template_sha256']='sha256:'+'d'*64;expected=m.digest(f['release'])
    else:f['capture']['extra']=True
    with pytest.raises(ValueError):m.render(f['release'],expected,f['policy'],f['capture'],image)


def test_api_added_rules_never_become_trusted_baseline():
    f=fixture();f['capture']['roles'][0]['rules'][0]['resourceNames'].append('forged-cm')
    with pytest.raises(ValueError,match='baseline'):render(f)
    f=fixture();f['capture']['roles'][0]['rules'][1]['resourceNames'].append('unexplained-dynamic-pod')
    docs=render(f)
    release=json.loads(next(x for x in docs if x['kind']=='ConfigMap')['data']['release.json'])
    assert release==f['release']
    assert 'unexplained-dynamic-pod' not in json.dumps(release)


def test_reviewed_held_pin_is_optional_but_exact_when_present():
    f=fixture();m=module();node_ns=f['release']['node_configuration']['namespace']
    dep=next(x for x in f['capture']['deployments'] if x['metadata']['namespace']==node_ns)
    f['release']['held_node_template_sha256']=m.digest(dep['spec']['template'])
    docs=render(f)
    assert json.loads(docs[0]['data']['release.json'])['held_node_template_sha256']==f['release']['held_node_template_sha256']


def test_full_cli_renders_only_after_reviewed_hash_and_explicit_flag(tmp_path):
    import os
    f=fixture();paths={}
    for key in ('release','policy','capture'):
        paths[key]=tmp_path/(key+'.json');paths[key].write_text(json.dumps(f[key]))
    command=[sys.executable,str(HERE/'render.py'),'--render','--release',str(paths['release']),
             '--reviewed-sha256',module().digest(f['release']),'--policy',str(paths['policy']),
             '--capture',str(paths['capture']),'--image','registry.example/operator@sha256:'+'b'*64]
    result=subprocess.run(command,env=os.environ.copy(),capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    manifest=json.loads(result.stdout)
    assert manifest['kind']=='List' and len(manifest['items'])==11
    assert manifest['items'][-1]['spec']['replicas']==0
    assert sorted(p.name for p in tmp_path.iterdir())==['capture.json','policy.json','release.json']
    paths['release'].write_text(paths['release'].read_text().replace('baseline-pod','tampered-pod'))
    blocked=subprocess.run(command,env=os.environ.copy(),capture_output=True,text=True)
    assert blocked.returncode!=0 and blocked.stdout==''
    assert 'baseline hash mismatch' in blocked.stderr


@pytest.mark.parametrize('raw',['{"version":1,"version":1}','{"version":NaN}'])
def test_duplicate_or_nonfinite_release_cannot_be_read(raw):
    with pytest.raises(ValueError):module().document(raw)
