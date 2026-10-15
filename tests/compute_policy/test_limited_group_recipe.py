"""Offline regressions for the frozen LIMITED group activation recipe."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'platform-staging/gpu/native-group-pilot/limited_group_recipe.py'
INPUTS = MODULE.parent / 'qualification/limited-group-20261012'


class LimitedGroupRecipeTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('limited_group_recipe', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_default_cli_performs_no_render(self):
        result = subprocess.run([sys.executable, str(MODULE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'rendered': False, 'activationPerformed': False})

    def test_runtime_overlay_removes_all_stale_qualification_fields(self):
        rendered = self.load().render(INPUTS)
        overlay = rendered['gateway-runtime-overlay.json']
        existing = {'preserved': {'opaqueCredentialRef': 'existing-ref'},
            'nativeGpuQualification': {'enabled': True, 'node_pool': {'old': True}, 'workspaces': {'old': {}}},
            'nativeGpuPilot': {'enabled': True, 'native_pilot_workspaces': {'old': {}}}}
        updated = copy.deepcopy(existing)
        updated.update(overlay)
        self.assertEqual(updated['nativeGpuQualification'], {'enabled': False})
        self.assertEqual(updated['nativeGpuPilot'], {'enabled': False})
        self.assertEqual(updated['preserved'], existing['preserved'])
        self.assertEqual(set(updated['nativeGpuGroups']['workspaces']),
                         {'cps:native-group-b', 'cit:native-group-a'})
        self.assertEqual(updated['nativeGpuGroups']['evidence']['profile_caps'],
                         {'interactive-shared-5': 5120, 'interactive-shared-10': 10240})
        self.assertEqual(updated['nativeGpuGroups']['node_pool']['memory_budget_mib'], 15360)
        self.assertFalse(rendered['acceptance.json']['production_qualified'])
        self.assertFalse(rendered['acceptance.json']['full_fleet_qualified'])
        self.assertFalse(rendered['acceptance.json']['target_profile_start_stop_passed'])

    def test_group_hook_calls_group_installer_and_preserves_personal_pull_settings(self):
        rendered = self.load().render(INPUTS)
        # The actual installer reads the source service token. Replace that
        # external boundary; the generated hook and its delegation run intact.
        package = ModuleType('cps_compute'); package.__path__ = []
        configuration = ModuleType('cps_compute.native_hub_config')
        for source, owner in [('cps', 'cpsnativegroupb'), ('cit', 'citnativegroupa')]:
            settings = rendered[source + '-settings.json']
            calls = []
            c = SimpleNamespace(KubeSpawner=SimpleNamespace(), Spawner=SimpleNamespace())
            async def released(spawner):
                calls.append(spawner.user.name)
            def install(config, actual):
                self.assertIs(config, c)
                self.assertEqual(actual, settings)
                config.KubeSpawner.pre_spawn_hook = released
            configuration.install_native_group_hub_configuration = install
            modules = {'cps_compute': package, 'cps_compute.native_hub_config': configuration}
            with patch.dict(sys.modules, modules), patch.object(Path, 'read_text', return_value=json.dumps(settings)):
                exec(compile(rendered[source + '-hub-hook.py'], source + '-group-hook', 'exec'), {'c': c})
            neutral = SimpleNamespace(user=SimpleNamespace(name=owner), image_pull_secrets=[])
            human = SimpleNamespace(user=SimpleNamespace(name='human'), image_pull_secrets=['personal-pull'])
            asyncio.run(c.KubeSpawner.pre_spawn_hook(neutral))
            asyncio.run(c.KubeSpawner.pre_spawn_hook(human))
            self.assertEqual(calls, [owner, 'human'])
            self.assertEqual(neutral.image_pull_secrets, ['cps-native-image-pull'])
            self.assertEqual(human.image_pull_secrets, ['personal-pull'])

    def test_changed_source_bytes_fail_before_output_creation(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            ready = directory / 'ready'; ready.mkdir()
            for path in INPUTS.iterdir():
                (ready / path.name).write_bytes(path.read_bytes())
            settings = ready / 'cps-settings.json'
            settings.write_text(settings.read_text() + ' ')
            output = directory / 'output'
            with self.assertRaisesRegex(ValueError, 'changed.*cps-settings.json'):
                module.prepare(ready, output)
            self.assertFalse(output.exists())

    def test_prepare_emits_only_source_documents_and_refuses_existing_output(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'recipe'
            receipt = module.prepare(INPUTS, output)
            self.assertFalse(receipt['activationPerformed'])
            self.assertEqual(set(receipt['files']), {'gateway-runtime-overlay.json', 'cps-settings.json',
                'cit-settings.json', 'cps-hub-hook.py', 'cit-hub-hook.py', 'acceptance.json'})
            self.assertEqual(json.loads((output / 'cps-settings.json').read_text()),
                             json.loads((INPUTS / 'cps-settings.json').read_text()))
            with self.assertRaisesRegex(ValueError, 'new output'):
                module.prepare(INPUTS, output)


if __name__ == '__main__':
    unittest.main()
