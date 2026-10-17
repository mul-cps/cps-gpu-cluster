import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

HERE = Path(__file__).parent
IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:' + 'a' * 64
SEED = b'{"version":1,"legacy":"exact original fixture"}\n'
SEED_HASH = 'sha256:' + hashlib.sha256(SEED).hexdigest()
STATE_HASH = 'sha256:' + 'b' * 64


def load(name):
    spec = importlib.util.spec_from_file_location('adoption_' + name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def inputs():
    config, configuration = load('test_render').fixture()
    return {'config': config, 'configuration': configuration, 'image': IMAGE,
        'config_secret': 'reviewed-adoption-inputs', 'journal_pvc': 'existing-delivery-journal',
        'job_name': 'cps-native-head-adoption-reviewed', 'legacy_state_sha256': STATE_HASH,
        'legacy_seed_sha256': SEED_HASH}


def test_job_uses_exact_installed_cli_one_attempt_and_readonly_original_journal():
    values = inputs(); original = copy.deepcopy(values['config'])
    job = load('adoption_job').render(**values)
    assert job['apiVersion'] == 'batch/v1' and job['kind'] == 'Job'
    assert job['metadata'] == {'namespace': 'cps-compute', 'name': values['job_name']}
    assert job['spec']['backoffLimit'] == 0 and job['spec']['activeDeadlineSeconds'] == 300
    assert job['spec']['parallelism'] == job['spec']['completions'] == 1
    pod = job['spec']['template']['spec']; assert pod['restartPolicy'] == 'Never'
    main = pod['containers'][0]
    assert main['command'] == ['python', '-I', '-B', '-m', 'cps_compute.native_approval_delivery']
    assert main['args'] == ['--config', '/inputs/delivery/delivery.json', '--state-dir', '/journal/delivery',
        '--execute', '--adopt-legacy', '--legacy-state', '/legacy/delivery/state.json',
        '--legacy-seed', '/inputs/delivery/legacy-seed.json', '--legacy-state-sha256', STATE_HASH,
        '--legacy-seed-sha256', SEED_HASH]
    assert {'name': 'journal', 'mountPath': '/legacy/delivery', 'subPath': 'delivery', 'readOnly': True} in main['volumeMounts']
    assert {'name': 'journal', 'mountPath': '/journal/delivery', 'subPath': 'head-delivery'} in main['volumeMounts']
    assert values['config'] == original


def test_job_reuses_reviewed_security_inputs_and_existing_service_account_without_permissions():
    values = inputs(); runtime = load('render')
    base = next(d for d in runtime.render(values['config'], configuration=values['configuration'], image=IMAGE,
        config_secret=values['config_secret'], journal_pvc=values['journal_pvc']) if d['kind'] == 'Deployment')
    job = load('adoption_job').render(**values)
    expected = copy.deepcopy(base['spec']['template']); actual = copy.deepcopy(job['spec']['template'])
    assert actual['spec']['initContainers'][0]['command'][-1].startswith(expected['spec']['initContainers'][0]['command'][-1])
    actual['spec']['initContainers'][0]['command'][-1] = expected['spec']['initContainers'][0]['command'][-1]
    actual['spec']['containers'][0]['args'] = expected['spec']['containers'][0]['args']
    actual['spec']['containers'][0]['volumeMounts'].pop()
    actual['spec'].pop('restartPolicy')
    assert actual == expected
    assert job['kind'] == 'Job' and 'rules' not in job and 'subjects' not in job
    assert job['spec']['template']['spec']['containers'][0]['securityContext']['runAsUser'] == 1000


@pytest.mark.parametrize('field,value', [
    ('legacy_state_sha256', None), ('legacy_state_sha256', 'b' * 64),
    ('legacy_seed_sha256', 'sha256:' + 'A' * 64), ('legacy_seed_sha256', 'sha256:' + '0' * 64),
    ('legacy_seed_sha256', 'sha256:' + 'a' * 63), ('job_name', ''), ('job_name', 'Unsafe_Name'),
    ('job_name', 'a' * 64), ('active_deadline_seconds', False), ('active_deadline_seconds', 0),
    ('active_deadline_seconds', 901)])
def test_invalid_byte_pins_or_job_bounds_are_rejected(field, value):
    values = inputs(); values[field] = value
    with pytest.raises(ValueError): load('adoption_job').render(**values)


def test_legacy_seed_cannot_shadow_existing_private_inputs():
    values = inputs(); values['config']['capture']['token_file'] = '/inputs/delivery/legacy-seed.json'
    with pytest.raises(ValueError): load('adoption_job').render(**values)


def test_job_reuses_actual_configuration_validation():
    values = inputs(); values['config']['node_configuration']['uid'] = str(uuid.uuid4())
    with pytest.raises(ValueError): load('adoption_job').render(**values)


@pytest.mark.parametrize('bad_seed', [False, True])
def test_actual_initializer_copies_exact_seed_private_and_preserves_old_inodes(tmp_path, bad_seed):
    values = inputs(); job = load('adoption_job').render(**values)
    init = job['spec']['template']['spec']['initContainers'][0]
    seed = tmp_path / 'seed'; seed.mkdir(); private = tmp_path / 'inputs'; private.mkdir()
    journal = tmp_path / 'journal'; journal.mkdir(); journal.chmod(0o2770)
    old = journal / 'delivery'; old.mkdir(mode=0o700)
    for name in ('state.json', 'lock'):
        (old / name).write_bytes(b'original ' + name.encode()); (old / name).chmod(0o600)
    before = {name: ((old / name).stat(), (old / name).read_bytes()) for name in ('state.json', 'lock')}
    for name in ('delivery.json', 'policy.json', 'gateway-ca.pem', 'export.token'):
        (seed / name).write_bytes(b'private fixture')
    (seed / 'legacy-seed.json').write_bytes(SEED + (b'tamper' if bad_seed else b''))
    code = init['command'][-1].replace('/inputs/delivery', str(private / 'delivery')).replace('/seed', str(seed)).replace('/journal', str(journal))
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True)
    assert result.returncode != 0 if bad_seed else result.returncode == 0
    target = private / 'delivery' / 'legacy-seed.json'
    if bad_seed: assert not target.exists()
    else:
        assert target.read_bytes() == SEED and target.stat().st_mode & 0o7777 == 0o600
        assert target.parent.stat().st_mode & 0o7777 == 0o700
    for name, (facts, raw) in before.items():
        after = (old / name).stat()
        assert (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid, after.st_nlink, after.st_mtime_ns) == (
            facts.st_dev, facts.st_ino, facts.st_mode, facts.st_uid, facts.st_gid, facts.st_nlink, facts.st_mtime_ns)
        assert (old / name).read_bytes() == raw
    assert journal.stat().st_mode & 0o7777 == 0o2770
