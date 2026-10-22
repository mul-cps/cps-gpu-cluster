"""Real protected journal/retirement fixtures; no live API or GPU."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

HERE = Path(__file__).parent
SDK = '/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023'


@pytest.fixture
def retired_pair(tmp_path, monkeypatch):
    sys.path[:0] = [SDK+'/src', SDK+'/tests']
    import test_native_node_backend as fixture
    from cps_compute.native_node import backend
    spec = importlib.util.spec_from_file_location('qa_controller_v2', HERE/'controller.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    fixtures = []; records = []; states = []
    root = tmp_path/'qa'; root.mkdir(mode=0o700)
    monkeypatch.setattr(m, 'ROOT', str(root)); monkeypatch.setattr(m, 'STATE', str(root/'state'))
    for i, uid in enumerate(('11111111-1111-4111-8111-111111111111',
                             '22222222-2222-4222-8222-222222222222')):
        monkeypatch.setattr(fixture, 'UID', uid)
        f = fixture.NodeBackendTests(); f.setUp(); fixtures.append(f)
        record = f.controller.reconcile(f.intent)
        f.stop(); f.pod = None; shutil.rmtree(f.group); f.retired_inventory(record)
        record = f.controller.cleanup(f.intent); records.append(record)
        old = root/'state' if i == 0 else root/'cohorts/6ba3353d-bf13-4cad-9c35-3119dd279a67/state'
        old.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        f.state.rename(old); f.state = old; f.backend.state = old; f.journal.directory = old/'journal'
        states.append({'state_root': str(old), 'records': [record.to_dict()]})
    for name, value in (('NS',records[0].intent.namespace), ('NODE',records[0].intent.node),
                        ('NODE_UID',records[0].intent.node_uid), ('BOOT',records[0].identity.boot_id),
                        ('GENERATION',records[0].identity.driver_generation)):
        monkeypatch.setattr(m, name, value)
    current = root/'cohorts/7ba3353d-bf13-4cad-9c35-3119dd279a67/state'
    current.mkdir(parents=True, mode=0o700)
    actual = {str(f.state): f for f in fixtures}
    calls = []
    def make(enrolled, old):
        f = actual[old]; assert enrolled == [f.intent]; calls.append(old); return f.backend
    back = SimpleNamespace(private_directory=lambda path: backend.private_directory(path, os.getuid()))
    path = tmp_path/'retirements.json'
    value = {'version':2, 'states':states}
    def run(document=None, pin=None):
        raw = json.dumps(value if document is None else document).encode(); path.write_bytes(raw)
        args = SimpleNamespace(retirement=path, retirement_sha256=pin or hashlib.sha256(raw).hexdigest())
        return m.retirement_inputs(args, fixture.models, back, make, str(current))
    try:
        yield SimpleNamespace(module=m, fixtures=fixtures, records=records, value=value, run=run,
                              current=current, calls=calls, back=back, make=make, models=fixture.models)
    finally:
        for f in fixtures: f.doCleanups()


def test_two_original_states_require_both_complete_journals_and_fresh_proofs(retired_pair):
    p = retired_pair
    before = {str(f.state):{str(x.relative_to(f.state)):x.read_bytes() for x in f.state.rglob('*') if x.is_file()}
              for f in p.fixtures}
    rows = p.run()
    assert set(rows) == {r.identity.cgroup_inode for r in p.records}
    assert all(row['offline'] is True and row['used'] == 0 for row in rows.values())
    assert p.calls == [state['state_root'] for state in p.value['states']]
    assert before == {str(f.state):{str(x.relative_to(f.state)):x.read_bytes() for x in f.state.rglob('*') if x.is_file()}
                      for f in p.fixtures}
    p.fixtures[1].retired_inventory(p.records[1], used=1)
    with pytest.raises(ValueError): p.run()


def test_original_version1_descriptor_remains_supported(retired_pair):
    p = retired_pair
    assert set(p.run({'version':1, **p.value['states'][0]})) == {p.records[0].identity.cgroup_inode}


@pytest.mark.parametrize('mutation', ['extra','state-extra','bool','empty','too-many-states','too-many-records',
    'duplicate-state','duplicate-uid','duplicate-inode','current-state','traversal','missing-journal',
    'changed-journal','symlink-state','unsafe-state','wrong-hash'])
def test_multiple_original_states_fail_closed(retired_pair, mutation):
    p = retired_pair; value = deepcopy(p.value); pin = None
    if mutation == 'extra': value['unreviewed'] = True
    elif mutation == 'state-extra': value['states'][1]['unreviewed'] = True
    elif mutation == 'bool': value['version'] = True
    elif mutation == 'empty': value['states'] = []
    elif mutation == 'too-many-states': value['states'] *= 5
    elif mutation == 'too-many-records': value['states'][0]['records'] *= 17
    elif mutation == 'duplicate-state': value['states'][1]['state_root'] = value['states'][0]['state_root']
    elif mutation == 'duplicate-uid': value['states'][1]['records'] = deepcopy(value['states'][0]['records'])
    elif mutation == 'duplicate-inode':
        # A rehashed descriptor cannot alias an actual native parent across original journals.
        item = value['states'][1]['records'][0]
        item['identity']['cgroup_inode'] = p.records[0].identity.cgroup_inode
    elif mutation == 'current-state': value['states'][1]['state_root'] = str(p.current)
    elif mutation == 'traversal': value['states'][1]['state_root'] += '/../state'
    elif mutation == 'missing-journal': p.fixtures[1].journal.path(p.records[1].intent.pod_uid).unlink()
    elif mutation == 'changed-journal':
        p.fixtures[1].journal.path(p.records[1].intent.pod_uid).write_text('{}')
    elif mutation == 'symlink-state':
        old = p.fixtures[1].state; renamed = old.with_name('preserved'); old.rename(renamed); old.symlink_to(renamed)
    elif mutation == 'unsafe-state': p.fixtures[1].state.chmod(0o755)
    elif mutation == 'wrong-hash': pin = '0'*64
    with pytest.raises((ValueError, FileNotFoundError)): p.run(value, pin)


def test_state_directory_inode_alias_denied_before_backend_proof(retired_pair, monkeypatch):
    p = retired_pair; original = os.stat
    first = original(p.fixtures[0].state, follow_symlinks=False)
    def aliased(path, *args, **kwargs):
        if str(path) == str(p.fixtures[1].state): return first
        return original(path, *args, **kwargs)
    monkeypatch.setattr(p.module.os, 'stat', aliased)
    with pytest.raises(ValueError, match='directory aliases'): p.run()
    assert p.calls == []
