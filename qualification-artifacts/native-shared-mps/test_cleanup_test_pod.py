import json
import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, Mock

import cleanup_test_pod as cleanup


class CleanupTestPodTests(unittest.TestCase):
    def test_uid_mismatch_never_deletes_replacement_pod(self):
        run = Mock(return_value=Mock(stdout=json.dumps({"metadata": {
            "uid": "11111111-2222-3333-4444-555555555555"
        }})))

        with self.assertRaisesRegex(RuntimeError, "UID changed"):
            cleanup.cleanup_pod("cps-qa", "mps-probe", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", run=run)

        run.assert_called_once_with(
            ["kubectl", "get", "pod", "mps-probe", "--namespace", "cps-qa", "-o", "json"],
            check=True, capture_output=True, text=True, timeout=30,
        )

    def test_matching_uid_deletes_only_the_reviewed_pod_with_uid_precondition(self):
        uid = "11111111-2222-3333-4444-555555555555"
        run = Mock(return_value=Mock(stdout=json.dumps({"metadata": {"uid": uid}})))
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"kind":"Status"}'
        open_url = Mock(return_value=response)

        with unittest.mock.patch.object(cleanup, "urlopen", open_url), \
                unittest.mock.patch.object(cleanup, "api_proxy", return_value=nullcontext("http://127.0.0.1:8001")):
            result = cleanup.cleanup_pod("cps-qa", "mps-probe", uid, run=run)

        self.assertIn("Status", result)
        run.assert_called_once_with(
            ["kubectl", "get", "pod", "mps-probe", "--namespace", "cps-qa", "-o", "json"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        request = open_url.call_args.args[0]
        self.assertEqual(request.method, "DELETE")
        self.assertEqual(request.full_url, "http://127.0.0.1:8001/api/v1/namespaces/cps-qa/pods/mps-probe")
        self.assertEqual(json.loads(request.data), {
            "apiVersion": "v1", "kind": "DeleteOptions",
            "preconditions": {"uid": uid},
        })

    def test_invalid_identity_is_rejected_before_kubectl(self):
        run = Mock()

        with self.assertRaisesRegex(ValueError, "Kubernetes namespace"):
            cleanup.cleanup_pod("--all", "mps-probe", "11111111-2222-3333-4444-555555555555", run=run)

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
