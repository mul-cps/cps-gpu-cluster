import subprocess
import yaml
import sys

def run_kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"kubectl command failed: {result.stderr}")
    return result.stdout

def main():
    # Get current configmap
    print("Fetching ConfigMap...")
    cm_yaml = run_kubectl(["get", "configmap", "-n", "gpu-operator", "default-mig-parted-config", "-o", "yaml"])
    cm = yaml.safe_load(cm_yaml)

    # Parse the config.yaml string
    config_str = cm["data"]["config.yaml"]
    config = yaml.safe_load(config_str)

    # Define the new profile
    new_profile = {
        "mixed-one-node-40gb-small": [
            {
                "devices": [0],
                "mig-enabled": False
            },
            {
                "devices": [1],
                "mig-enabled": True,
                "mig-devices": {
                    "1g.5gb": 7
                }
            }
        ]
    }

    # Add the profile if it doesn't exist
    if "mig-configs" not in config:
        config["mig-configs"] = {}
    
    if "mixed-one-node-40gb-small" in config["mig-configs"]:
        print("Profile already exists. Exiting.")
        return

    print("Adding new profile...")
    config["mig-configs"].update(new_profile)

    # Update the configmap data
    cm["data"]["config.yaml"] = yaml.dump(config)

    # Write to file
    with open("updated_cm.yaml", "w") as f:
        yaml.dump(cm, f)

    # Apply the updated configmap
    print("Applying updated ConfigMap...")
    run_kubectl(["apply", "-f", "updated_cm.yaml"])
    print("Done.")

if __name__ == "__main__":
    main()
