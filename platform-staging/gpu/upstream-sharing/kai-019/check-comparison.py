"""Check rendered KAI objects against the captured production API state."""
import json
from pathlib import Path
import sys

import yaml


def main(directory):
    candidate = [
        item for item in yaml.safe_load_all((directory / "candidate.yaml").read_text())
        if item
    ]
    live_admission = {
        item["metadata"]["name"]: item
        for item in json.loads((directory / "live-admission.json").read_text())["items"]
    }
    live_queues = {
        item["metadata"]["name"]: item
        for item in json.loads((directory / "live-queues.json").read_text())["items"]
    }
    changes = {"crds": {}, "queues": {}, "liveWebhooks": []}
    for item in candidate:
        name = item["metadata"]["name"]
        if item["kind"] == "CustomResourceDefinition":
            previous = live_admission[name]
            known = {version["name"] for version in item["spec"]["versions"]}
            unknown = sorted(set(previous["status"]["storedVersions"]) - known)
            changes["crds"][name] = {
                "changed": previous["spec"] != item["spec"],
                "unknownStoredVersions": unknown,
            }
        if item["kind"] == "Queue":
            changes["queues"][name] = live_queues.get(name, {}).get("spec") != item["spec"]

    changes["liveWebhooks"] = sorted(
        name for name, item in live_admission.items()
        if item["kind"].endswith("WebhookConfiguration")
    )
    print(json.dumps(changes, indent=2))
    if (
        not changes["crds"] or not changes["queues"] or not changes["liveWebhooks"]
        or any(item["unknownStoredVersions"] for item in changes["crds"].values())
        or any(changes["queues"].values())
    ):
        raise SystemExit("KAI comparison requires review before staging")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
