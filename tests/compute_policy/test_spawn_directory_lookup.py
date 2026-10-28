"""Exercise the UID/GID part of the shipped CPS spawn hook without a directory."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import yaml

from cps_compute_hub.directory_identity import DirectoryIdentityCache

ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / 'cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml'


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
                 'PROFILE_CONFIGS': {'cpu-default': {}}, 'getattr': getattr}
    exec(compile(ast.Module(body=[hook], type_ignores=[]), str(VALUES), 'exec'), namespace)
    async def run():
        for _ in range(2):
            spawner = SimpleNamespace(user_options={'profile': 'cpu-default'},
                                      user=SimpleNamespace(name='student'), log=log)
            await namespace['apply_profile_settings'](spawner)
            assert (spawner.uid, spawner.gid, spawner.fs_gid) == (1234, 456, 456)
        assert calls == ['student']
    asyncio.run(run())
