import importlib.util
from pathlib import Path
import sys
import pytest

HERE=Path(__file__).parent

def observer():
    s=importlib.util.spec_from_file_location('fresh_observe',HERE/'observe.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_original_sealed_journal_receipt_and_live_limit_are_all_required():
    sdk='/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023'
    sys.path[:0]=[sdk+'/src',sdk+'/tests']
    from test_native_node_backend import NodeBackendTests
    f=NodeBackendTests();f.setUp()
    try:
        m=observer();r=f.controller.reconcile(f.intent)
        value=m.sealed_record(f.backend,f.journal,f.intent)
        assert value['identity']==r.identity.to_dict() and value['limit']['hard']==5368709120
        (f.state/'receipts'/(f.intent.pod_uid+'.json')).unlink()
        with pytest.raises(ValueError):m.sealed_record(f.backend,f.journal,f.intent)
        assert f.journal.read(f.intent.pod_uid)==r
    finally:f.doCleanups()
