"""Real CPS-pair proposal and released qualification installer; no Hub access."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import yaml
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent))
from test_gateway_transition import fixture as gateway_fixture, uid
import test_current_group_configuration_intent as current_fixture
import qualification_transition_proposal as transition


def tool():
    path=HERE/'hub_transition.py'
    assert path.exists(), 'CPS-only qualification Hub transition is required'
    spec=importlib.util.spec_from_file_location('prospective_hub_transition',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def fixture():
    gateway=gateway_fixture();runtime=json.loads(base64.b64decode(gateway['originals']['runtime']['data']['runtime.json']))
    group=runtime['nativeGpuGroups'];approved={k:v for k,v in group['workspaces'].items() if k.startswith('cps:')}
    settings=dict(enabled=True,source='cps',policyPath='/etc/cps-native-hub/policy.json',gatewayUrl='https://compute-gateway.cps-compute.svc.cluster.local:8000',
        gatewayCAFile='/etc/cps-native-hub/gateway-ca.crt',serviceTokenEnv='CPS_NATIVE_HUB_TOKEN',profiles=['interactive-cpu','interactive-shared-5'],
        workspaces=sorted(approved),owners=sorted(v['owner'] for v in approved.values()),gateImage=group['gateImage'],workloadImages=[group['workloadImage']],
        writablePVCClaims=sorted(v['storage']['pvc'] for v in approved.values()),writableMountPaths=['/workspace'],readonlyNFS=[],groupShareTokenCompatibility=True,
        groupDeployment=group,qualificationDeployment={'enabled':False},pilotDeployment={'enabled':False})
    config=dict(apiVersion='v1',kind='ConfigMap',immutable=True,metadata=dict(namespace='jupyterhub',name='original-native-config',uid=uid(301),resourceVersion='3'),
        data={'settings.json':transition.canonical(settings),'policy.json':gateway['originals']['policy']['data']['policy.json'],'unrelated':'preserved'})
    secret=current_fixture.CurrentConfigurationTest().hub_secrets()['cps']
    deployment=dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(namespace='jupyterhub',name='hub',uid=uid(302),resourceVersion='4'),
        spec=dict(replicas=1,template=dict(metadata={'annotations':{'other':'preserved'}},spec=dict(containers=[dict(name='hub',image='registry.example/hub@sha256:'+'e'*64)],
            volumes=[dict(name='native',configMap={'name':config['metadata']['name']}),dict(name='hub-secret',secret={'secretName':'hub'})]))))
    return dict(gateway_inputs=gateway,originals=dict(config=config,secret=secret,deployment=deployment))


def test_cps_hub_forward_installs_actual_two_target_capabilities_and_preserves_personal_settings(monkeypatch):
    args=fixture();before=copy.deepcopy(args);result=tool().forward_intent(**args)
    config=result['configuration.json'];settings=json.loads(config['data']['settings.json'])
    mode=args['gateway_inputs']['proposal']['operator-qualification.json']
    assert settings['profiles']==['interactive-native-qualification-20','interactive-native-qualification-5']
    assert len(settings['owners'])==len(settings['writablePVCClaims'])==2
    from cps_compute_hub import native_hub_config as released
    monkeypatch.setattr(released,'_read_json',lambda *a:args['gateway_inputs']['proposal']['policy.json'])
    installed=[]
    monkeypatch.setattr(released,'_install_native_hub_configuration',lambda c,plain,**kw:installed.append((plain,kw)))
    plain={k:v for k,v in settings.items() if k not in ('groupDeployment','pilotDeployment')}
    released.install_native_qualification_hub_configuration(SimpleNamespace(),plain)
    assert len(installed)==1
    assert set(installed[0][1]['operator_qualification'].workspaces)==set(mode['workspaces'])
    old=yaml.safe_load(base64.b64decode(args['originals']['secret']['data']['values.yaml']))
    new=yaml.safe_load(base64.b64decode(result['secret.patch.json'][-1]['value']['values.yaml']))
    old['hub']['extraConfig'].pop('zz-native-group-pilot');hook=new['hub']['extraConfig'].pop('zz-native-group-pilot')
    assert new==old
    assert all(owner in hook for owner in settings['owners'])
    assert "['cps-native-image-pull']" in hook
    assert result['modified_sources']==['cps']
    assert args==before


def current_objects(args,result):
    current=copy.deepcopy(args['originals'])
    current['config']=copy.deepcopy(result['configuration.json']);current['config']['metadata'].update(uid=uid(303),resourceVersion='8')
    for key,file,field in [('secret','secret.patch.json','data'),('deployment','deployment.patch.json','spec')]:
        current[key][field]=copy.deepcopy(result[file][-1]['value']);current[key]['metadata']['resourceVersion']='9'
    return current


def test_cps_hub_inverse_restores_exact_secret_and_deployment_with_fresh_cas():
    args=fixture();result=tool().forward_intent(**args);current=current_objects(args,result)
    inverse=tool().inverse_intent(current=current,**args)
    for key,file,field in [('secret','secret.patch.json','data'),('deployment','deployment.patch.json','spec')]:
        patch=inverse[file]
        assert [op['op'] for op in patch]==['test','test','test','replace']
        assert patch[1]['value']=='9'
        assert patch[-1]['value']==args['originals'][key][field]
    assert inverse['modified_sources']==['cps']


@pytest.mark.parametrize('fault',['hook','foreign-secret','group','transport-config','duplicate-yaml','mount'])
def test_cps_hub_forward_rejects_unreviewed_baselines(fault):
    args=fixture();original=args['originals']
    if fault=='hook':
        data=yaml.safe_load(base64.b64decode(original['secret']['data']['values.yaml']))
        data['hub']['extraConfig']['zz-native-group-pilot']+='print("foreign")\n'
        original['secret']['data']['values.yaml']=base64.b64encode(yaml.safe_dump(data).encode()).decode()
    elif fault=='foreign-secret': original['secret']['metadata']['namespace']='cit-jhub'
    elif fault in ('group','transport-config'):
        settings=json.loads(original['config']['data']['settings.json'])
        if fault=='group': settings['groupDeployment']={'enabled':False}
        else: settings['gatewayUrl']='http://foreign.invalid'
        original['config']['data']['settings.json']=transition.canonical(settings)
    elif fault=='duplicate-yaml': original['secret']['data']['values.yaml']=base64.b64encode(b'hub: {}\nhub: {}\n').decode()
    else: original['deployment']['spec']['template']['spec']['volumes'][0]['configMap']['name']='foreign'
    with pytest.raises(ValueError): tool().forward_intent(**args)


@pytest.mark.parametrize('fault',['config','code','image','mount','auth','uid','namespace','nonimmutable'])
def test_cps_hub_inverse_refuses_to_overwrite_any_unrelated_drift(fault):
    args=fixture();forward=tool().forward_intent(**args);current=current_objects(args,forward)
    if fault=='config': current['config']['data']['unrelated']='changed'
    elif fault=='code':
        values=yaml.safe_load(base64.b64decode(current['secret']['data']['values.yaml']))
        values['hub']['extraConfig']['unrelated']='changed'
        current['secret']['data']['values.yaml']=base64.b64encode(yaml.safe_dump(values).encode()).decode()
    elif fault=='image': current['deployment']['spec']['template']['spec']['containers'][0]['image']='foreign'
    elif fault=='mount': current['deployment']['spec']['template']['spec']['volumes'].append({'name':'foreign','hostPath':{'path':'/'}})
    elif fault=='auth': current['secret']['data']['unrelated-auth']='changed'
    elif fault=='uid': current['deployment']['metadata']['uid']=uid(9999)
    elif fault=='namespace': current['config']['metadata']['namespace']='cit-jhub'
    else: current['config']['immutable']=False
    with pytest.raises(ValueError): tool().inverse_intent(current=current,**args)


def test_generated_hook_chains_personal_hook_and_assigns_pull_secret_only_to_pair(monkeypatch):
    import asyncio
    args=fixture();result=tool().forward_intent(**args)
    settings=json.loads(result['configuration.json']['data']['settings.json'])
    value=yaml.safe_load(base64.b64decode(result['secret.patch.json'][-1]['value']['values.yaml']))
    hook=value['hub']['extraConfig']['zz-native-group-pilot']
    from cps_compute_hub import native_hub_config as released
    monkeypatch.setattr(released,'_read_json',lambda *a:args['gateway_inputs']['proposal']['policy.json'])
    monkeypatch.setattr(released,'_install_native_hub_configuration',lambda *a,**kw:None)
    original_read=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda path,*a,**kw:json.dumps(settings) if str(path)=='/etc/cps-native-hub/settings.json' else original_read(path,*a,**kw))
    called=[]
    async def personal(spawner):called.append(spawner.user.name)
    config=SimpleNamespace(KubeSpawner=SimpleNamespace(pre_spawn_hook=personal),Spawner=SimpleNamespace())
    exec(hook,{'c':config})
    for name in settings['owners']+['ordinary-student']:
        spawner=SimpleNamespace(user=SimpleNamespace(name=name),image_pull_secrets=['existing-personal-secret'])
        asyncio.run(config.KubeSpawner.pre_spawn_hook(spawner))
        assert spawner.image_pull_secrets==(['cps-native-image-pull'] if name in settings['owners'] else ['existing-personal-secret'])
    assert called==settings['owners']+['ordinary-student']
