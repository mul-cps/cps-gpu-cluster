import subprocess
import json
import sys

def run_kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"kubectl command failed: {result.stderr}")
    return result.stdout

def main():
    # Read the previously patched json
    with open("cm_patched.json", "r") as f:
        cm = json.load(f)

    # Remove metadata fields that might cause issues
    if "resourceVersion" in cm["metadata"]:
        del cm["metadata"]["resourceVersion"]
    if "uid" in cm["metadata"]:
        del cm["metadata"]["uid"]
    if "creationTimestamp" in cm["metadata"]:
        del cm["metadata"]["creationTimestamp"]

    # Write to file
    with open("cm_force_apply.json", "w") as f:
        json.dump(cm, f, indent=2)

    # Apply the updated configmap
    print("Applying updated ConfigMap (force)...")
    run_kubectl(["apply", "-f", "cm_force_apply.json"])
    
    # Verify content
    print("Verifying content on server...")
    cm_yaml = run_kubectl(["get", "configmap", "-n", "gpu-operator", "default-mig-parted-config", "-o", "yaml"])
    if "mixed-one-node-40gb-small" in cm_yaml:
        print("SUCCESS: Profile found in ConfigMap.")
    else:
        print("FAILURE: Profile NOT found in ConfigMap.")

if __name__ == "__main__":
    main()
