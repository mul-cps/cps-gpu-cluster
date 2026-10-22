"""CPU-only checks of exact-source generation and real supported SDK caps."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

HERE = Path(__file__).parent
COHORT = 'a9fc091b-f388-4f21-8771-b6ae7b4734dc'


def adapter():
    s = importlib.util.spec_from_file_location('unequal_harness', HERE/'prepare.py')
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def load(name, raw):
    m = ModuleType('unequal_'+name.replace('.','_')); m.__file__ = str(HERE/name)
    exec(compile(raw, m.__file__, 'exec'), m.__dict__); return m


def request():
    return {'version':1,'namespace':'cps-native-qa147-20261022',
        'namespace_uid':'1f7d941a-872d-4453-a1ba-fd489d8aff14','cohort_uid':COHORT,'pair':'5-20',
        'gate_image':'ghcr.io/mul-cps/cps-compute@sha256:'+'a'*64,'policy_hash':'sha256:'+'b'*64}


def test_generated_real_compiler_binds_exact_five_twenty_and_inherits_reaper():
    m = adapter(); sources = m.build_sources(); r = load('render_fixture.py', sources['render_fixture.py'])
    value = r.render(request(), approve_qa_hostpaths=True)
    for label, cap in (('a',5120),('b',20480)):
        pod = value['pods'][label]; main, = pod['spec']['containers']
        assert 'command' not in main and main['args'][-1].endswith('time.sleep(1800)')
        gate = pod['spec']['initContainers'][0]
        assert gate['args'][gate['args'].index('--cap-mib')+1] == str(cap)
        actual = deepcopy(pod); actual['metadata']['uid'] = ('1' if label=='a' else '2')*8+'-1111-4111-8111-111111111111'
        bound = r.finalize(request(),pod,pod,actual=actual,approve_qa_hostpaths=True)
        assert bound['intent']['cap_mib']==cap and bound['intent']['pod_uid']==actual['metadata']['uid']
        assert bound['spec_sha256']==r.runtime.native_spec_sha256(actual)
    with pytest.raises(ValueError): r.render({k:v for k,v in request().items() if k!='cohort_uid'},approve_qa_hostpaths=True)


def test_native_inventory_maps_each_actual_parent_to_its_exact_cap_and_budget():
    c = load('controller.py',adapter().build_sources()['controller.py'])
    def row(inode, cap):
        return dict(cgroup_id=inode,kernfs_id=inode,inode=inode,offline=False,pinned=True,
            default_hierarchy=True,soft=cap*1048576,hard=cap*1048576,used=0)
    value=dict(version=1,backend='misc-fallback',gpu_uuid=c.GPU,gpu_id=0,entries=[row(31,5120),row(32,20480)])
    c.inventory(value,{31:5120*1048576,32:20480*1048576},sealed=True)
    for bad in ('swapped','missing','unknown','unlimited','charge','budget'):
        doc=deepcopy(value); caps={31:5120*1048576,32:20480*1048576}
        if bad=='swapped': doc['entries']=[row(31,20480),row(32,5120)]
        elif bad=='missing': doc['entries'].pop()
        elif bad=='unknown': doc['entries'].append(row(33,5120))
        elif bad=='unlimited': doc['entries'][1].update(soft=0,hard=2**64-1)
        elif bad=='charge': doc['entries'][1]['used']=20480*1048576+1
        elif bad=='budget': caps[31]=20480*1048576; doc['entries'][0]=row(31,20480)
        with pytest.raises(ValueError): c.inventory(doc,caps,sealed=True)


def test_generated_prepare_is_inert_and_emits_exclusive_private_pinned_scripts(tmp_path):
    m=adapter()
    with patch.object(Path,'read_bytes',side_effect=AssertionError('inert IO')),patch('builtins.print'):
        m.main([])
    path=tmp_path/'request'; raw=json.dumps(request()).encode();path.write_bytes(raw)
    out=tmp_path/'prepared'
    m.main(['--prepare','--inputs',str(path),'--inputs-sha256',hashlib.sha256(raw).hexdigest(),
            '--output',str(out),'--approve-qa-hostpaths'])
    receipt=json.loads((out/'preparation.json').read_bytes())
    assert receipt['hardware_qualified'] is False and receipt['profile_caps']=={'a':5120,'b':20480}
    for name,digest in receipt['generated_sha256'].items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
        assert (out/name).stat().st_mode&0o777==0o600
    assert (out/'b.proposed.json').is_file() and out.stat().st_mode&0o777==0o700
    with pytest.raises(FileExistsError):
        m.main(['--prepare','--inputs',str(path),'--inputs-sha256',hashlib.sha256(raw).hexdigest(),
                '--output',str(out),'--approve-qa-hostpaths'])


def test_actual_sdk_twenty_cap_sealing_and_original_cleanup_are_reused():
    sdk='/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023'
    sys.path[:0]=[sdk+'/src',sdk+'/tests']
    from test_native_node_backend import NodeBackendTests
    f=NodeBackendTests();f.setUp()
    try:
        f.intent=replace(f.intent,cap_mib=20480);f.backend.intents={f.intent.pod_uid:f.intent}
        c=load('controller.py',adapter().build_sources()['controller.py'])
        o=load('observe.py',adapter().build_sources()['observe.py'])
        record=f.controller.reconcile(f.intent)
        assert f.driver.writes[-1]==(20480*1048576,20480*1048576)
        assert o.sealed_record(f.backend,f.journal,f.intent)['limit']['hard']==20480*1048576
        f.driver.value['hard']=5120*1048576
        with pytest.raises(ValueError):o.sealed_record(f.backend,f.journal,f.intent)
        f.driver.value['hard']=20480*1048576
        f.stop();result=c.cleanup_records(f.controller,f.journal,[f.intent])
        assert result[0].state=='cleaned' and result[0].intent==record.intent
    finally:f.doCleanups()


def test_retirement_predicates_and_original_source_bytes_are_unchanged():
    import ast
    m=adapter();sources=m.build_sources()
    original=(HERE.parent/'native-fresh-domain/controller.py').read_bytes()
    names=('cohort_state','verify_retirements','retirement_inputs','cleanup_records')
    def definitions(raw):
        return {n.name:ast.dump(n) for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name in names}
    assert definitions(original)==definitions(sources['controller.py'])
    assert all(hashlib.sha256((HERE.parent/name).read_bytes()).hexdigest()==pin for name,pin in m.PINS.items())


def test_tampered_source_preimage_denied_before_any_dependency_execution(monkeypatch,tmp_path):
    m=adapter();original=Path.read_bytes
    def changed(path):
        if path.name=='peer_probe.py':return b'raise RuntimeError("unreviewed code")'
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',changed)
    monkeypatch.setattr(m,'load',lambda *_:pytest.fail('unverified dependency executed'))
    with pytest.raises(ValueError,match='preimages'):m.build_sources()


def test_old_retirements_never_enter_active_budget_or_become_a_global_allowlist():
    c=load('controller.py',adapter().build_sources()['controller.py'])
    def row(inode,cap,offline=False):
        return dict(cgroup_id=inode,kernfs_id=inode,inode=inode,offline=offline,pinned=True,
            default_hierarchy=True,soft=cap*1048576,hard=cap*1048576,used=0)
    retired={i:row(i,5120,True) for i in range(1,7)}
    value=dict(version=1,backend='misc-fallback',gpu_uuid=c.GPU,gpu_id=0,
        entries=[*retired.values(),row(31,5120),row(32,20480)])
    c.inventory(value,{31:5120*1048576,32:20480*1048576},sealed=True,retired=retired)
    for mutation in ('missing-original','changed-original','unknown-original'):
        changed=deepcopy(value)
        if mutation=='missing-original':changed['entries'].pop(0)
        elif mutation=='changed-original':changed['entries'][0]['used']=1
        else:changed['entries'].append(row(9,5120,True))
        with pytest.raises(ValueError):c.inventory(changed,{31:5120*1048576,32:20480*1048576},sealed=True,retired=retired)


def test_twenty_oom_engine_retains_original_touch_hold_recovery_and_oversized_denial():
    test_dir=HERE.parent/'native-fresh-domain';sys.path.insert(0,str(test_dir))
    from test_peer_oom import Torch
    p=load('peer_probe.py',adapter().build_sources()['peer_probe.py']);p.CAP_MIB=20480
    torch=Torch(19968);holds=[]
    with patch.object(p.time,'sleep',side_effect=lambda seconds:holds.append((seconds,torch.held))):
        result=p.run_steps(torch,lambda *a:None,19456)
    assert holds==[(8,19968*1048576)] and torch.held==0
    assert result['oversized_denied'] is True and result['maximum_attempted_tensor_mib']==20736
    assert result['bounded_step_sequence_passed'] is True and result['recovery_byte']==37
    assert result['oversized_error']==result['over_error']=={'kind':'torch.OutOfMemoryError','cuda_error_code':None}


def events(cap=20480,aggregate=False):
    held=cap-(2816 if aggregate else 512)
    peer=[dict(phase='peer_tick',tick=i+1,monotonic_ns=n,holder_tensor_mib=2048 if aggregate else 0)
          for i,n in enumerate(range(1_000_000_000,13_000_000_000,1_000_000_000))]
    peer.append(dict(phase='receipt',state='measurement-completed',case='aggregate-peer' if aggregate else 'peer',
        cap_mib=cap if aggregate else 5120,hardware={'gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56',
        'torch_version':'2.11.0'},peer_loop_passed=True,production_qualified=False))
    typed={'kind':'torch.OutOfMemoryError','cuda_error_code':None}
    oom=[dict(phase='over-allocation-error',monotonic_ns=2_000_000_000,typed_oom=True),
        dict(phase='oom-held-start',monotonic_ns=2_100_000_000,held_tensor_mib=held),
        dict(phase='oom-held-end',monotonic_ns=10_100_000_000,held_tensor_mib=held),
        dict(phase='after-recovery-free64',monotonic_ns=10_500_000_000),
        dict(phase='receipt',case='aggregate-oom' if aggregate else 'oom',state='measurement-completed',cap_mib=cap,
            hardware={'gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56','torch_version':'2.11.0'},
            bounded_step_sequence_passed=True,over_denied=True,ordinary_byte=19,recovery_byte=37,
            held_before_oom_mib=held,over_error=typed,oversized_error=typed,oversized_denied=True,
            maximum_attempted_tensor_mib=cap+256,production_qualified=False)]
    samples=[dict(observed_monotonic_ns=n,physical_free_bytes=8*1024**3,physical_total_bytes=40*1024**3,
        gpu_uuid='GPU-16128952-b438-556a-00bb-93039ee24e56') for n in (3_000_000_000,5_000_000_000,7_000_000_000)]
    return peer,oom,samples


@pytest.mark.parametrize('aggregate',[False,True])
def test_target_specific_oom_thresholds_and_all_original_peer_physical_guards(aggregate):
    name='run_aggregate.py' if aggregate else 'run_peer_oom.py'
    r=load(name,adapter().build_sources()[name]);peer,oom,samples=events(aggregate=aggregate)
    assert r.assess(peer,oom,samples,cap_mib=20480,peer_cap_mib=20480 if aggregate else 5120)['measurement_passed']
    for bad in ('wrong-cap','low-held','oversized-not-denied','generic-error','no-peer-overlap','low-physical','short-hold'):
        p,o,s=deepcopy((peer,oom,samples))
        if bad=='wrong-cap':o[-1]['cap_mib']=5120
        elif bad=='low-held':o[-1]['held_before_oom_mib']=1536
        elif bad=='oversized-not-denied':o[-1]['oversized_denied']=False
        elif bad=='generic-error':o[-1]['over_error']={'kind':'RuntimeError','cuda_error_code':None}
        elif bad=='no-peer-overlap':p=[x for x in p if x['phase']!='peer_tick' or x['tick'] in (1,12)]
        elif bad=='low-physical':s[0]['physical_free_bytes']=6*1024**3
        else:o[2]['monotonic_ns']=3_000_000_000
        with pytest.raises(ValueError):r.assess(p,o,s,cap_mib=20480,peer_cap_mib=20480 if aggregate else 5120)


def accounting():
    targets={'pods':{'a':{'uid':'actual-a','cap_mib':5120},'b':{'uid':'actual-b','cap_mib':20480}}}
    base={'pods':['actual-a-spec','actual-b-spec'],'host':{'processes':['actual-a-process','actual-b-process'],
        'observed_monotonic_ns':1_000_000_000,'targets':[
            {'pod_uid':row['uid'],'seal_id':'original-'+row['uid'],
             'limit':{'soft':row['cap_mib']*1048576,'hard':row['cap_mib']*1048576,'used':0}}
            for row in targets['pods'].values()]}}
    held=deepcopy(base);held['host']['observed_monotonic_ns']=3_000_000_000
    held['host']['targets'][0]['limit']['used']=64*1048576
    held['host']['targets'][1]['limit']['used']=19968*1048576
    return targets,base,held


def test_held_native_accounting_requires_inside_pressure_exact_cap_and_unchanged_custody():
    r=load('run_peer_oom.py',adapter().build_sources()['run_peer_oom.py'])
    targets,before,held=accounting();_,oom,_=events()
    r.held_accounting(before,held,oom,targets,'b')
    for bad in ('late','low-charge','wrong-cap','seal-drift','process-drift','foreign-uid'):
        value=deepcopy(held)
        if bad=='late':value['host']['observed_monotonic_ns']=11_000_000_000
        elif bad=='low-charge':value['host']['targets'][1]['limit']['used']=5120*1048576
        elif bad=='wrong-cap':value['host']['targets'][1]['limit']['hard']=5120*1048576
        elif bad=='seal-drift':value['host']['targets'][1]['seal_id']='replacement'
        elif bad=='process-drift':value['host']['processes'][0]='replacement'
        else:value['host']['targets'][1]['pod_uid']='foreign'
        with pytest.raises(ValueError):r.held_accounting(before,value,oom,targets,'b')


@pytest.mark.parametrize('fault',[None,'preflight','late-held','final-seal','cancel'])
def test_generated_runner_main_late_proof_and_cancel_never_accept_and_clean_transports(tmp_path,fault):
    sources=adapter().build_sources()
    for name,raw in sources.items():(tmp_path/name).write_bytes(raw)
    r=load('run_peer_oom.py',sources['run_peer_oom.py']);r.__file__=str(tmp_path/'run_peer_oom.py')
    targets,before,held=accounting();peer_events,oom_events,samples=events();runs=[];calls=[]
    def preflight(_):
        calls.append(len(calls)+1)
        if fault=='preflight' and len(calls)==1:raise ValueError('actual preflight rejected')
        if fault=='cancel' and len(calls)==2:raise KeyboardInterrupt()
        value=deepcopy(held if len(calls)==2 else before)
        if fault=='late-held' and len(calls)==2:value['host']['observed_monotonic_ns']=11_000_000_000
        if fault=='final-seal' and len(calls)==3:value['host']['targets'][1]['seal_id']='replacement'
        return value
    current=ModuleType('fake_external_observers');current.read_targets=lambda *_:targets;current.preflight=preflight
    # External API/host seams are replaced; real generated hash checks, stage order,
    # assessment, held-accounting checks and finally cleanup execute unchanged.
    r.exec=lambda code,namespace:namespace.update(current.__dict__)
    class Run:
        def __init__(self,target,case,*_):
            self.events=deepcopy(peer_events if case=='peer' else oom_events);self.closed=False;runs.append(self)
            assert target['cap_mib']==(5120 if case=='peer' else 20480)
        def wait(self,predicate,_):assert predicate(self.events)
        def complete(self):return self.events
        def close(self):self.closed=True
    r.ProbeRun=Run;r.physical_samples=lambda _:deepcopy(samples)
    output=tmp_path/'measurement'
    argv=['--execute','--manifest','Root-reviewed','--manifest-sha256','Root-reviewed',
        '--output',str(output),'--runner-sha256',hashlib.sha256(sources['run_peer_oom.py']).hexdigest(),
        '--preflight-sha256',hashlib.sha256(sources['fresh_preflight.py']).hexdigest(),
        '--probe-sha256',hashlib.sha256(sources['peer_probe.py']).hexdigest()]
    if fault:
        with pytest.raises(KeyboardInterrupt if fault=='cancel' else ValueError):r.main(argv)
        assert not (output/'assessment.json').exists()
    else:
        r.main(argv);assert json.loads((output/'assessment.json').read_bytes())['measurement_passed']
        assert calls==[1,2,3]
    assert all(run.closed for run in runs)


@pytest.mark.parametrize('pair,large,budget',[('5-10',10240,15360),('5-20',20480,25600)])
def test_closed_pair_choice_emits_individually_fixed_map_budget_and_coherent_observer_pin(pair,large,budget):
    m=adapter();sources=m.build_sources(pair);request_value=request();request_value['pair']=pair
    r=load('render_fixture.py',sources['render_fixture.py'])
    result=r.render(request_value,approve_qa_hostpaths=True)
    gate=result['pods']['b']['spec']['initContainers'][0]
    assert gate['args'][gate['args'].index('--cap-mib')+1]==str(large)
    c=load('controller.py',sources['controller.py']);o=load('observe.py',sources['observe.py'])
    assert o.CONTROLLER_SHA256==hashlib.sha256(sources['controller.py']).hexdigest()
    assert c.expected_cap('native-qa147-a-'+COHORT[:8],COHORT)==5120
    assert c.expected_cap('native-qa147-b-'+COHORT[:8],COHORT)==large
    wrong=deepcopy(request_value);wrong['pair']='5-20' if pair=='5-10' else '5-10'
    with pytest.raises(ValueError):r.render(wrong,approve_qa_hostpaths=True)
    def row(inode,cap):return dict(cgroup_id=inode,kernfs_id=inode,inode=inode,offline=False,pinned=True,
        default_hierarchy=True,soft=cap*1048576,hard=cap*1048576,used=0)
    value=dict(version=1,backend='misc-fallback',gpu_uuid=c.GPU,gpu_id=0,entries=[row(31,5120),row(32,large)])
    c.inventory(value,{31:5120*1048576,32:large*1048576},sealed=True)
    assert sum(v['hard'] for v in value['entries'])==budget*1048576
    peer,oom,samples=events(cap=large)
    runner=load('run_peer_oom.py',sources['run_peer_oom.py'])
    assert runner.assess(peer,oom,samples,cap_mib=large,peer_cap_mib=5120)['measurement_passed']
    assert oom[-1]['maximum_attempted_tensor_mib']==large+256


@pytest.mark.parametrize('pair',[None,True,'5-30','10-20',{'a':5120,'b':10240}])
def test_invalid_or_unreviewed_pair_denied_before_source_read(pair):
    m=adapter()
    with patch.object(Path,'read_bytes',side_effect=AssertionError('source IO')):
        with pytest.raises(ValueError,match='Closed reviewed pair'):m.build_sources(pair)


@pytest.mark.parametrize('alias',[False,True])
def test_generated_execute_reaches_inventory_only_after_disjoint_parent_guard(tmp_path,monkeypatch,alias):
    from types import SimpleNamespace
    sys.path.insert(0,'/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/src')
    from cps_compute import native_gpu_controller as actual_models
    c=load('controller.py',adapter().build_sources('5-10')['controller.py'])
    class BeforeCaps(Exception):pass
    observations=[];inventories=[];closed=[]
    class Backend:
        def observe(self,intent):
            observations.append(intent.pod_uid)
            return SimpleNamespace(identity=SimpleNamespace(cgroup_inode=31 if '-a-' in intent.name else 32))
        def _inventory(self,identity):return {'actual':'fresh inventory boundary'}
    class Driver:
        version='615.71.09'
        def close(self):closed.append(True)
    class Journal:
        def __init__(self,*_):pass
        def records(self):return ()
    def before_caps(value,allowed,**kwargs):
        inventories.append(allowed)
        assert allowed=={31:5120*1048576,32:10240*1048576}
        raise BeforeCaps()
    kube=SimpleNamespace(call=lambda *_:{'metadata':{'uid':c.NS_UID}},pod=lambda *_:None,
                         node=lambda *_:None,delete=lambda *_:None)
    back=SimpleNamespace(private_directory=lambda *_:None,private_read=lambda *_,**kw:c.GENERATION,
                         QualificationNodeBackend=lambda *_,**kw:Backend())
    models=SimpleNamespace(CapIntent=actual_models.CapIntent,PrivateJournal=Journal,
        NativeCapController=lambda *_,**kw:SimpleNamespace(reconcile=lambda *_:pytest.fail('cap mutation')))
    modules={name:SimpleNamespace() for name in c.PINS}
    modules.update({'native_gpu_controller.py':models,'native_node/backend.py':back,
        'native_node/nvml.py':SimpleNamespace(Nvml=Driver),
        'native_node/transport.py':SimpleNamespace(Kubernetes=lambda *_:kube,cri_reader=lambda *_:None)})
    monkeypatch.setattr(c,'load_bundle',lambda _:modules)
    monkeypatch.setattr(c,'retirement_inputs',lambda *_:{31 if alias else 99:{'protected':'old proof'}})
    monkeypatch.setattr(c,'inventory',before_caps);monkeypatch.setattr(c.os,'geteuid',lambda:0)
    monkeypatch.setattr(Path,'read_text',lambda self,*_,**kw:c.BOOT)
    files=[]
    for label,cap in (('a',5120),('b',10240)):
        intent=actual_models.CapIntent(c.NS,'native-qa147-'+label+'-'+COHORT[:8],
            ('1' if label=='a' else '2')*8+'-1111-4111-8111-111111111111',c.NODE,c.NODE_UID,
            'a'*64,c.GPU,cap,'sha256:'+'b'*64)
        path=tmp_path/(label+'.json');raw=json.dumps(intent.to_dict()).encode();path.write_bytes(raw)
        files.append((path,hashlib.sha256(raw).hexdigest()))
    args=SimpleNamespace(approve_qa_hostpaths=True,cohort_uid=COHORT,state_root=None,bundle='pinned',
        intent_a=files[0][0],intent_a_sha256=files[0][1],intent_b=files[1][0],intent_b_sha256=files[1][1],
        service_account='private',crictl='actual-cri',cri_socket='actual-socket',nvidia_smi='actual-binary',cleanup=False)
    with pytest.raises(ValueError if alias else BeforeCaps):c.execute(args)
    assert len(observations)==2 and closed==[True]
    assert bool(inventories) is not alias
