import subprocess
import json
import sys

def run_kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"kubectl command failed: {result.stderr}")
    return result.stdout

def main():
    # Get current configmap as JSON
    print("Fetching ConfigMap as JSON...")
    cm_json_str = run_kubectl(["get", "configmap", "-n", "gpu-operator", "default-mig-parted-config", "-o", "json"])
    cm = json.loads(cm_json_str)

    # Get the config.yaml string
    config_str = cm["data"]["config.yaml"]

    # Check if profile already exists
    if "mixed-one-node-40gb-small" in config_str:
        print("Profile already exists in string. Exiting.")
        return

    # Define the new profile string (YAML format)
    # Ensure indentation matches (2 spaces for profile name, 4 spaces for properties)
    new_profile_str = """
  mixed-one-node-40gb-small:
    - devices: [0]
      mig-enabled: false
    - devices: [1]
      mig-enabled: true
      mig-devices:
        "1g.5gb": 7
"""

    # Append to the config string
    # We assume the file ends with a newline or we add one
    if not config_str.endswith("\n"):
        config_str += "\n"
    
    config_str += new_profile_str

    # Update the configmap data
    cm["data"]["config.yaml"] = config_str

    # Write to file
    with open("cm_patched.json", "w") as f:
        json.dump(cm, f, indent=2)

    # Apply the updated configmap
    print("Applying updated ConfigMap...")
    run_kubectl(["apply", "-f", "cm_patched.json"])
    print("Done.")

if __name__ == "__main__":
    main()
