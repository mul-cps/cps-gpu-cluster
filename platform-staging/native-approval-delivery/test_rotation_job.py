import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location('rotation_' + name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def inputs():
    config, configuration = load('test_render').fixture()
    return dict(config=config, configuration=configuration,
        image='ghcr.io/mul-cps/cps-compute@sha256:' + 'a' * 64,
        config_secret='reviewed-rotation-inputs', journal_pvc='existing-delivery-journal',
        job_name='cps-native-head-rotation-reviewed',
        previous_config_sha256='sha256:' + 'b' * 64,
        previous_state_sha256='sha256:' + 'c' * 64,
        anchor_sha256='sha256:' + 'd' * 64,
        previous_node_template_sha256='sha256:' + 'e' * 64)


def test_rotation_job_preserves_same_journal_and_uses_one_installed_cli_attempt():
    values=inputs();before=copy.deepcopy(values['config'])
    job=load('rotation_job').render(**values)
    assert job['apiVersion']=='batch/v1' and job['kind']=='Job'
    assert job['metadata']=={'namespace':'cps-compute','name':values['job_name']}
    assert {k:job['spec'][k] for k in ('backoffLimit','activeDeadlineSeconds','parallelism','completions')}==dict(
        backoffLimit=0,activeDeadlineSeconds=300,parallelism=1,completions=1)
    pod=job['spec']['template']['spec'];main=pod['containers'][0]
    assert pod['restartPolicy']=='Never'
    assert main['command']==['python','-I','-B','-m','cps_compute.native_approval_delivery']
    assert main['args']==['--config','/inputs/delivery/delivery.json','--state-dir','/journal/delivery','--execute',
        '--rotate-config','--previous-config','/inputs/delivery/previous-config.json',
        '--previous-config-sha256',values['previous_config_sha256'],
        '--previous-state-sha256',values['previous_state_sha256'],'--anchor-sha256',values['anchor_sha256'],
        '--previous-node-template','/inputs/delivery/previous-node-template.json']
    assert {'name':'journal','mountPath':'/journal/delivery','subPath':'head-delivery'} in main['volumeMounts']
    assert len([m for m in main['volumeMounts'] if m['name']=='journal'])==1
    assert values['config']==before
    base=next(o for o in load('render').render(values['config'],configuration=values['configuration'],
        image=values['image'],config_secret=values['config_secret'],journal_pvc=values['journal_pvc'])
        if o['kind']=='Deployment')['spec']['template']
    actual=copy.deepcopy(job['spec']['template'])
    del actual['spec']['restartPolicy']
    actual['spec']['containers'][0]['args']=base['spec']['containers'][0]['args']
    emitted=actual['spec']['initContainers'][0]['command'][-1]
    assert emitted.startswith(base['spec']['initContainers'][0]['command'][-1])
    actual['spec']['initContainers'][0]['command'][-1]=base['spec']['initContainers'][0]['command'][-1]
    assert actual==base


@pytest.mark.parametrize('field,value',[
    ('previous_config_sha256',None),('previous_state_sha256','a'*64),('anchor_sha256','sha256:'+'0'*64),
    ('previous_node_template_sha256','sha256:'+'A'*64),('job_name','Bad_Name'),
    ('active_deadline_seconds',False),('active_deadline_seconds',0),('active_deadline_seconds',901)])
def test_rotation_job_rejects_unpinned_or_unbounded_inputs(field,value):
    args=inputs();args[field]=value
    with pytest.raises(ValueError):load('rotation_job').render(**args)


@pytest.mark.parametrize('shadow',['previous-config.json','previous-node-template.json'])
def test_rotation_inputs_cannot_shadow_current_private_files(shadow):
    args=inputs();args['config']['policy_path']='/inputs/delivery/'+shadow
    with pytest.raises(ValueError):load('rotation_job').render(**args)


@pytest.mark.parametrize('fault',['none','config-bytes','template-bytes'])
def test_rotation_initializer_checks_extra_seed_bytes_without_touching_journal(tmp_path,fault):
    args=inputs();old=b'{"old":"exact bytes"}\n';template=b'{"template":"exact bytes"}\n'
    args['previous_config_sha256']='sha256:'+hashlib.sha256(old).hexdigest()
    args['previous_node_template_sha256']='sha256:'+hashlib.sha256(template).hexdigest()
    job=load('rotation_job').render(**args)
    seed=tmp_path/'seed';seed.mkdir();private=tmp_path/'inputs';private.mkdir()
    journal=tmp_path/'journal';journal.mkdir();state=journal/'head-delivery';state.mkdir(mode=0o700)
    files={'state.json':b'original journal','anchor.json':b'original anchor',
        'rotation-0123456789abcdef-node-template.json':b'original rotation archive'}
    for name,raw in files.items():(state/name).write_bytes(raw);(state/name).chmod(0o600)
    for name in ('delivery.json','policy.json','gateway-ca.pem','export.token'):(seed/name).write_bytes(b'current input')
    (seed/'previous-config.json').write_bytes(old if fault!='config-bytes' else b'changed')
    (seed/'previous-node-template.json').write_bytes(template if fault!='template-bytes' else b'changed')
    code=job['spec']['template']['spec']['initContainers'][0]['command'][-1]
    code=code.replace('/inputs/delivery',str(private/'delivery')).replace('/seed',str(seed)).replace('/journal',str(journal))
    result=subprocess.run([sys.executable,'-I','-c',code],capture_output=True,text=True)
    assert result.returncode==(0 if fault=='none' else 1)
    assert all((state/name).read_bytes()==raw for name,raw in files.items())
    if fault=='none':
        for name,raw in [('previous-config.json',old),('previous-node-template.json',template)]:
            target=private/'delivery'/name
            assert target.read_bytes()==raw and target.stat().st_mode&0o7777==0o600
