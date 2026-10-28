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
    collector.check_peer=lambda pid:None
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


def test_reviewed_manifest_original_bytes_are_retained(monkeypatch,tmp_path):
    import json
    data={'version':1,'context':{},'policy':{},'operator':{},'resources':{},
          'pods':{'pressure':{},'peer':{}},'observer':{},'driver_version':'615.71.09','operator_ref':{},'node_ref':{}}
    original=(json.dumps(data,indent=4)+'\n').encode()
    manifest=tmp_path/'reviewed';manifest.write_bytes(original);manifest.chmod(0o600)
    probe=tmp_path/'probe';probe.write_bytes(b'probe source')
    host=tmp_path/'host';host.write_bytes(b'host source')
    window=tmp_path/'window';window.write_bytes(b'window source')
    output=tmp_path/'result'
    class InertCollector:
        def __init__(self,*args,**kwargs):pass
        def execute(self):pass
    monkeypatch.setattr(runner,'Collector',InertCollector)
    monkeypatch.setattr(sys,'argv',['run.py','--execute','--manifest',str(manifest),
        '--manifest-sha256',runner.sha(original),'--runner-sha256',runner.sha(Path(runner.__file__).read_bytes()),
        '--probe-source',str(probe),'--probe-sha256',runner.sha(probe.read_bytes()),
        '--collector-source',str(host),'--collector-sha256',runner.sha(host.read_bytes()),
        '--window-source',str(window),'--window-sha256',runner.sha(window.read_bytes()),'--output',str(output)])
    runner.main()
    assert (output/'manifest.raw.json').read_bytes()==original
    assert runner.sha((output/'manifest.raw.json').read_bytes())==json.loads((output/'source-pins.json').read_bytes())['manifest_raw']


def test_synthetic_runner_lifecycle_derives_actual_window_parser_fifth_receipt(tmp_path,monkeypatch):
    """Synthetic transport only, through the owning execute/derive/validator path."""
    import copy,json
    from test_personal_qualification_window import synthetic_window_fixture
    from test_personal_qualification_probe import synthetic_measurements
    bundle=synthetic_window_fixture();ctx,pressure,samples,_=synthetic_measurements()
    order=[];finished=False
    class Window:
        rows=[bundle['raw_window']]
        def finish(self):order.append('drain');return bundle['raw_window']
        def abandon(self):order.append('close-owned-pipe')
    c=runner.Collector({'context':ctx},b'probe',b'collector',tmp_path)
    def initialize():
        order.append('registered-ready-before-kernel');c.window=Window()
        c.window_identity={k:v for k,v in bundle['identities'].items() if k not in ('peer','peer_checks')}
        caps={role:{**row,'used_bytes':0,'gpu_processes':{},'driver_version':'615.synthetic'}
            for role,row in c.window_identity['caps'].items()}
        c.baseline={**bundle['kernel_records']['before'],'cgroups':caps}
        c.kernel_baseline=c.baseline['kernel_anchor']
    c.initialize=initialize
    c.check_final_authority=lambda:order.append('fresh-node-authorities')
    def rpc(role,body):
        nonlocal finished
        op=body['operation'];order.append(role+'-'+op)
        if op=='setup':return {'root':'/tmp/cps-mujoco-'+role}
        if op=='read':
            if role=='pressure':return {'stdout':pressure.decode()+'\n','exit':'0'}
            raw=bundle['raw_peer'].decode()+'\n'
            return {'stdout':raw,**({'exit':'0'} if finished else {})}
        if op=='finish-peer':finished=True;return {}
        if op in ('ack','cleanup'):return {}
        raise AssertionError(op)
    c.rpc=rpc;c.pod=lambda role:(b'{}',{})
    def check_peer(pid):
        order.append('root-peer-check');c.peer_checks.append(copy.deepcopy(bundle['identities']['peer_checks'][len(c.peer_checks)]))
    c.check_peer=check_peer
    c.sample=lambda event,pid:copy.deepcopy(next(s for s in samples if s['event_sha256']=='sha256:'+runner.sha(runner.canonical(event))))
    def baseline():
        order.append('actual-cap-health-check')
        return b'{}',{**bundle['kernel_records']['after'],'cgroups':copy.deepcopy(c.baseline['cgroups'])}
    c.host_baseline=baseline
    monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    c.execute()
    result=json.loads((tmp_path/'review-material.json').read_bytes())
    assert result['complete'] and len(result['probes'])==5 and result['authoritative'] is False
    assert 'unobservable' in result['exclusions']
    assert order.index('actual-cap-health-check')<order.index('peer-finish-peer')<order.index('drain')
    assert order[-1]=='pressure-cleanup'


def test_host_interpreter_receives_explicit_pinned_library_despite_invisible_inherited_loader_path(tmp_path):
    """Faithful embedded host Python command, no native initialization/calls."""
    import hashlib,json,os
    from cps_compute import native_gpu_health
    expected={'path':'/run/nvidia/driver/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.615.71.09',
        'sha256':'283793c0c30dc32f87c0e9fc9b5326fe764bad156e61afa3e997684c47b29a95'}
    source=b'import json; assert globals().get("_nvml_library") == '+repr(expected).encode()+b'; print(json.dumps(_nvml_library))'
    c=runner.Collector({'context':{'health_sha256':hashlib.sha256(Path(native_gpu_health.__file__).read_bytes()).hexdigest()}},
        b'',source,tmp_path)
    program=c.host_program()
    result=subprocess.run([sys.executable,'-I','-B','-c',program],capture_output=True,text=True,
        env={**os.environ,'LD_LIBRARY_PATH':'/invisible-container-only-mount'},check=False)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==expected
