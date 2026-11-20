#!/usr/bin/env python3
"""Prepare private GPU2-only CAS patches. Never applies a Kubernetes mutation."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
NODE = "k3s-wk-gpu2"
UID = "3336cdd5-d245-436e-b57c-2f66c6dcaa41"
KEYS = ("accelerator", "nvidia.com/gpu.deploy.device-plugin",
        "nvidia.com/gpu.deploy.dcgm-exporter",
        "nvidia.com/gpu.deploy.gpu-feature-discovery",
        "nvidia.com/gpu.deploy.operator-validator")
DRIVER_KEY = "nvidia.com/gpu.deploy.driver"


def get(*args):
    return json.loads(subprocess.check_output(["kubectl", *args, "-o", "json"]))


def ready(pod):
    return any(c["type"] == "Ready" and c["status"] == "True"
               for c in pod.get("status", {}).get("conditions", []))


def summary(pod):
    return {"namespace": pod["metadata"]["namespace"],
            "name": pod["metadata"]["name"], "uid": pod["metadata"]["uid"],
            "node": pod["spec"].get("nodeName"), "ready": ready(pod),
            "containers": [{"name": c["name"], "imageID": c.get("imageID"),
                            "restartCount": c.get("restartCount", 0)}
                           for c in pod["status"].get("containerStatuses", [])]}


def private_write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def path_for_label(key):
    return "/metadata/labels/" + key.replace("~", "~0").replace("/", "~1")


def prepare(stage, directory):
    node = get("get", "node", NODE)
    assert node["metadata"]["uid"] == UID, "GPU2 node was replaced"
    pods = [p for p in get("get", "pods", "-A")["items"]
            if p["status"]["phase"] not in ("Succeeded", "Failed")]
    baseline = json.loads((HERE / "preflight.json").read_text())
    by_name = {(p["metadata"]["namespace"], p["metadata"]["name"]): p for p in pods}
    for expected in baseline["protectedGpuDriverPods"]:
        if expected["node"] == NODE and stage == "restore":
            continue
        pod = by_name[("gpu-operator", expected["name"])]
        assert pod["metadata"]["uid"] == expected["uid"], "protected driver UID drift"
        assert ready(pod), "protected driver not Ready"
        assert [c.get("imageID") for c in pod["status"]["containerStatuses"]] == expected["imageIds"]
    for expected in baseline["protectedPvcPods"]:
        pod = by_name[(expected["namespace"], expected["name"])]
        assert pod["metadata"]["uid"] == expected["uid"] and ready(pod), "critical PVC Pod drift"
    patch = [{"op": "test", "path": "/metadata/uid", "value": UID},
             {"op": "test", "path": "/metadata/resourceVersion",
              "value": node["metadata"]["resourceVersion"]}]
    labels = node["metadata"]["labels"]
    journal_path = directory / "before.json"
    if stage == "consumers":
        assert not journal_path.exists(), "reuse the existing journal instead of overwriting it"
        assert labels.get("accelerator") == "nvidia"
        assert labels.get(DRIVER_KEY) == "true"
        assert all(labels.get(key) == "true" for key in KEYS[1:])
        for pod in pods:
            if pod["spec"].get("nodeName") != NODE:
                continue
            assert ready(pod), "GPU2 Pod not Ready"
            for container in pod["spec"].get("containers", []) + pod["spec"].get("initContainers", []):
                for resource_type in ("requests", "limits"):
                    assert not any(any(s in key.lower() for s in ("gpu", "nvidia", "hami", "dmem"))
                                   and str(value) not in ("0", "0m")
                                   for key, value in container.get("resources", {}).get(resource_type, {}).items()), "GPU2 GPU allocation exists"
            assert "reservation" not in pod["metadata"]["namespace"].lower(), "GPU2 reservation exists"
            assert not any(any(s in key.lower() for s in ("kai", "gpu", "mps", "hami", "dmem"))
                           for key in pod["metadata"].get("annotations", {})), "GPU2 GPU binding annotation exists"
        journal = {"observedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "node": NODE, "uid": UID, "resourceVersion": node["metadata"]["resourceVersion"],
                   "unschedulable": node["spec"].get("unschedulable", False),
                   "labels": {key: labels.get(key) for key in (*KEYS, DRIVER_KEY)},
                   "untouchedMigManagerLabel": labels.get("nvidia.com/gpu.deploy.mig-manager"),
                   "pods": [summary(p) for p in pods if p["spec"].get("nodeName") in
                            (NODE, "k3s-wk-gpu1", "k3s-wk-gpu3", "k3s-wk-gpu4")]}
        private_write(journal_path, journal)
        patch.append({"op": "add", "path": "/spec/unschedulable", "value": True})
        for key in KEYS:
            patch.append({"op": "add", "path": path_for_label(key),
                          "value": "r615-canary-maintenance" if key == "accelerator" else "false"})
    else:
        journal = json.loads(journal_path.read_text())
        assert journal["uid"] == UID and journal["node"] == NODE
        assert node["spec"].get("unschedulable") is True
        assert labels.get("nvidia.com/gpu.deploy.mig-manager") == journal["untouchedMigManagerLabel"]
        if stage == "driver":
            assert all(labels.get(key) == ("r615-canary-maintenance" if key == "accelerator" else "false") for key in KEYS)
            assert labels.get(DRIVER_KEY) == "true"
            prefixes = ("mps-control-daemon-standalone-", "nvidia-device-plugin-daemonset-",
                        "nvidia-dcgm-exporter-", "gpu-feature-discovery-", "nvidia-operator-validator-")
            assert not any(p["spec"].get("nodeName") == NODE and p["metadata"]["name"].startswith(prefixes)
                           for p in pods), "GPU2 consumers still exist; inspect holders before stopping driver"
            patch.append({"op": "add", "path": path_for_label(DRIVER_KEY), "value": "false"})
        elif stage == "restore":
            assert labels.get(DRIVER_KEY) == "true", "root must recover R580 separately before restoring consumers"
            assert not any(p["spec"].get("nodeName") == NODE and
                           p["metadata"].get("labels", {}).get("app") == "gpu2-r615-driver-canary"
                           for p in pods), "owned canary still exists; never overlap driver ownership"
            legacy = [p for p in pods if p["spec"].get("nodeName") == NODE and
                      p["metadata"].get("labels", {}).get("app") == "nvidia-driver-daemonset"]
            assert len(legacy) == 1 and ready(legacy[0]), "R580 legacy driver must be Ready"
            assert [c.get("imageID") for c in legacy[0]["status"]["containerStatuses"]] == [
                "nvcr.io/nvidia/driver@sha256:41515698692bd5e192186e620b65717af960a66d22dbb5a06e3656575a5d9148"]
            version = subprocess.check_output(["kubectl", "-n", "gpu-operator", "exec",
                legacy[0]["metadata"]["name"], "-c", "nvidia-driver-ctr", "--", "nvidia-smi",
                "--query-gpu=driver_version,mig.mode.current,mig.mode.pending", "--format=csv,noheader"], text=True)
            assert version.splitlines() == ["580.95.05, Disabled, Disabled"] * 2, "actual R580/MIG-disabled recovery required"
            for key, value in journal["labels"].items():
                patch.append({"op": "remove", "path": path_for_label(key)} if value is None
                             else {"op": "add", "path": path_for_label(key), "value": value})
            patch.append({"op": "add", "path": "/spec/unschedulable", "value": journal["unschedulable"]})
        else:
            raise ValueError(stage)
    output = directory / (stage + ".patch.json")
    private_write(output, patch)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("consumers", "driver", "restore"))
    parser.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()
    args.journal.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert args.journal.stat().st_mode & 0o077 == 0, "journal directory must be private"
    output = prepare(args.stage, args.journal)
    print(json.dumps({"prepared": str(output), "applied": False,
                      "rootCommand": ["kubectl", "patch", "node", NODE, "--type=json", "--patch-file", str(output)]}))
