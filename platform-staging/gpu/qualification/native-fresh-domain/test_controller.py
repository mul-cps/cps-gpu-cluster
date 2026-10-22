import importlib.util
from pathlib import Path
import subprocess
import sys
import hashlib
import json
import shutil
from types import SimpleNamespace
import pytest

HERE = Path(__file__).parent

def module():
    spec = importlib.util.spec_from_file_location('fresh_controller', HERE / 'controller.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_default_inert():
    result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'controller.py')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '"state": "inert"' in result.stdout

def test_complete_pinned_bundle_is_checked_before_import(tmp_path):
    m = module()
    bundle = m.prepare_bundle(tmp_path / 'bundle')
    assert m.check_bundle(bundle)
    (bundle / 'cps_compute/native_node/backend.py').write_text('raise RuntimeError("must not execute")')
    with pytest.raises(ValueError, match='source'):
        m.check_bundle(bundle)

def test_bundle_import_is_standalone_and_never_loads_nvml_or_installed_sdk(tmp_path):
    m = module()
    bundle = m.prepare_bundle(tmp_path / 'bundle')
    command = ('import importlib.util,sys; '
        's=importlib.util.spec_from_file_location("qa",sys.argv[1]); '
        'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
        'v=m.load_bundle(sys.argv[2]); '
        'assert v["native_gpu_controller.py"].NativeCapController.production_qualified is False; '
        'assert v["native_gpu_health.py"].MODULE_BUILDS["nvidia"]["elf_sha256"]=="24b83a0ed1c676fccee3eb3d558d32b407a32f5ebd3e4a979bf468ac405e852c"; '
        'assert "ctypes" in sys.modules;print("exact-bundle-loaded")')
    actual = subprocess.run([sys.executable,'-I','-B','-c',command,str(HERE/'controller.py'),str(bundle)],
                            capture_output=True,text=True,timeout=5)
    assert actual.returncode == 0, actual.stderr
    assert actual.stdout.strip() == 'exact-bundle-loaded'

def test_inventory_rejects_unrelated_rows():
    m = module()
    row = dict(cgroup_id=31, kernfs_id=31, inode=31, offline=False, pinned=True,
               default_hierarchy=True, soft=5120*1048576, hard=5120*1048576, used=0)
    value = {'version': 1, 'backend': 'misc-fallback', 'gpu_uuid': m.GPU, 'gpu_id': 0, 'entries': [row]}
    m.inventory(value, {31})
    with pytest.raises(ValueError, match='Unrelated'):
        m.inventory(value, {32})

def test_partial_transaction_cleanup_uses_actual_journal_and_full_stop_proof():
    # Existing real private-file/proc/cgroup fixture; no live driver/API.
    sys.path.insert(0, '/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/src')
    sys.path.insert(0, '/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/tests')
    from test_native_node_backend import NodeBackendTests
    fixture = NodeBackendTests()
    fixture.setUp()
    try:
        m = module()
        sealed = fixture.controller.reconcile(fixture.intent)
        writes = list(fixture.driver.writes)
        with pytest.raises(ValueError):
            m.cleanup_records(fixture.controller, fixture.journal, [fixture.intent])
        assert fixture.driver.writes == writes
        assert fixture.journal.read(fixture.intent.pod_uid).state == 'sealed'
        fixture.stop()
        result = m.cleanup_records(fixture.controller, fixture.journal, [fixture.intent])
        assert result[0].state == 'cleaned'
        assert result[0].intent == sealed.intent and result[0].identity == sealed.identity
        assert fixture.backend.read_gate(sealed.identity) is None
        assert fixture.journal.read(fixture.intent.pod_uid) == result[0]
    finally: fixture.doCleanups()

@pytest.mark.parametrize('changed',[
    {'namespace':'foreign'}, {'node_uid':'11111111-1111-4111-8111-111111111111'},
    {'gpu_uuid':'GPU-11111111-1111-4111-8111-111111111111'}, {'cap_mib':10240}])
def test_wrong_fresh_cohort_denies_before_host_or_api_observation(tmp_path, monkeypatch, changed):
    m = module()
    sys.path.insert(0, str(m.SDK))
    from cps_compute import native_gpu_controller as models
    modules = {name:SimpleNamespace() for name in m.PINS}
    modules['native_gpu_controller.py'] = models
    monkeypatch.setattr(m,'load_bundle',lambda _:modules)
    monkeypatch.setattr(m.os,'geteuid',lambda:0)
    intent = dict(namespace=m.NS,name='native-qa147-a',pod_uid='11111111-1111-4111-8111-111111111111',
        node=m.NODE,node_uid=m.NODE_UID,spec_sha256='a'*64,gpu_uuid=m.GPU,cap_mib=5120,policy_hash='sha256:'+'b'*64)
    intent.update(changed)
    raw = json.dumps(intent).encode()
    path = tmp_path/'intent.json'; path.write_bytes(raw)
    args = SimpleNamespace(approve_qa_hostpaths=True,state_root=m.STATE,bundle='unused',intent_a=path,
        intent_a_sha256=hashlib.sha256(raw).hexdigest(),intent_b=path,intent_b_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError,match='Exact fresh QA cohort'):
        m.execute(args)

def test_retirement_requires_original_protected_record_and_fresh_exact_sdk_proof():
    sys.path[:0]=['/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/src',
                  '/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/tests']
    from test_native_node_backend import NodeBackendTests
    f=NodeBackendTests();f.setUp()
    try:
        m=module();record=f.controller.reconcile(f.intent)
        f.stop();f.pod=None;shutil.rmtree(f.group);f.retired_inventory(record)
        original=f.controller.cleanup(f.intent)
        rows=m.verify_retirements(f.backend,f.journal,[original])
        assert rows[original.identity.cgroup_inode]['offline'] is True
        f.retired_inventory(original,used=1)
        with pytest.raises(ValueError):m.verify_retirements(f.backend,f.journal,[original])
        assert f.journal.read(f.intent.pod_uid)==original
    finally:f.doCleanups()
