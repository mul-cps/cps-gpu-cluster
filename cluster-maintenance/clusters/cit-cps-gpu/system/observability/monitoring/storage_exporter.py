"""Prometheus metrics for Longhorn allocation and backup state."""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SA = Path("/var/run/secrets/kubernetes.io/serviceaccount")
API = "https://kubernetes.default.svc"
LONGHORN = "/apis/longhorn.io/v1beta2/namespaces/longhorn-system/"


def api_get(path):
    token = (SA / "token").read_text().strip()
    request = Request(API + path, headers={"Authorization": "Bearer " + token})
    context = ssl.create_default_context(cafile=str(SA / "ca.crt"))
    with urlopen(request, context=context, timeout=4) as response:
        return json.load(response)


def api_list(path):
    continuation = ""
    while True:
        query = {"limit": 250, "continue": continuation}
        page = api_get(path + "?" + urlencode(query))
        yield from page["items"]
        continuation = page["metadata"].get("continue")
        if not continuation:
            break


def list_objects(resource):
    return api_list(LONGHORN + resource)


def scheduled_headroom(maximum, reserved, scheduled, overprovisioning):
    return int(float(maximum - reserved) * overprovisioning / 100) - scheduled


def physical_headroom(maximum, available, minimum_percent):
    return available - int(float(maximum) * minimum_percent / 100)


def sample(metric, value, *, prefix="cps_longhorn_", **labels):
    suffix = ",".join(key + "=" + json.dumps(str(label), ensure_ascii=False)
                      for key, label in labels.items())
    return prefix + metric + ("{" + suffix + "}" if suffix else "") + f" {value}"


def epoch(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() if value else 0


def conditions(status):
    return {entry["type"]: entry["status"] for entry in status.get("conditions", [])}


def collect():
    settings = {}
    for name in ("storage-over-provisioning-percentage", "storage-minimal-available-percentage"):
        settings[name] = int(api_get(LONGHORN + "settings/" + name)["value"])
        yield sample("setting_percent", settings[name], setting=name)
    over = settings["storage-over-provisioning-percentage"]
    minimum = settings["storage-minimal-available-percentage"]
    for node in list_objects("nodes"):
        for name, disk in node.get("status", {}).get("diskStatus", {}).items():
            spec = node["spec"].get("disks", {}).get(name)
            maximum = disk.get("storageMaximum", 0)
            if not spec or not maximum:
                continue
            labels = {"node": node["metadata"]["name"], "disk": name, "path": spec["path"]}
            available, scheduled = disk["storageAvailable"], disk["storageScheduled"]
            reserved = spec.get("storageReserved", 0)
            for suffix, value in {
                "capacity_bytes": maximum,
                "available_bytes": available,
                "reserved_bytes": reserved,
                "scheduled_bytes": scheduled,
                "schedulable_bytes": scheduled_headroom(maximum, reserved, scheduled, over),
                "physical_headroom_bytes": physical_headroom(maximum, available, minimum),
                "replicas": len(disk.get("scheduledReplica") or {}),
            }.items():
                yield sample("disk_" + suffix, value, **labels)
    for target in list_objects("backuptargets"):
        state = conditions(target.get("status", {})).get("Unavailable")
        if state in {"True", "False"}:
            yield sample("backup_target_available", int(state == "False"), target=target["metadata"]["name"])
    for volume in list_objects("volumes"):
        meta, status = volume["metadata"], volume.get("status", {})
        if meta.get("labels", {}).get("recurring-job-group.longhorn.io/default") != "enabled":
            continue
        if status.get("state") != "attached":
            continue
        claim = status.get("kubernetesStatus", {})
        yield sample("last_backup_timestamp_seconds", epoch(status.get("lastBackupAt")),
                     volume=meta["name"], pvc_namespace=claim.get("namespace", ""),
                     pvc=claim.get("pvcName", ""))
    latest = {}
    for backup in list_objects("backups"):
        status = backup.get("status", {})
        labels = backup["metadata"].get("labels", {})
        volume = labels.get("backup-volume")
        state = status.get("state")
        if not volume or state not in {"Error", "Completed", "InProgress", "Pending", "Unknown"}:
            continue
        created = epoch(status.get("snapshotCreatedAt") or backup["metadata"].get("creationTimestamp"))
        key = (labels.get("backup-target", "default"), volume)
        if key not in latest or created > latest[key][0]:
            latest[key] = (created, state)
    for (target, volume), (_, state) in latest.items():
        yield sample("latest_backup_failed", int(state == "Error"), target=target, volume=volume)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/readyz":
            status, body = 200, b"ok\n"
        elif self.path in {"/metrics", "/workloads"}:
            collector = collect
            if self.path == "/workloads":
                from workload_allocations import collect as collect_workloads
                collector = collect_workloads
            try:
                status, body = 200, ("\n".join(collector()) + "\n").encode()
            except (OSError, ValueError, KeyError) as error:
                status, body = 503, b"Metrics unavailable\n"
                print(self.path, "scrape failed:", type(error).__name__, flush=True)
        else:
            status, body = 404, b"not found\n"
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    HTTPServer(("", 8080), Handler).serve_forever()
