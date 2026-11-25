import json
from pathlib import Path
import subprocess
import sys

KEY = "k8s-sidecar-target-directory"
NAMESPACE = "cattle-dashboards"
FOLDER = {
    "home": "00 Cluster Operations",
    "k8s": "10 Kubernetes and Nodes",
    "gpu": "20 GPU and Scheduling",
    "storage": "30 Storage and Backups",
    "services": "40 Services and Teaching",
    "monitor": "50 Monitoring and Delivery",
    "reference": "90 Community References",
}
CPS = {
    "cps-cluster-overview": "home", "cps-storage-capacity": "storage",
    "cps-service-reliability": "services", "cps-worker-health": "gpu",
    "cps-alert-operations": "monitor", "cps-compute-overview-dashboard": "gpu",
    "cps-gpu-packing-dashboard": "gpu", "cps-kai-fairness-dashboard": "gpu",
    "cps-teaching-readiness-dashboard": "services",
    "arc-runner-monitoring-dashboard": "monitor",
    "nvidia-dcgm-official-dashboard-fleet": "gpu", "jupyterhub-stats-23694": "services",
}

def category(name):
    if name in CPS:
        return CPS[name]
    if name.startswith("gpu-dash-") or name.endswith(("-darwin", "-aix")):
        return "reference"
    if name == "rancher-default-dashboards-home":
        return "home"
    if "persistentvolume" in name or "longhorn" in name:
        return "storage"
    if name.startswith("rancher-fleet-") or any(
        name.startswith("rancher-monitoring-"+prefix) for prefix in ("alertmanager", "grafana", "prometheus")
    ):
        return "monitor"
    if name.startswith(("rancher-default-dashboards-", "rancher-monitoring-")):
        return "k8s"
    return None

def kube(*args):
    return subprocess.check_output(["kubectl","-n",NAMESPACE,*args],text=True)

inventory = json.loads(kube("get","cm","-l","grafana_dashboard=1","-o","json"))["items"]
previous = []
for cm in sorted(inventory,key=lambda cm:cm["metadata"]["name"]):
    meta = cm["metadata"]
    name = meta["name"]
    target = category(name)
    if not target:
        print("Unclassified:",name)
        continue
    folder = FOLDER[target]
    old = meta.get("annotations",{}).get(KEY)
    if old == folder:
        continue
    print(f"{name} -> {folder}")
    previous.append({"name":name,"uid":meta["uid"],"value":old})
    if "--apply" in sys.argv:
        patch = {"metadata":{"resourceVersion":meta["resourceVersion"],"annotations":{KEY:folder}}}
        kube("patch","cm",name,"--type=merge","-p",json.dumps(patch))
if "--apply" in sys.argv:
    Path("grafana-folder-changes.json").write_text(json.dumps(previous, indent=2)+"\n")
