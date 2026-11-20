"""Prepare and run one isolated, bounded retention QA fixture; no production updates."""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

HERE = Path(__file__).parent
CONTROLLER_SHA = "9cadec1f0229222f34923b18f456a0506ae5e92826ea78ab7e791e1e72e73542"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, text):
    if not ok:
        raise ValueError(text)


def kubectl(argv, body=None, *, check=True, timeout=30):
    result = subprocess.run(
        ["kubectl", "--context", "local", "--request-timeout=15s", *argv],
        input=canonical(body).encode() if body is not None else None,
        capture_output=True,
        timeout=timeout,
    )
    if check:
        need(
            result.returncode == 0,
            "Scoped Kubernetes request failed: " + " ".join(argv[:3]),
        )
    return result


def get(kind, name, namespace):
    return json.loads(
        kubectl(["get", kind, name, "-n", namespace, "-o", "json"]).stdout
    )


def case_inventory():
    cases = [
        ("boundary", 14),
        ("boundary", 90),
        ("active", 14),
        ("active", 90),
        ("retained-tag", 14),
        ("retained-tag", 90),
        ("retained-claim", 90),
        ("etag-conflict", 14),
        ("ambiguous-before", 14),
        ("ambiguous-after", 90),
    ]
    return [
        {"case": name, "days": days, "identifier": str(uuid.uuid4())}
        for name, days in cases
    ]


def authorization(name, workflows):
    def meta(namespace):
        return {"name": name, "namespace": namespace}

    return [
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": meta("cps-compute"),
            "automountServiceAccountToken": False,
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": meta("cps-workflows"),
            "rules": [
                {
                    "apiGroups": ["argoproj.io"],
                    "resources": ["workflows"],
                    "resourceNames": workflows,
                    "verbs": ["get", "patch"],
                }
            ],
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": meta("cps-workflows"),
            "subjects": [
                {"kind": "ServiceAccount", "name": name, "namespace": "cps-compute"}
            ],
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "Role",
                "name": name,
            },
        },
    ]


def private_write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def capture():
    cron = get("cronjob", "cps-artifact-retention", "cps-compute")
    cm = get("configmap", "cps-artifact-retention", "cps-compute")
    need(cron["spec"]["suspend"] is True, "Production retention must remain suspended")
    need(
        sha(cm["data"]["artifact-retention.py"].encode()) == CONTROLLER_SHA,
        "Actual deployed retention controller differs",
    )
    config = json.loads(cm["data"]["config.json"])
    pod = cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    need(
        pod["automountServiceAccountToken"] is False
        and pod["serviceAccountName"] == "cps-artifact-retention"
        and len(pod["containers"]) == 1
        and pod["containers"][0]["image"] == config["image"],
        "Actual dedicated current template/image required",
    )
    need(
        config["conditionalDeleteQualified"] is False
        and config["lifecycleQualified"] is False
        and config["reconcileMetadata"] is False,
        "Production qualification settings unexpectedly changed",
    )
    return cron, cm, config


def prepare(directory):
    need(
        directory.is_absolute() and not directory.exists(),
        "Fresh private qualification output directory required",
    )
    directory.mkdir(mode=0o700)
    cron, cm, config = capture()
    plan = {
        "version": 1,
        "name": "cps-retention-qa-" + uuid.uuid4().hex[:10],
        "cases": case_inventory(),
        "cronUid": cron["metadata"]["uid"],
        "cronSpecSha256": sha(canonical(cron["spec"]).encode()),
        "configmapUid": cm["metadata"]["uid"],
        "configSha256": sha(cm["data"]["config.json"].encode()),
        "controllerSha256": CONTROLLER_SHA,
        "fixtureSha256": sha((HERE / "fixture.py").read_bytes()),
        "runnerSha256": sha(Path(__file__).read_bytes()),
        "image": config["image"],
        "policyHash": config["policyHash"],
        "productionQualified": False,
        "syntheticTerminalStatus": True,
        "globalClockMutation": False,
        "namespace": "cps-compute",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    # Dry-run all owned workflow records before the caller can execute.
    for record in plan["cases"]:
        kubectl(["create", "--dry-run=server", "-f", "-"], workflow(plan, record))
    private_write(directory / "plan.json", canonical(plan).encode())
    print(
        canonical(
            {
                "state": "prepared-no-mutations",
                "plan": str(directory / "plan.json"),
                "planSha256": sha(canonical(plan).encode()),
                "workflows": 10,
                "image": config["image"],
            }
        )
    )


def workflow(plan, record):
    annotations = {
        "cps.compute/notebook-id": record["identifier"],
        "cps.compute/submission-hash": sha(canonical(record).encode()),
        "compute.cps.unileoben.ac.at/policy-hash": plan["policyHash"],
        "cps.compute/artifact-lifecycle": canonical({"version": 1, "artifacts": {}}),
    }
    if record["case"] == "retained-claim":
        annotations["cps.compute/artifact-lifecycle"] = canonical(
            {
                "version": 1,
                "artifacts": {
                    "executed-notebook": {
                        "state": "retained",
                        "actor": plan["name"],
                        "at": plan["createdAt"],
                    }
                },
            }
        )
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": "cps-" + record["identifier"],
            "namespace": "cps-workflows",
            "labels": {
                "workflows.argoproj.io/completed": "true",
                "qualification.cps/owner": plan["name"],
                "compute.cps.unileoben.ac.at/owner": sha(plan["name"].encode())[:63],
            },
            "annotations": annotations,
        },
        "spec": {
            "suspend": True,
            "entrypoint": "idle",
            "templates": [{"name": "idle", "suspend": {}}],
        },
    }


def execute(path, reviewed_sha):
    raw = path.read_bytes()
    need(sha(raw) == reviewed_sha, "Exact reviewed owned QA plan required")
    plan = json.loads(raw)
    directory = path.parent
    need(
        sha(Path(__file__).read_bytes()) == plan["runnerSha256"]
        and sha((HERE / "fixture.py").read_bytes()) == plan["fixtureSha256"],
        "QA source bytes changed after review",
    )
    cron, cm, config = capture()
    need(
        cron["metadata"]["uid"] == plan["cronUid"]
        and sha(canonical(cron["spec"]).encode()) == plan["cronSpecSha256"]
        and cm["metadata"]["uid"] == plan["configmapUid"]
        and sha(cm["data"]["config.json"].encode()) == plan["configSha256"],
        "Actual suspended configuration drifted",
    )
    owned = []
    records = []
    report = {
        "version": 1,
        "passed": False,
        "productionQualified": False,
        "planSha256": reviewed_sha,
        "plan": plan,
        "cleanup": [],
        "automaticCleanupActivated": False,
    }

    def record_report():
        target = directory / "report.json"
        target.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        os.chmod(target, 0o600)

    def create(obj):
        made = json.loads(kubectl(["create", "-f", "-", "-o", "json"], obj).stdout)
        owned.append(
            {
                "kind": made["kind"],
                "name": made["metadata"]["name"],
                "namespace": made["metadata"]["namespace"],
                "uid": made["metadata"]["uid"],
            }
        )
        report["ownedResources"] = owned.copy()
        record_report()
        return made

    try:
        for resource in authorization(
            plan["name"], ["cps-" + r["identifier"] for r in plan["cases"]]
        ):
            create(resource)
        for case in plan["cases"]:
            made = create(workflow(plan, case))
            now = datetime.now(timezone.utc).isoformat()
            kubectl(
                [
                    "patch",
                    "workflow",
                    made["metadata"]["name"],
                    "-n",
                    "cps-workflows",
                    "--type=merge",
                    "-p",
                    canonical(
                        {
                            "status": {
                                "phase": "Succeeded",
                                "startedAt": now,
                                "finishedAt": now,
                                "message": "Owned controlled synthetic terminal retention fixture; no execution templates",
                            }
                        }
                    ),
                ]
            )
            records.append(
                {
                    **case,
                    "workflow": get(
                        "workflow", made["metadata"]["name"], "cps-workflows"
                    ),
                }
            )
        create(
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": plan["name"], "namespace": "cps-compute"},
                "data": {
                    "fixture.py": (HERE / "fixture.py").read_text(),
                    "records.json": canonical({"cases": records}),
                },
            }
        )
        spec = copy.deepcopy(cron["spec"]["jobTemplate"]["spec"]["template"]["spec"])
        spec.update(
            serviceAccountName=plan["name"],
            restartPolicy="Never",
            activeDeadlineSeconds=300,
        )
        c = spec["containers"][0]
        c["command"] = ["python", "-c", "import time;time.sleep(300)"]
        c.pop("args", None)
        spec["volumes"].extend(
            [
                {"name": "qa", "configMap": {"name": plan["name"]}},
                {"name": "scratch", "emptyDir": {"sizeLimit": "4Mi"}},
            ]
        )
        c["volumeMounts"].extend(
            [
                {"name": "qa", "mountPath": "/qa", "readOnly": True},
                {"name": "scratch", "mountPath": "/tmp"},
            ]
        )
        pod = create(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": plan["name"],
                    "namespace": "cps-compute",
                    "labels": {
                        "app": "cps-artifact-retention",
                        "qualification.cps/owner": plan["name"],
                    },
                },
                "spec": spec,
            }
        )
        report["podUid"] = pod["metadata"]["uid"]
        record_report()
        kubectl(
            [
                "wait",
                "--for=condition=Ready",
                "pod/" + plan["name"],
                "-n",
                "cps-compute",
                "--timeout=100s",
            ],
            timeout=110,
        )
        observed = get("pod", plan["name"], "cps-compute")
        statuses = observed["status"]["containerStatuses"]
        need(
            observed["metadata"]["uid"] == pod["metadata"]["uid"]
            and len(statuses) == 1
            and statuses[0]["ready"] is True
            and statuses[0]["restartCount"] == 0
            and statuses[0]["imageID"].endswith(plan["image"].split("@", 1)[1]),
            "Actual immutable image/Pod lifetime readback required",
        )
        result = kubectl(
            [
                "exec",
                "-n",
                "cps-compute",
                plan["name"],
                "--",
                "python",
                "/qa/fixture.py",
                "--execute",
            ],
            check=False,
            timeout=180,
        )
        private_write(directory / "execution.stdout", result.stdout)
        private_write(directory / "execution.stderr", result.stderr)
        saved = kubectl(
            [
                "exec",
                "-n",
                "cps-compute",
                plan["name"],
                "--",
                "cat",
                "/tmp/retention-report.json",
            ],
            check=False,
        )
        if saved.returncode == 0:
            report["fixture"] = json.loads(saved.stdout)
        need(
            result.returncode == 0 and report.get("fixture", {}).get("passed") is True,
            "Controlled retention fixture failed; inspect private logs",
        )
        for case in records:
            pods = json.loads(
                kubectl(
                    [
                        "get",
                        "pods",
                        "-n",
                        "cps-workflows",
                        "-l",
                        "workflows.argoproj.io/workflow="
                        + case["workflow"]["metadata"]["name"],
                        "-o",
                        "json",
                    ]
                ).stdout
            )
            need(
                not pods["items"],
                "Controlled fixture unexpectedly created execution Pods",
            )
        report.update(
            passed=True,
            actualImageId=statuses[0]["imageID"],
            executionPodsCreated=0,
            survivingOwnedS3EvidencePreserved=True,
        )
    finally:
        types = {
            "Pod": ("/api/v1", "pods"),
            "ConfigMap": ("/api/v1", "configmaps"),
            "ServiceAccount": ("/api/v1", "serviceaccounts"),
            "Role": ("/apis/rbac.authorization.k8s.io/v1", "roles"),
            "RoleBinding": ("/apis/rbac.authorization.k8s.io/v1", "rolebindings"),
            "Workflow": ("/apis/argoproj.io/v1alpha1", "workflows"),
        }
        for item in reversed(owned):
            prefix, plural = types[item["kind"]]
            api = (
                prefix
                + "/namespaces/"
                + item["namespace"]
                + "/"
                + plural
                + "/"
                + item["name"]
            )
            result = kubectl(
                ["delete", "--raw", api, "-f", "-"],
                {
                    "apiVersion": "v1",
                    "kind": "DeleteOptions",
                    "preconditions": {"uid": item["uid"]},
                },
                check=False,
            )
            if item["kind"] == "Pod":
                kubectl(
                    [
                        "wait",
                        "--for=delete",
                        "pod/" + item["name"],
                        "-n",
                        item["namespace"],
                        "--timeout=40s",
                    ],
                    check=False,
                    timeout=50,
                )
            remaining = kubectl(
                ["get", plural, item["name"], "-n", item["namespace"]], check=False
            )
            report["cleanup"].append(
                {
                    **item,
                    "deleteAccepted": result.returncode == 0,
                    "removed": b"NotFound" in remaining.stderr,
                }
            )
        fresh, _, _ = capture()
        report["productionCronSpecUnchanged"] = (
            fresh["metadata"]["uid"] == plan["cronUid"]
            and sha(canonical(fresh["spec"]).encode()) == plan["cronSpecSha256"]
        )
        record_report()
    need(
        all(r["removed"] for r in report["cleanup"])
        and report["productionCronSpecUnchanged"],
        "Complete owned cleanup and unchanged suspended Cron required",
    )
    print(
        canonical(
            {
                "passed": report["passed"],
                "cases": 10,
                "resourcesRemoved": len(report["cleanup"]),
                "reportSha256": sha((directory / "report.json").read_bytes()),
                "productionQualified": False,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--execute", type=Path)
    parser.add_argument("--reviewed-plan-sha256")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.prepare)
    elif args.execute:
        execute(args.execute, args.reviewed_plan_sha256)
    else:
        print(
            canonical(
                {"state": "inert", "api_calls": False, "productionQualified": False}
            )
        )
