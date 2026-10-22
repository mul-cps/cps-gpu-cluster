"""Actual compiler and protected-file CPU tests; no installed-image/hardware claim."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

HERE=Path(__file__).parent
COHORT='5d1ea1a3-45e7-4d44-934a-d6eaa75f9a13'
IMAGE='ghcr.io/mul-cps/cps-native-node@sha256:81aac20157965ed5503b0d208b0326fef1ba10d71089d9e635128cea48dafe82'
POLICY='sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281'


def adapter():
    s=importlib.util.spec_from_file_location('packaged_gate',HERE/'prepare_packaged_gate.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def load(name,raw):
    m=ModuleType('packaged_'+name.replace('.','_'));m.__file__=str(HERE/name)
    exec(compile(raw,m.__file__,'exec'),m.__dict__);return m


def request():
    return dict(version=1,namespace='cps-native-qa147-20261022',
        namespace_uid='1f7d941a-872d-4453-a1ba-fd489d8aff14',cohort_uid=COHORT,
        gate_image=IMAGE,policy_hash=POLICY,pair='5-10')


def test_actual_compiler_ordinary_packaged_gate_has_no_qa_code_projection_and_exact_caps():
    sources=adapter().build_sources(COHORT);r=load('render_fixture.py',sources['render_fixture.py'])
    value=r.render(request(),approve_qa_hostpaths=True)
    assert not value.get('source_configmap')
    for label,cap in (('a',5120),('b',10240)):
        pod=value['pods'][label];gate=pod['spec']['initContainers'][0]
        assert gate['image']==IMAGE
        assert gate['command']==['python','-m','cps_compute.native_gpu_runtime']
        assert gate['args'][0]=='wait-for-cap' and gate['args'][gate['args'].index('--cap-mib')+1]==str(cap)
        assert '/opt/cps-qa' not in json.dumps(pod)
        assert not any('configMap' in v or v['name']=='qa-gate-package' for v in pod['spec']['volumes'])
        paths={v['name']:v.get('hostPath',{}).get('path') for v in pod['spec']['volumes']}
        assert paths['cps-native-authority']==r.LOAD_AUTHORITY
        assert paths['cps-native-receipts'].endswith('/cohorts/'+COHORT+'/state/receipts')
        main,=pod['spec']['containers'];assert 'command' not in main and main['args'][-1].endswith('time.sleep(1800)')
        assert gate['securityContext']['runAsUser']==0 and main['securityContext']['runAsUser']==1000
        actual=deepcopy(pod);actual['metadata']['uid']=('1' if label=='a' else '2')*8+'-1111-4111-8111-111111111111'
        bound=r.finalize(request(),pod,pod,actual=actual,approve_qa_hostpaths=True)
        assert bound['intent']['cap_mib']==cap and bound['spec_sha256']==r.runtime.native_spec_sha256(actual)
        actual['spec']['containers'][0]['args'][-1]+='; changed'
        with pytest.raises(ValueError):r.finalize(request(),pod,pod,actual=actual,approve_qa_hostpaths=True)
    assert r.runtime.wait_for_native_cap.__kwdefaults__['timeout_seconds']==300


@pytest.mark.parametrize('field,value',[('gate_image','ghcr.io/mul-cps/cps-compute@sha256:'+'a'*64),
    ('policy_hash','sha256:'+'d'*64),('pair','5-20')])
def test_wrong_packaged_image_policy_or_pair_never_renders(field,value):
    r=load('render_fixture.py',adapter().build_sources(COHORT)['render_fixture.py'])
    changed=request();changed[field]=value
    with pytest.raises(ValueError):r.render(changed,approve_qa_hostpaths=True)


def test_preparation_never_emits_a_gate_source_configmap(tmp_path):
    m=adapter();p=tmp_path/'request';raw=json.dumps(request()).encode();p.write_bytes(raw)
    out=tmp_path/'prepared'
    m.main(['--prepare','--inputs',str(p),'--inputs-sha256',hashlib.sha256(raw).hexdigest(),
        '--output',str(out),'--approve-qa-hostpaths'])
    assert not (out/'gate-source.configmap.json').exists()
    review=json.loads((out/'preparation.json').read_bytes())
    assert review['gate_image']==IMAGE and review['hardware_qualified'] is False
    assert review['installed_runtime_sha256']=='035fa64027c09965fcb7557f4346b449b637aa39de804a94565deffe067b0e74'
    c=load('controller.py',(out/'controller.py').read_bytes());o=load('observe.py',(out/'observe.py').read_bytes())
    assert o.CONTROLLER_SHA256==hashlib.sha256((out/'controller.py').read_bytes()).hexdigest()
    assert c.expected_cap('native-qa147-b-'+COHORT[:8],COHORT)==10240


@pytest.mark.parametrize('cap',[5120,10240,20480])
def test_retired_original_ten_gib_admission_keeps_all_actual_sdk_proofs(tmp_path,monkeypatch,cap):
    from dataclasses import replace
    import os
    import shutil
    from types import SimpleNamespace
    sdk='/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023'
    sys.path[:0]=[sdk+'/src',sdk+'/tests']
    import test_native_node_backend as fixture
    from cps_compute.native_node import backend
    f=fixture.NodeBackendTests();f.setUp()
    try:
        f.intent=replace(f.intent,cap_mib=cap);f.backend.intents={f.intent.pod_uid:f.intent}
        record=f.controller.reconcile(f.intent)
        f.stop();f.pod=None;shutil.rmtree(f.group);f.retired_inventory(record)
        record=f.controller.cleanup(f.intent)
        sources=adapter().build_sources(COHORT);c=load('controller.py',sources['controller.py'])
        baseline=load('old_controller.py',adapter().load('prepare.py',(HERE/'prepare.py').read_bytes()).build_sources('5-10')['controller.py'])
        current=tmp_path/'new-state';current.mkdir(mode=0o700)
        for m in (c,baseline):
            for name,value in (('STATE',str(f.state)),('NS',f.intent.namespace),('NODE',f.intent.node),
                ('NODE_UID',f.intent.node_uid),('BOOT',record.identity.boot_id),('GENERATION',record.identity.driver_generation)):
                monkeypatch.setattr(m,name,value)
        path=tmp_path/'retirement';raw=json.dumps({'version':2,'states':[
            {'state_root':str(f.state),'records':[record.to_dict()]}]}).encode();path.write_bytes(raw)
        args=SimpleNamespace(retirement=path,retirement_sha256=hashlib.sha256(raw).hexdigest())
        back=SimpleNamespace(private_directory=lambda path:backend.private_directory(path,os.getuid()))
        def make(intents,old):
            assert intents==[f.intent] and old==str(f.state);return f.backend
        def run(m):return m.retirement_inputs(args,fixture.models,back,make,str(current))
        if cap!=5120:
            with pytest.raises(ValueError):run(baseline)  # Original historical5-only guard.
        if cap==20480:
            with pytest.raises(ValueError):run(c)
        else:
            rows=run(c);assert rows[record.identity.cgroup_inode]['hard']==cap*1048576
            assert rows[record.identity.cgroup_inode]['offline'] is True
            f.retired_inventory(record,used=1)
            with pytest.raises(ValueError):run(c)
            assert f.journal.read(record.intent.pod_uid)==record
    finally:f.doCleanups()


def test_retirement_proof_functions_and_active_budget_are_not_relaxed():
    import ast
    m=adapter();sources=m.build_sources(COHORT)
    old=m.load('prepare.py',(HERE/'prepare.py').read_bytes()).build_sources('5-10')['controller.py']
    def definition(raw,name):
        return ast.dump(next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==name))
    for name in ('inventory','verify_retirements','cleanup_records'):
        assert definition(old,name)==definition(sources['controller.py'],name)
    c=load('controller.py',sources['controller.py'])
    def row(inode,cap,offline):
        return dict(cgroup_id=inode,kernfs_id=inode,inode=inode,offline=offline,pinned=True,
            default_hierarchy=True,soft=cap*1048576,hard=cap*1048576,used=0)
    retired={n:row(n,10240 if n==8 else 5120,True) for n in range(1,9)}
    value=dict(version=1,backend='misc-fallback',gpu_uuid=c.GPU,gpu_id=0,
        entries=[*retired.values(),row(31,5120,False),row(32,10240,False)])
    caps={31:5120*1048576,32:10240*1048576}
    c.inventory(value,caps,retired=retired,sealed=True)
    for bad in ('cap-swap','unknown','changed-retired'):
        changed=deepcopy(value)
        if bad=='cap-swap':changed['entries'][-2:]=[row(31,10240,False),row(32,5120,False)]
        elif bad=='unknown':changed['entries'].append(row(90,5120,True))
        else:changed['entries'][7]['used']=1
        with pytest.raises(ValueError):c.inventory(changed,caps,retired=retired,sealed=True)


def test_inert_source_drift_and_old_or_invalid_cohort_denials(monkeypatch,tmp_path):
    from unittest.mock import patch
    m=adapter()
    with patch.object(Path,'read_bytes',side_effect=AssertionError('inert IO')),patch('builtins.print'):m.main([])
    for cohort in ('a9fc091b-f388-4f21-8771-b6ae7b4734dc','../old',True,'00000000-0000-0000-0000-000000000000'):
        with pytest.raises(ValueError):m.build_sources(cohort)
    original=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda p:b'unreviewed' if p.name=='prepare.py' else original(p))
    with pytest.raises(ValueError,match='before execution'):m.build_sources(COHORT)
