import copy,importlib.util,uuid
from pathlib import Path
import pytest
P=Path(__file__).with_name('process_attribution.py')
def module():
 s=importlib.util.spec_from_file_location('vmm_attribution',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def request(role='importer',cap=20480):
 return dict(trial_id=str(uuid.uuid4()),namespace_pid=7,identity={},role=role,expect='deny' if role=='importer' else None,cap_mib=cap,exporter_pod_uid=str(uuid.uuid4()) if role=='importer' else None)

@pytest.mark.parametrize('role,cap',[('importer',5120),('exporter',20480)])
def test_exact_roles_and_caps(role,cap):
 r=request(role,cap);assert module().validate_request(r)==r

@pytest.mark.parametrize('key,value',[('cap_mib',True),('cap_mib',40960),('namespace_pid',True),('role','arbitrary'),('expect','skip'),('exporter_pod_uid','name-only'),('override',True)])
def test_changed_or_unbounded_request_rejected_before_process_scan(key,value):
 r=request();r[key]=value
 with pytest.raises(ValueError):module().observe(r)
