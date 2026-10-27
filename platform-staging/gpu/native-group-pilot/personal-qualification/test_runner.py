"""Deterministic transport tests only; no real GPU or cluster invocation."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest
spec=importlib.util.spec_from_file_location('personal_runner',Path(__file__).with_name('run.py'))
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def test_inert_default_has_no_cluster_or_probe_side_effects():
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('run.py'))],capture_output=True,text=True,check=True)
    assert '"api_calls":false' in result.stdout


def test_reviewed_manifest_drift_is_rejected_before_command(tmp_path):
    manifest=tmp_path/'manifest';manifest.write_text('{}');manifest.chmod(0o600)
    with pytest.raises(ValueError,match='Reviewed manifest bytes changed'):
        runner.private(manifest,'f'*64)


def test_api_uid_replacement_is_not_adopted(tmp_path):
    calls=[]
    def command(args,stdin=None):
        calls.append(args);return b'{"metadata":{"uid":"replacement"}}'
    collector=runner.Collector({},b'',b'',tmp_path,command=command)
    with pytest.raises(ValueError,match='UID changed'):
        collector.get('pod',{'namespace':'owned','name':'owned','uid':'original'})
    assert len(calls)==1 and 'get' in calls[0] and 'exec' not in calls[0]


def test_failed_owned_run_only_cleans_proven_terminal_directories(tmp_path):
    collector=runner.Collector({},b'',b'',tmp_path)
    collector.initialize=lambda:None
    calls=[]
    def rpc(role,body):
        calls.append((role,body['operation']))
        if body['operation']=='setup':
            if role=='pressure':raise RuntimeError('ambiguous remote reply')
            return {'root':'/tmp/cps-mujoco-owned'}
        if body['operation']=='read':return {'stdout':'{"phase":"peer-tick","pid":123}\n'*2}
        raise AssertionError('Nonterminal child must not be deleted')
    collector.rpc=rpc
    with pytest.raises(RuntimeError,match='ambiguous'):collector.execute()
    assert 'hold-until-watchdog-terminal' in (tmp_path/'cleanup.json').read_text()
    assert all(operation!='cleanup' for _,operation in calls)


def test_offline_proposal_derives_canonical_resources_and_preserves_existing_operator_identities():
    import copy,json
    from cps_compute.policy import Policy
    from test_native_operator_node import combined_authority,operator_document
    from test_personal_qualification_probe import candidate_fixture
    from cps_compute.native_qualification import NativeGroupQualification
    spec=importlib.util.spec_from_file_location('prepare_personal',Path(__file__).with_name('prepare.py'))
    prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
    old,deployment,_,_=combined_authority();candidate,_=candidate_fixture()
    catalog=copy.deepcopy(old.catalog)
    catalog['profiles']['personal-mujoco-10']=candidate.catalog['profiles']['personal-mujoco-10']
    policy=Policy(catalog);operator=operator_document(policy,deployment)
    before=copy.deepcopy(operator)
    result=prepare.render(policy,operator)
    config=result['operator-qualification.json'];mode=NativeGroupQualification.from_config(config,Policy(result['policy.json']))
    for scope,row in before['workspaces'].items():
        for key in ('owner','pod','members','principal','storage'):
            assert mode.workspaces[scope][key]==row[key]
    assert mode.resource_contract('interactive-native-qualification-10')['requests']=={'cpu':'2','memory':'4G'}
    assert operator==before and result['review.json']['hardware_qualified'] is False
