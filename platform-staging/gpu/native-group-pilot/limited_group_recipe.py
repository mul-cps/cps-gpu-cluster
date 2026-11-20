#!/usr/bin/env python3
"""Render the frozen LIMITED two-group source recipe, with no live transport."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORD = HERE / 'qualification/limited-group-20261012/record.json'


def group_hook(owners):
    """Delegate the released group hook before the existing machine pull rule."""
    return f'''import json
import inspect as _native_pull_inspect
from pathlib import Path
from cps_compute.native_hub_config import install_native_group_hub_configuration
install_native_group_hub_configuration(c, json.loads(Path('/etc/cps-native-hub/settings.json').read_text()))
_native_released_pre = c.KubeSpawner.pre_spawn_hook
_native_pull_owners = frozenset({sorted(owners)!r})
async def _native_private_pull_pre(spawner):
    result = _native_released_pre(spawner)
    if _native_pull_inspect.isawaitable(result):
        await result
    if spawner.user.name in _native_pull_owners:
        spawner.image_pull_secrets = ['cps-native-image-pull']
c.Spawner.pre_spawn_hook = c.KubeSpawner.pre_spawn_hook = _native_private_pull_pre
'''


def render(ready):
    """Read only the three pinned sanitized source configurations."""
    record = json.loads(RECORD.read_text())
    inputs = {}
    for name, checksum in record['inputs'].items():
        raw = (Path(ready) / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError('changed reviewed source bytes: ' + name)
        inputs[name] = json.loads(raw)
    groups = inputs['native-groups.json']
    if groups['policy_hash'] != record['target_policy_hash']:
        raise ValueError('Exact reviewed target policy required')
    outputs = {'gateway-runtime-overlay.json': {
        'policy_hash': record['target_policy_hash'],
        'nativeGpuGroups': groups,
        'nativeGpuQualification': {'enabled': False},
        'nativeGpuPilot': {'enabled': False}}}
    for source in ('cps', 'cit'):
        settings = inputs[source + '-settings.json']
        if settings['source'] != source or settings['groupDeployment'] != groups:
            raise ValueError('Exact source-owned reviewed group settings required')
        outputs[source + '-settings.json'] = settings
        outputs[source + '-hub-hook.py'] = group_hook(settings['owners'])
    outputs['acceptance.json'] = {key: record[key] for key in (
        'scope', 'target_policy_hash', 'production_qualified', 'full_fleet_qualified',
        'target_profile_start_stop_passed', 'remaining_live_acceptance')}
    outputs['acceptance.json'].update(activationPerformed=False,
        status='offline-source-recipe', hardwareAcceptancePerformed=False)
    return outputs


def prepare(ready, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('A new output directory is required')
    documents = render(ready)
    output.mkdir(mode=0o700)
    for name, value in documents.items():
        content = value if name.endswith('.py') else json.dumps(value, indent=2, sort_keys=True) + '\n'
        with (output / name).open('x') as stream:
            stream.write(content)
        (output / name).chmod(0o600)
    return {'rendered': True, 'activationPerformed': False, 'files': sorted(documents)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--ready', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not args.render:
        print(json.dumps({'rendered': False, 'activationPerformed': False}))
        return
    if args.ready is None or args.output is None:
        parser.error('--render requires --ready and --output')
    print(json.dumps(prepare(args.ready, args.output)))


if __name__ == '__main__':
    main()
