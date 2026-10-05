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


if __name__ == '__main__':
    unittest.main()
