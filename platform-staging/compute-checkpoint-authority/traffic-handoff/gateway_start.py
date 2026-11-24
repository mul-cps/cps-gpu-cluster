"""Start the staged gateway only after its current controller permits it."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import time

from cps_compute.native_group_process import (
    _api_document, _contains, _match_pod_spec, _object, _owner, _require,
    _selector, _template, validate_process_declaration,
)


PERMIT = "cps.unileoben.ac.at/gateway-start-template"


def template_digest(template):
    encoded = json.dumps(template, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def permit_start(core, apps, declaration, pod_name, pod_uid):
    expected = validate_process_declaration(declaration)
    _require(expected["kind"] == "Deployment", "A pinned gateway Deployment is required")
    namespace = expected["namespace"]
    timeout = (.35, .65)

    def current_template():
        raw = apps.read_namespaced_deployment(expected["name"], namespace, _request_timeout=timeout)
        deployment = _object(_api_document(apps, raw), "Deployment", namespace, expected["name"], expected["uid"])
        template = _template(deployment)
        _require(deployment["spec"].get("replicas") == 1
                 and deployment["metadata"].get("annotations", {}).get(PERMIT) == template_digest(template),
                 "An operator permit for the current single-replica gateway template is required")
        return deployment, template

    deployment, desired = current_template()
    containers = [row for row in desired["spec"]["containers"] if row["name"] == expected["container"]]
    _require(len(containers) == 1 and containers[0].get("image") == expected["image"]
             and desired["spec"].get("serviceAccountName") == expected["service_account"],
             "The permitted gateway image and service account must match the declaration")

    actual = core.read_namespaced_pod(pod_name, namespace, _request_timeout=timeout)
    pod = _object(_api_document(core, actual), "Pod", namespace, pod_name, pod_uid)
    owner = _owner(pod, "ReplicaSet")
    actual = apps.read_namespaced_replica_set(owner["name"], namespace, _request_timeout=timeout)
    replica = _object(_api_document(apps, actual), "ReplicaSet", namespace, owner["name"], owner["uid"])
    parent = _owner(replica, "Deployment")
    _require((parent["name"], parent["uid"]) == (expected["name"], expected["uid"])
             and replica["spec"].get("replicas") == 1, "Exactly one replica of the adopted gateway is required")
    replica_template = deepcopy(_template(replica))
    replica_template.get("metadata", {}).get("labels", {}).pop("pod-template-hash", None)
    _require(replica_template == desired, "The gateway ReplicaSet must match the permitted template")
    metadata = pod["metadata"]
    _selector(metadata.get("labels", {}), deployment["spec"]["selector"])
    _match_pod_spec(pod["spec"], desired["spec"])
    _require(all(_contains(metadata.get(field, {}), desired.get("metadata", {}).get(field, {}))
                 for field in ("labels", "annotations")), "The actual gateway Pod metadata differs")
    _require(pod["status"]["phase"] == "Running", "Gateway process must be running while parked")
    _, confirmed = current_template()
    _require(confirmed == desired, "The gateway template changed during the start check")
    return template_digest(desired)


def wait_for_start(core, apps, declaration, pod_name, pod_uid):
    from kubernetes.client.exceptions import ApiException
    from urllib3.exceptions import HTTPError

    validate_process_declaration(declaration)
    while True:
        try:
            return permit_start(core, apps, declaration, pod_name, pod_uid)
        except (ApiException, HTTPError, OSError, ValueError):
            time.sleep(.05)


def main():
    from kubernetes import client, config
    import uvicorn
    from cps_compute.runtime import create_runtime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    declaration = json.loads(Path(os.environ["CPS_NATIVE_APPROVAL_PUBLISHER_PATH"]).read_bytes())["process"]
    pod_name = os.environ["CPS_NATIVE_APPROVAL_POD_NAME"]
    pod_uid = os.environ["CPS_NATIVE_APPROVAL_POD_UID"]
    _require(declaration["namespace"] == os.environ["CPS_NATIVE_APPROVAL_POD_NAMESPACE"],
             "Gateway namespace differs from the pinned declaration")
    server = uvicorn.Server(uvicorn.Config(
        create_runtime, factory=True, workers=1, host="0.0.0.0", port=args.port,
        ssl_keyfile="/tls/tls.key", ssl_certfile="/tls/tls.crt",
    ))
    config.load_incluster_config()
    with client.ApiClient() as api:
        wait_for_start(client.CoreV1Api(api), client.AppsV1Api(api), declaration, pod_name, pod_uid)
    server.run()


if __name__ == "__main__":
    main()
