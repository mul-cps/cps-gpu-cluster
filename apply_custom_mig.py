import subprocess
import json
import sys
import time

def run_kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"kubectl command failed: {result.stderr}")
    return result.stdout

def main():
    # Read the patched json
    with open("cm_patched.json", "r") as f:
        cm = json.load(f)

    # Modify metadata for new ConfigMap
    cm["metadata"] = {
        "name": "custom-mig-parted-config",
        "namespace": "gpu-operator"
    }

    # Write to file
    with open("custom_cm.json", "w") as f:
        json.dump(cm, f, indent=2)

    # Apply the new configmap
    print("Applying custom ConfigMap...")
    run_kubectl(["apply", "-f", "custom_cm.json"])

    # Patch ClusterPolicy
    print("Patching ClusterPolicy...")
    patch = {
        "spec": {
            "migManager": {
                "config": {
                    "name": "custom-mig-parted-config"
                }
            }
        }
    }
    patch_json = json.dumps(patch)
    run_kubectl(["patch", "clusterpolicy", "cluster-policy", "--type=merge", "-p", patch_json])

    print("Done. Waiting for operator to reconcile...")
    time.sleep(5)
    
    # Check if pods are restarting (optional, but good to know)
    pods = run_kubectl(["get", "pods", "-n", "gpu-operator", "-l", "app=nvidia-mig-manager"])
    print(pods)

if __name__ == "__main__":
    main()
