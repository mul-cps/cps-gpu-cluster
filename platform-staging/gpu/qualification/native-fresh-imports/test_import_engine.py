import ast
import hashlib
from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest

HERE=Path(__file__).parent

def engine():
    spec=importlib.util.spec_from_file_location('import_engine',HERE/'same_parent_engine.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def fixture(m):
    packet={'events':[{'phase':'native-event','monotonic_ns':150},{'phase':'native-event','monotonic_ns':200},
        {'phase':'receipt','state':'bounded-same-parent-measurement-completed',
         'results':[{'mode':'vmm-direct','successful_raw_cuda_measurement':True,'production_qualified':False}],
         'production_qualified':False,'cross_pod_import_isolation_qualified':False}], 'stage_cleanup_confirmed':True}
    peer=[{'phase':'peer_tick','tick':1,'monotonic_ns':100},{'phase':'peer_tick','tick':2,'monotonic_ns':300},
        {'phase':'receipt','case':'peer','state':'measurement-completed','peer_loop_passed':True,
         'production_qualified':False,'hardware':{'gpu_uuid':m.GPU,'torch_version':'2.11.0'}}]
    return packet,peer

def test_original_bundle_and_assessment_are_ast_identical():
    actual={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()
            for n in ast.parse((HERE/'same_parent_engine.py').read_text()).body
            if isinstance(n,ast.FunctionDef) and n.name in ('bundle','assess')}
    assert actual=={'bundle':'c8f103f09bf15457400930067da0649dc54f5ce043acd3d3e251f8449a95e6ac',
                   'assess':'1bafb47ab84072f253196ba975ba665b141b502099ff6f9a7df4c6828b766af8'}

def test_original_cleanup_native_results_and_peer_continuity_thresholds_remain():
    m=engine();packet,peer=fixture(m)
    assert m.assess(packet,peer,'vmm-direct')['peer_continuity'] is True
    for kind in ('cleanup','mode','qualified','early-peer-exit','gap','native-failure'):
        changed,ticks=deepcopy(packet),deepcopy(peer)
        if kind=='cleanup':changed['stage_cleanup_confirmed']=False
        elif kind=='mode':changed['events'][-1]['results'][0]['mode']='ipc'
        elif kind=='qualified':changed['events'][-1]['production_qualified']=True
        elif kind=='early-peer-exit':ticks[1]['monotonic_ns']=175
        elif kind=='gap':ticks[1]['monotonic_ns']=6000000100
        else:changed['events'][-1]['results'][0]['successful_raw_cuda_measurement']=False
        with pytest.raises(ValueError):m.assess(changed,ticks,'vmm-direct')
