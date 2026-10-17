"""Pure one-time legacy adoption Job using the reviewed delivery runtime.

Root must stop both writers and establish the external maintenance fences before
applying the result. This module creates no API objects or additional grants.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path, PurePosixPath
import re


def _runtime():
    spec = importlib.util.spec_from_file_location('native_head_delivery_runtime', Path(__file__).with_name('render.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def render(config, *, configuration, image, config_secret, journal_pvc, job_name,
           legacy_state_sha256, legacy_seed_sha256, namespace='cps-compute',
           image_pull_secret=None, active_deadline_seconds=300):
    """Return only a Job, reusing already-reviewed runtime identity/permissions.

    Hashes pin the original raw legacy state/seed bytes, including whitespace.
    The old journal is read-only; SDK adoption takes its existing lock read-only
    and independently validates the original state hash and actual authority.
    """
    runtime = _runtime()
    for pin in (legacy_state_sha256, legacy_seed_sha256):
        runtime.require(isinstance(pin, str) and re.fullmatch(r'sha256:[a-f0-9]{64}', pin)
            and pin != 'sha256:' + '0' * 64, 'Two explicit canonical original byte SHA-256 pins required')
    runtime.require(isinstance(job_name, str)
        and re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?', job_name), 'Explicit canonical Job name required')
    runtime.require(type(active_deadline_seconds) is int and 1 <= active_deadline_seconds <= 900,
                    'Finite one-time Job deadline from 1 through 900 seconds required')
    objects = runtime.render(config, configuration=configuration, image=image, config_secret=config_secret,
        journal_pvc=journal_pvc, namespace=namespace, image_pull_secret=image_pull_secret)
    runtime.require('legacy-seed.json' not in {PurePosixPath(value).name for value in
        (config['policy_path'], config['capture']['ca_file'], config['capture']['token_file'])},
        'Legacy seed must not shadow another protected input')
    deployment = next(value for value in objects if value['kind'] == 'Deployment')
    template = deepcopy(deployment['spec']['template']); pod = template['spec']
    pod['restartPolicy'] = 'Never'
    main = pod['containers'][0]
    main['args'] += ['--adopt-legacy', '--legacy-state', '/legacy/delivery/state.json',
        '--legacy-seed', '/inputs/delivery/legacy-seed.json', '--legacy-state-sha256', legacy_state_sha256,
        '--legacy-seed-sha256', legacy_seed_sha256]
    main['volumeMounts'].append({'name': 'journal', 'mountPath': '/legacy/delivery',
        'subPath': 'delivery', 'readOnly': True})
    # Keep the existing private input/journal initializer byte-for-byte, then
    # copy only this extra fixed Secret key. Neither its bytes nor any token is
    # embedded in the rendered Job. SDK also verifies the pin during adoption.
    pod['initContainers'][0]['command'][-1] += '''
import hashlib
raw = Path('/seed/legacy-seed.json').read_bytes()
if 'sha256:' + hashlib.sha256(raw).hexdigest() != ''' + repr(legacy_seed_sha256) + ''':
    raise ValueError('Original legacy seed byte pin differs')
fd = os.open('/inputs/delivery/legacy-seed.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'wb') as output:
    output.write(raw)
    output.flush()
    os.fsync(output.fileno())
'''
    return {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'namespace': namespace, 'name': job_name},
        'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': active_deadline_seconds,
            'parallelism': 1, 'completions': 1, 'template': template}}
