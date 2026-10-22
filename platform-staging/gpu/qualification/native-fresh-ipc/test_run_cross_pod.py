import importlib.util
import io
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock,patch
import pytest
from types import SimpleNamespace

HERE=Path(__file__).parent

def runner():
    s=importlib.util.spec_from_file_location('fresh_ipc_runner',HERE/'run_cross_pod.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_default_inert_and_missing_closed_trust_inputs_do_no_io():
    m=runner()
    with patch.object(m.Path,'read_bytes',side_effect=AssertionError),patch.object(m.subprocess,'Popen',side_effect=AssertionError), \
         patch('sys.stdout',new_callable=io.StringIO) as output:m.main([])
    assert 'inert' in output.getvalue()
    with pytest.raises(ValueError):m.main(['--execute'])

def test_root_markers_must_bracket_open_result_before_endpoint_completion():
    import types
    path=HERE/'ipc_engine.py';module=types.ModuleType('engine');exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    trace=[];denied=Mock();witness=Mock();actual={'phase':'import-result'}
    witness.begin.side_effect=lambda *_:trace.append('root-begin')
    denied.send.side_effect=lambda *_:trace.append('actual-open')
    denied.wait.side_effect=lambda *_:(trace.append('actual-result') or actual)
    witness.end.side_effect=lambda *_:(trace.append('root-end') or {'correlated':True})
    denied.complete.side_effect=lambda :(trace.append('native-cleanup') or [actual])
    module.open_denied(denied,'trial',{'actual':'attribution'},witness)
    assert trace==['root-begin','actual-open','actual-result','root-end','native-cleanup']

@pytest.mark.parametrize('fault',[None,'late-proof','late-process','kernel','cancel'])
def test_actual_main_requires_kernel_and_final_fresh_context_then_cleans_every_session(tmp_path,fault):
    m=runner();trial='11111111-1111-4111-8111-111111111111'
    routes={'version':1,'attribution_argv':['ssh','approved','python3','-I','-B',m.ROOT+'/ipc_host_pid.py','--execute'],
        'witness_argv':['ssh','approved','python3','-I','-B',m.ROOT+'/kernel_witness_collector.py','--execute','--qualification',
            '--source-sha256',m.PINS['kernel_witness_collector.py'],'--validator-sha256',m.PINS['kernel_witness_validator.py']]}
    manifest={'pods':{k:{'uid':'uid-'+k,'namespace':'qa','name':'pod-'+k} for k in ('a','b')}}
    target=lambda k:dict(pod_uid='uid-'+k,intent={},identity={'pod_uid':'uid-'+k},seal_id=k,journal_sha256=k,
                         gate_sha256=k,limit={'soft':5,'hard':5,'used':0})
    before={'pods':['a','b'],'host':{'targets':[target('a'),target('b')],'processes':['actual']}}
    after=deepcopy(before)
    if fault=='late-process':after['host']['processes']=['replacement']
    observed=[]
    def preflight(_):
        observed.append('fresh')
        if len(observed)==2 and fault=='late-proof':raise ValueError('final actual proof denied')
        return before if len(observed)==1 else after
    cleaned=[]
    class Session:
        def __init__(self,target,args,source,label,output):self.label=label
        def wait(self,phase):return {'handle_b64':'opaque','namespace_pid':22}
        def wait_matching(self,*_):return None
        def send(self,*_):pass
        def complete(self):return ['actual clean endpoint events']
        def abandon(self):cleaned.append(self.label)
    witness=Mock()
    def opened(*_):
        if fault=='kernel':raise ValueError('no matching kernel denial')
        if fault=='cancel':raise KeyboardInterrupt()
        return [{'phase':'import-result','call_ended_monotonic_ns':10}],({'actual':'capture'},{'matched':'kernel'})
    engine=SimpleNamespace(Session=Session,open_denied=opened,
        assess_endpoint_events=lambda *_:{'state':'api-denial-observed-awaiting-kernel-witness'})
    current=SimpleNamespace(read_targets=lambda *_:manifest,preflight=preflight,GPU='selected',unique=lambda pairs:dict(pairs))
    spec=importlib.util.spec_from_file_location('retained_imports',HERE.parent/'native-fresh-imports/run_imports.py')
    retained=importlib.util.module_from_spec(spec);spec.loader.exec_module(retained)
    wt=SimpleNamespace(KernelWitness=lambda *_args,**_kw:witness)
    reply=SimpleNamespace(returncode=0,stdout=json.dumps({'trial_id':trial,'namespace_pid':22,'pod_uid':'uid-b',
        'boot_id':m.BOOT,'driver_generation':m.GENERATION}))
    args=['--execute','--manifest','reviewed','--manifest-sha256','reviewed','--transports','transport.json',
          '--transports-sha256','reviewed','--runner-sha256','reviewed','--output',str(tmp_path/'out')]
    def checked(path,_):return json.dumps(routes).encode() if Path(path).name=='transport.json' else b'approved'
    with patch.object(m,'checked',side_effect=checked),patch.object(m,'load',side_effect=[engine,current,retained,wt]), \
         patch.object(m.subprocess,'run',return_value=reply) as command,patch.object(m.uuid,'uuid4',return_value=trial), \
         patch('sys.stdout',new_callable=io.StringIO):
        if fault=='cancel':
            with pytest.raises(KeyboardInterrupt):m.main(args)
        elif fault:
            with pytest.raises(SystemExit):m.main(args)
        else:m.main(args)
    assert command.call_count==1 and sorted(cleaned)==['cross-pod-importer','exporter','same-pod-positive']
    witness.close.assert_called_once()
    receipt=json.loads((tmp_path/'out/receipt.json').read_text())
    assert receipt['production_qualified'] is False
    if fault:assert receipt['state']=='inconclusive' and not receipt.get('unchanged_native_authorities')
    else:assert observed==['fresh','fresh'] and receipt['state']=='bounded-cross-parent-kernel-denial-measured'
