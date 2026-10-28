"""Exercise the UID/GID part of the shipped CPS spawn hook without a directory."""
import ast
import asyncio
import importlib.machinery
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import yaml

# These pure helpers do not require the Hub package's eager runtime imports.
# Load only the package namespace so the test stays independent of Kubernetes
# client dependencies which are unrelated to profile validation/cache behavior.
_package_spec = importlib.machinery.PathFinder.find_spec('cps_compute_hub')
if _package_spec is not None:
    _package = types.ModuleType('cps_compute_hub')
    _package.__path__ = list(_package_spec.submodule_search_locations or [])
    sys.modules.setdefault('cps_compute_hub', _package)

from cps_compute_hub.directory_identity import DirectoryIdentityCache
from cps_compute_hub.legacy_profile_request import validate_legacy_profile_request
from kubespawner import KubeSpawner

ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / 'cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml'


def make_spawner(options, profiles=None):
    spawner = KubeSpawner(_mock=True)
    spawner.user_options = options
    spawner.user.name = 'student'
    spawner.profile_list = profiles or [{'slug': 'cpu-default', 'display_name': 'CPU', 'default': True}]
    return spawner


def test_spawn_directory_lookup_uses_packaged_nonblocking_cache():
    code = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    tree = ast.parse(code)
    hook = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'apply_profile_settings')
    # Keep the actual hook through UID/GID assignment; storage, SSH and native
    # scheduling have separate effects and are intentionally not executed here.
    end = next(i for i, n in enumerate(hook.body) if isinstance(n, ast.If)
               and ast.unparse(n.test) == 'not mount_nfs')
    hook.body = hook.body[:end]
    calls = []
    def lookup(name, log):
        calls.append(name)
        return {'uid': 1234, 'gid': 456}
    log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)
    namespace = {'get_ldap_info': lookup, 'directory_identities': DirectoryIdentityCache(lookup),
                 'PROFILE_CONFIGS': {'cpu-default': {}}, 'getattr': getattr,
                 'get_profile_list': lambda spawner: [{'slug': 'cpu-default', 'default': True}]}
    exec(compile(ast.Module(body=[hook], type_ignores=[]), str(VALUES), 'exec'), namespace)
    async def run():
        for _ in range(2):
            spawner = make_spawner({'profile': 'cpu-default'})
            await namespace['apply_profile_settings'](spawner)
            assert (spawner.uid, spawner.gid, spawner.fs_gid) == (1234, 456, 456)
        assert calls == ['student']
    asyncio.run(run())


def test_forged_spawn_options_fail_before_directory_lookup_or_spawner_mutation():
    code = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    tree = ast.parse(code)
    hook = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'apply_profile_settings')
    ldap_line = next(i for i, n in enumerate(hook.body)
                     if isinstance(n, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id == 'ldap_info'
                         for target in n.targets))
    hook.body = hook.body[:ldap_line + 1]
    calls = []

    def lookup(name, log):
        calls.append(name)
        return {'uid': 1000, 'gid': 100}

    log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)
    namespace = {
        'validate_legacy_profile_request': validate_legacy_profile_request,
        'get_profile_list': lambda spawner: [{'slug': 'cpu-default', 'default': True}],
        'directory_identities': DirectoryIdentityCache(lookup),
        'PROFILE_CONFIGS': {'cpu-default': {}},
        'getattr': getattr,
    }
    exec(compile(ast.Module(body=[hook], type_ignores=[]), str(VALUES), 'exec'), namespace)

    async def run():
        forged_requests = [
            {'profile': 'cpu-default', 'custom_nfs_enabled': True,
             'custom_nfs_server': 'arbitrary.example', 'custom_nfs_path': '/export',
             'custom_nfs_mount_path': '/home/jovyan/data'},
            {'profile': 'cpu-default', 'custom_gpus': 1},
            {'profile': 'cpu-default', 'custom_image': 'attacker/image:latest'},
            {'profile': 'not-approved'},
        ]
        for options in forged_requests:
            forged = make_spawner(options)
            before_ids = (forged.uid, forged.gid, forged.fs_gid)
            with __import__('pytest').raises(ValueError, match='fixed approved profile'):
                await namespace['apply_profile_settings'](forged)
            assert (forged.uid, forged.gid, forged.fs_gid) == before_ids
        assert calls == []

    asyncio.run(run())


def test_empty_default_rest_options_resolve_only_through_server_default_profile():
    code = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    tree = ast.parse(code)
    hook = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'apply_profile_settings')
    end = next(i for i, n in enumerate(hook.body) if isinstance(n, ast.If)
               and ast.unparse(n.test) == 'not mount_nfs')
    hook.body = hook.body[:end]
    calls = []

    def lookup(name, log):
        calls.append(name)
        return {'uid': 1234, 'gid': 456}

    log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)
    namespace = {
        'directory_identities': DirectoryIdentityCache(lookup),
        'PROFILE_CONFIGS': {'cpu-default': {}},
        'get_profile_list': lambda spawner: [{'slug': 'cpu-default', 'default': True}],
        'getattr': getattr,
    }
    exec(compile(ast.Module(body=[hook], type_ignores=[]), str(VALUES), 'exec'), namespace)

    async def run():
        spawner = make_spawner({})
        await namespace['apply_profile_settings'](spawner)
        assert (spawner.uid, spawner.gid, spawner.fs_gid) == (1234, 456, 456)
        assert calls == ['student']

    asyncio.run(run())


def test_unbacked_dask_and_slurm_profiles_are_not_server_resolved_choices():
    code = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    tree = ast.parse(code)
    profile_list = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_profile_list')
    namespace = {
        'PROFILE_CONFIGS': {
            'cpu-default': {'display_name': 'CPU', 'gpu': 0},
            'dask-cluster': {'display_name': 'Dask', 'gpu': 0},
            'gpu-slurm': {'display_name': 'Slurm', 'gpu': 0},
        },
        'is_power_user': lambda user: True,
        'is_student': lambda user: False,
    }
    exec(compile(ast.Module(body=[profile_list], type_ignores=[]), str(VALUES), 'exec'), namespace)
    choices = namespace['get_profile_list'](SimpleNamespace(user=SimpleNamespace()))
    assert [profile['slug'] for profile in choices] == ['cpu-default']


def test_student_priority_requires_student_membership_even_for_power_users():
    code = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    tree = ast.parse(code)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_profile_list')
    namespace = {
        'PROFILE_CONFIGS': {
            'cpu-default': {'display_name': 'CPU', 'gpu': 0},
            'gpu-student': {'display_name': 'Student', 'gpu': 1, 'student_profile': True},
        },
        'is_power_user': lambda user: True,
        'is_student': lambda user: False,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(VALUES), 'exec'), namespace)
    assert [p['slug'] for p in namespace['get_profile_list'](SimpleNamespace(user=None))] == ['cpu-default']


def test_hook_accepts_final_async_native_profile_before_directory_lookup():
    code = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    tree = ast.parse(code)
    hook = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'apply_profile_settings')
    hook.body = hook.body[:2]
    namespace = {}
    exec(compile(ast.Module(body=[hook], type_ignores=[]), str(VALUES), 'exec'), namespace)
    async def profiles(spawner):
        return [{'slug': 'cpu-default', 'display_name': 'CPU', 'default': True},
                {'slug': 'native-only', 'display_name': 'Native'}]
    async def run():
        spawner = make_spawner({'profile': 'native-only'}, profiles)
        await namespace['apply_profile_settings'](spawner)
    asyncio.run(run())
