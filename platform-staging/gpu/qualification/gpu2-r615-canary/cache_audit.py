#!/usr/bin/env python3
"""Read local GPU2 cache status and public manager descriptor sizes; never pull."""
import datetime
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
POD = "nvidia-driver-daemonset-ssr7r"
CTR = "/proc/1/root/var/lib/rancher/k3s/data/65415f7708224bbfc7865f032e84da4a5123a3acebef70c8ee40fa991aa68555/bin/ctr"
SOCKET = "/proc/1/root/run/k3s/containerd/containerd.sock"
EXEC = ["kubectl", "-n", "gpu-operator", "exec", POD, "-c", "nvidia-driver-ctr", "--"]
COMMAND = EXEC + [CTR, "--address", SOCKET, "--namespace", "k8s.io"]
OLD = "nvcr.io/nvidia/driver@sha256:41515698692bd5e192186e620b65717af960a66d22dbb5a06e3656575a5d9148"
NEW = "nvcr.io/nvidia/driver@sha256:bc7572b7f14177c467e4dd8b66c4f4535f462ea9cf6a65cebd7603cc966ebbd7"
MANAGER_DIGEST = "sha256:a6c12abacc9c4f51d3653c90fcad32f19799069889338601407eba05fea4ba18"
MANAGER = "nvcr.io/nvidia/cloud-native/k8s-driver-manager@" + MANAGER_DIGEST


def read(*args):
    return subprocess.check_output(COMMAND + list(args), text=True)


if __name__ == "__main__":
    node = json.loads(subprocess.check_output(["kubectl", "get", "node", "k3s-wk-gpu2", "-o", "json"]))
    assert node["metadata"]["uid"] == "3336cdd5-d245-436e-b57c-2f66c6dcaa41"
    pod = json.loads(subprocess.check_output(["kubectl", "-n", "gpu-operator", "get", "pod", POD, "-o", "json"]))
    assert pod["metadata"]["uid"] == "b72e0314-256d-44a5-83ec-b6a8cc180447"
    assert pod["spec"]["nodeName"] == "k3s-wk-gpu2"
    receipt = {"observedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "nodeUID": node["metadata"]["uid"], "driverPodUID": pod["metadata"]["uid"],
               "operations": "local metadata and file-size reads only; no pull",
               "images": [{"reference": ref, "check": read("images", "check", "--snapshotter", "overlayfs", "name==" + ref)}
                          for ref in (OLD, MANAGER, NEW)]}
    index = json.loads(read("content", "get", MANAGER_DIGEST))
    child = next(m for m in index["manifests"] if m.get("platform", {}).get("architecture") == "amd64"
                 and m["platform"].get("os") == "linux")
    manifest = json.loads(read("content", "get", child["digest"]))
    descriptors = [child, manifest["config"], *manifest["layers"]]
    prefix = "/proc/1/root/var/lib/rancher/k3s/agent/containerd/io.containerd.content.v1.content/blobs/sha256/"
    script = "set -eu\n" + "\n".join("if test -f " + prefix + d["digest"].split(":")[1]
        + "; then stat -c '%s' " + prefix + d["digest"].split(":")[1] + "; else echo MISSING; fi"
        for d in descriptors) + "\n"
    sizes = subprocess.check_output(EXEC[:-1] + ["-i", "--", "sh", "-s"], input=script, text=True).splitlines()
    assert len(sizes) == len(descriptors)
    receipt["managerAmd64"] = {"manifest": child["digest"], "descriptors": [
        {"digest": d["digest"], "expectedSize": d["size"],
         "actualSize": None if size == "MISSING" else int(size),
         "sizeMatched": size != "MISSING" and int(size) == d["size"]}
        for d, size in zip(descriptors, sizes)]}
    receipt["managerAmd64"]["contentComplete"] = all(d["sizeMatched"] for d in receipt["managerAmd64"]["descriptors"])
    (HERE / "cache-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"written": "cache-receipt.json", "managerAmd64ContentComplete": receipt["managerAmd64"]["contentComplete"]}))
