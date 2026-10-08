import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import server_validation


class ProbeIdentityTests(unittest.TestCase):
    def test_proxy_identity_mismatch_stops_before_admission_request(self):
        identity = {'exitCode': 0, 'stdout': json.dumps({'status': {'userInfo': {'username': 'proxy-user'}}}), 'stderr': ''}
        with patch.object(server_validation, 'kubectl', return_value=identity) as call:
            with self.assertRaisesRegex(RuntimeError, 'not authenticated'):
                server_validation.probe(Path('/unused'), 'fixture', {}, 'system:serviceaccount:review:probe')
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[0], ['auth', 'whoami', '-o', 'json'])


if __name__ == '__main__':
    unittest.main()
