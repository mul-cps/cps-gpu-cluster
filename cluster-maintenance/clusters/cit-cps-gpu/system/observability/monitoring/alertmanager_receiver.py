"""Write Alertmanager webhook notifications to the cluster Loki gateway."""

import json
import time
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, HTTPServer

MAX_BODY_BYTES = 4 * 1024 * 1024


def loki_payload(notification):
    alerts = notification["alerts"]
    if not isinstance(alerts, list) or not alerts:
        raise ValueError("expected a nonempty alert list")

    values = []
    for alert in alerts:
        labels = alert["labels"]
        status = alert["status"]
        if status not in ("firing", "resolved") or not labels["alertname"]:
            raise ValueError("invalid alert name or status")
        record = {"status": status}
        for source, keys in (
            (labels, ("alertname", "namespace", "severity")),
            (alert, ("fingerprint", "startsAt", "endsAt")),
        ):
            for key in keys:
                if key in source:
                    value = source[key]
                    if not isinstance(value, str):
                        raise ValueError("expected a string")
                    record[key] = value
        values.append([str(time.time_ns()), json.dumps(record, separators=(",", ":"))])

    return {
        "streams": [{"stream": {"job": "alertmanager-notifications"}, "values": values}]
    }


def push_to_loki(payload):
    connection = HTTPConnection("loki-gateway.loki.svc", timeout=5)
    try:
        connection.request(
            "POST",
            "/loki/api/v1/push",
            json.dumps(payload).encode(),
            {"Content-Type": "application/json"},
        )
        return connection.getresponse().status
    finally:
        connection.close()


class Receiver(BaseHTTPRequestHandler):
    timeout = 10

    def do_GET(self):
        self.reply(200 if self.path == "/readyz" else 404)

    def do_POST(self):
        if self.path != "/alerts":
            self.reply(404)
            return

        try:
            size = int(self.headers.get("Content-Length", ""))
            if size > MAX_BODY_BYTES:
                self.reply(413)
                return
            if size <= 0:
                raise ValueError("expected a body")
            payload = loki_payload(json.loads(self.rfile.read(size)))
        except (KeyError, TypeError, ValueError, OSError):
            self.reply(400)
            return

        try:
            status = push_to_loki(payload)
        except (OSError, HTTPException) as error:
            self.log_error("Loki push failed (%s)", type(error).__name__)
            self.reply(503)
            return

        if status != 204:
            self.log_error("Loki push returned %s", status)
            self.reply(503)
            return

        self.reply(204)

    def reply(self, status):
        self.send_response(status)
        self.end_headers()

    def log_request(self, code="-", size="-"):
        if self.path != "/readyz":
            super().log_request(code, size)


if __name__ == "__main__":
    with HTTPServer(("0.0.0.0", 8080), Receiver) as server:
        server.serve_forever()
