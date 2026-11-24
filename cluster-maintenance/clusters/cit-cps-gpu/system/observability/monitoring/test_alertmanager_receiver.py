import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import HTTPServer
from unittest.mock import patch

import alertmanager_receiver as receiver


class ReceiverTest(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), receiver.Receiver)
        worker = threading.Thread(target=self.server.serve_forever)
        worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(worker.join)
        self.addCleanup(self.server.shutdown)
        self.connection = HTTPConnection(*self.server.server_address, timeout=5)
        self.addCleanup(self.connection.close)

    def send(self, alerts):
        self.connection.request("POST", "/alerts", json.dumps({"alerts": alerts}))
        response = self.connection.getresponse()
        response.read()
        return response.status

    @patch.object(receiver, "push_to_loki", return_value=204)
    def test_preserves_each_alert_status_and_omits_annotations(self, push):
        alerts = [
            {
                "status": status,
                "labels": {"alertname": "GPUOffline", "namespace": "gpu", "severity": "warning"},
                "annotations": {"summary": "contains private data"},
                "fingerprint": fingerprint,
            }
            for status, fingerprint in [("firing", "abc"), ("resolved", "def")]
        ]
        self.assertEqual(self.send(alerts), 204)
        stream = push.call_args.args[0]["streams"][0]
        self.assertEqual(stream["stream"], {"job": "alertmanager-notifications"})
        self.assertTrue(all(timestamp.isdigit() for timestamp, _ in stream["values"]))
        self.assertEqual(
            [json.loads(line) for _, line in stream["values"]],
            [
                {"status": status, "alertname": "GPUOffline", "namespace": "gpu",
                 "severity": "warning", "fingerprint": fingerprint}
                for status, fingerprint in [("firing", "abc"), ("resolved", "def")]
            ],
        )

    @patch.object(receiver, "push_to_loki", return_value=503)
    def test_loki_rejection_is_retryable(self, push):
        alerts = [{"status": "firing", "labels": {"alertname": "GPUOffline"}}]
        self.assertEqual(self.send(alerts), 503)
        push.side_effect = TimeoutError
        self.assertEqual(self.send(alerts), 503)

    @patch.object(receiver, "push_to_loki")
    def test_invalid_notification_is_rejected_before_forwarding(self, push):
        self.assertEqual(self.send([{"status": "unknown", "labels": {}}]), 400)
        push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
