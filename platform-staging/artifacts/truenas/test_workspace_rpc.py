import base64
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('rpc', Path(__file__).resolve().parents[3] / 'scripts/compute-platform/truenas-workspace-rpc.py')
rpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpc)


class WorkspaceRPCTests(unittest.TestCase):
    def payload(self, **changes):
        data = dict(version=1, action='status', source='cps', group_id='../../existing-home', actor='operator', workspaces=['qualification'])
        data.update(changes)
        return 'cps-workspace-rpc ' + base64.b64encode(json.dumps(data).encode()).decode()

    def test_path_derived_even_for_malicious_group(self):
        data, path = rpc.request(self.payload())
        self.assertEqual(path.rsplit('/', 1)[0], rpc.ROOT + '/cps')
        self.assertEqual(len(path.rsplit('/', 1)[1]), 64)
        self.assertNotIn('..', path)

    def test_arbitrary_commands_and_fields_rejected(self):
        for command in ('sh -c id', self.payload(action='delete'), self.payload(path='/mnt/home'), self.payload(source='other')):
            with self.assertRaises(ValueError):
                rpc.request(command)

    def test_archived_dataset_never_reopened(self):
        data, path = rpc.request(self.payload(action='provision'))
        calls = []
        def call(method, *args):
            calls.append(method)
            return [{'mountpoint': '/mnt/' + path, 'readonly': {'value': 'ON'}}]
        with self.assertRaises(ValueError):
            rpc.execute(data, path, call)
        self.assertEqual(calls, ['pool.dataset.query'])

    def test_archive_requires_verified_property(self):
        data, path = rpc.request(self.payload(action='archive'))
        def call(method, *args):
            if method == 'pool.dataset.query':
                return [{'mountpoint': '/mnt/' + path, 'readonly': {'value': 'OFF'}}]
            self.assertEqual((method, args), ('pool.dataset.update', (path, {'readonly': 'ON'})))
        with self.assertRaises(ValueError):
            rpc.execute(data, path, call)

    def qualified_fixture(self, **changes):
        data, path = rpc.request(self.payload(action='provision'))
        row = {'mountpoint': '/mnt/' + path, 'readonly': {'value': 'OFF'},
               'acltype': {'value': 'POSIX'}, 'aclmode': {'value': 'DISCARD'}}
        stat = {'realpath': '/mnt/' + path, 'type': 'DIRECTORY', 'uid': 1000, 'gid': 1000, 'mode': 0o40770}
        acl = {'uid': 1000, 'gid': 1000, 'acltype': 'POSIX1E', 'trivial': True,
               'acl': [{'tag': tag, 'id': -1, 'default': False,
                        'perms': {key: tag != 'OTHER' for key in ('READ', 'WRITE', 'EXECUTE')}}
                       for tag in ('USER_OBJ', 'GROUP_OBJ', 'OTHER')]}
        row.update(changes.get('row', {})); stat.update(changes.get('stat', {})); acl.update(changes.get('acl', {}))
        calls = []
        def call(method, *args):
            calls.append(method)
            if method == 'pool.dataset.query': return [row]
            if method == 'filesystem.stat': return stat
            if method == 'filesystem.getacl': return acl
            if method == 'sharing.nfs.query': return []
            if method == 'sharing.nfs.create': return {'id': 1}
            raise AssertionError(method)
        return data, path, call, calls

    def test_existing_private_posix_workspace_verified_before_export(self):
        data, path, call, calls = self.qualified_fixture()
        result = rpc.execute(data, path, call)
        self.assertTrue(result['evidence']['permissions_verified'])
        self.assertLess(calls.index('filesystem.getacl'), calls.index('sharing.nfs.create'))
        self.assertNotIn('filesystem.setperm', calls)

    def test_unsafe_existing_storage_rejected_without_export_or_permission_rewrite(self):
        for changes in ({'row': {'acltype': {'value': 'NFSV4'}}},
                        {'row': {'aclmode': {'value': 'PASSTHROUGH'}}},
                        {'stat': {'mode': 0o40777}}, {'stat': {'uid': 950}},
                        {'stat': {'gid': 100}}, {'stat': {'realpath': '/mnt/elsewhere'}},
                        {'acl': {'trivial': False}}, {'acl': {'acltype': 'NFS4'}},
                        {'acl': {'acl': []}}, {'acl': {'uid': 950}}):
            with self.subTest(changes=changes):
                data, path, call, calls = self.qualified_fixture(**changes)
                with self.assertRaises(ValueError): rpc.execute(data, path, call)
                self.assertNotIn('sharing.nfs.create', calls)
                self.assertNotIn('filesystem.setperm', calls)


    def test_v2_uses_isolated_root_without_changing_v1_identifiers(self):
        _, legacy = rpc.request(self.payload(version=1))
        _, isolated = rpc.request(self.payload(version=2))
        self.assertEqual(legacy.rsplit('/', 1)[0], 'persistent1/cps_persistent1_shared/compute/cps')
        self.assertEqual(isolated.rsplit('/', 1)[0], 'persistent1/cps_compute_workspaces/cps')
        self.assertEqual(legacy.rsplit('/', 1)[1], isolated.rsplit('/', 1)[1])
        for version in (True, False, 0, 3, '2'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                rpc.request(self.payload(version=version))

    def test_v2_provision_only_creates_isolated_parents(self):
        data, path = rpc.request(self.payload(version=2, action='provision'))
        created = []
        class StopBeforePermissions(Exception): pass
        def call(method, *args):
            if method == 'pool.dataset.query': return []
            if method == 'pool.dataset.create':
                created.append(args[0]['name'])
                if len(created) == 3: raise StopBeforePermissions()
                return {}
            raise AssertionError(method)
        with self.assertRaises(StopBeforePermissions): rpc.execute(data, path, call)
        self.assertEqual(created, ['persistent1/cps_compute_workspaces',
                                   'persistent1/cps_compute_workspaces/cps', path])

    def test_execute_refuses_version_path_mismatch_before_middleware(self):
        data, legacy = rpc.request(self.payload(version=1, action='provision'))
        data['version'] = 2
        def call(*args): raise AssertionError('Mismatch must not reach middleware')
        with self.assertRaises(ValueError): rpc.execute(data, legacy, call)


if __name__ == '__main__':
    unittest.main()
