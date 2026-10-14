"""Owned-prefix controlled test; credentials remain in the mounted fixture Pod."""

import argparse
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import urllib.error

CONTROLLER_SHA = "9cadec1f0229222f34923b18f456a0506ae5e92826ea78ab7e791e1e72e73542"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class ScopedStorage:
    """Closed mutation/read allowlist for just this run's exact object keys."""

    METHODS = {
        "head_object",
        "get_object",
        "get_object_tagging",
        "put_object_tagging",
        "put_object",
        "delete_object",
    }

    def __init__(self, client, bucket, keys):
        self.client, self.bucket, self.keys = client, bucket, frozenset(keys)
        self.prefixes = {key.rsplit("/", 1)[0] + "/" for key in keys}
        self.deletes = []

    def check(self, kwargs):
        need(
            kwargs.get("Bucket") == self.bucket and kwargs.get("Key") in self.keys,
            "Only exact owned QA object keys may be accessed",
        )

    def __getattr__(self, name):
        need(name in self.METHODS, "Unreviewed storage operation")

        def call(**kwargs):
            self.check(kwargs)
            if name == "put_object":
                need(
                    kwargs.get("IfNoneMatch") == "*",
                    "Initial QA creation must not overwrite",
                )
            if name == "delete_object":
                need(
                    isinstance(kwargs.get("IfMatch"), str) and kwargs["IfMatch"],
                    "Only conditional owned deletion permitted",
                )
                self.deletes.append({"key": kwargs["Key"], "etag": kwargs["IfMatch"]})
            return getattr(self.client, name)(**kwargs)

        return call

    def replace_owned(self, **kwargs):
        self.check(kwargs)
        need(isinstance(kwargs.get("IfMatch"), str), "Conditional replacement required")
        return self.client.put_object(**kwargs)

    def get_paginator(self, name):
        need(name == "list_objects_v2", "Only bounded exact-prefix inventory permitted")
        return self

    def paginate(self, **kwargs):
        need(
            kwargs.get("Bucket") == self.bucket
            and kwargs.get("Prefix") in self.prefixes,
            "Only complete owned QA prefix may be scanned",
        )
        yield from self.client.get_paginator("list_objects_v2").paginate(**kwargs)


def clients():
    import boto3
    from botocore.client import Config

    raw = Path("/scripts/artifact-retention.py").read_bytes()
    need(
        hashlib.sha256(raw).hexdigest() == CONTROLLER_SHA,
        "Actual current reviewed controller bytes required",
    )
    spec = importlib.util.spec_from_file_location(
        "actual_retention", "/scripts/artifact-retention.py"
    )
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    config = json.loads(Path("/scripts/config.json").read_text())
    need(
        config["namespace"] == "cps-workflows"
        and config["endpoint"].startswith("https://")
        and config["argoUrl"].startswith("https://")
        and config["kubeUrl"].startswith("https://"),
        "Verified HTTPS required for all APIs",
    )
    client = boto3.client(
        "s3",
        endpoint_url=config["endpoint"],
        aws_access_key_id=Path(config["accessKeyFile"]).read_text().strip(),
        aws_secret_access_key=Path(config["secretKeyFile"]).read_text().strip(),
        region_name="us-east-1",
        verify=config["ca"],
        config=Config(
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 0},
            s3={"addressing_style": "path"},
        ),
    )
    need(
        "IfMatch"
        in client.meta.service_model.operation_model("DeleteObject").input_shape.members
        and "IfNoneMatch"
        in client.meta.service_model.operation_model("PutObject").input_shape.members
        and "IfMatch"
        in client.meta.service_model.operation_model("PutObject").input_shape.members,
        "Actual SDK conditional operations required",
    )
    proof = controller.ArgoProof(
        config["argoUrl"],
        config["namespace"],
        config["argoTokenFile"],
        config["argoCa"],
        kube_url=config["kubeUrl"],
        kube_ca=config["kubeCa"],
    )
    return controller, config, client, proof


def artifact(record):
    prefix, filename = (
        ("notebook-inputs", "snapshot.tar")
        if record["days"] == 14
        else ("run-artifacts", "executed.ipynb")
    )
    return prefix + "/" + record["identifier"] + "/" + filename


def keys_for(records):
    return {
        key
        for record in records
        for key in (
            artifact(record),
            "notebook-provenance/" + record["identifier"] + "/intent.json",
            "notebook-provenance/" + record["identifier"] + "/binding.json",
        )
    }


def body_hash(storage, bucket, key):
    from botocore.exceptions import ClientError

    try:
        response = storage.get_object(Bucket=bucket, Key=key)
    except ClientError as error:
        need(
            error.response["ResponseMetadata"]["HTTPStatusCode"] == 404,
            "Authenticated absence required",
        )
        return None
    try:
        raw = response["Body"].read(8193)
        need(len(raw) <= 8192, "Bounded QA payload required")
        return hashlib.sha256(raw).hexdigest()
    finally:
        response["Body"].close()


def sweep(controller, storage, bucket, proof, record, now, apply=True):
    return controller.sweep(
        storage,
        bucket,
        proof,
        prefix=artifact(record).rsplit("/", 1)[0] + "/",
        now=now,
        apply=apply,
        conditional_delete_qualified=apply,
        lifecycle_qualified=apply,
        max_examined=3,
        max_deletes=1,
    )


def recover(path):
    state = json.loads(path.read_text())
    record = state["record"]
    controller, config, client, proof = clients()
    storage = ScopedStorage(client, config["bucket"], keys_for([record]))
    report = sweep(
        controller,
        storage,
        config["bucket"],
        proof,
        record,
        datetime.fromisoformat(state["now"]) + timedelta(days=100),
    )
    current = proof.get("cps-" + record["identifier"])
    need(
        current["metadata"]["uid"] == record["workflow"]["metadata"]["uid"]
        and controller.lifecycle(current) == state["lifecycle"],
        "Recovery must preserve original UID and permanent lifecycle claims",
    )
    need(
        report["deleted"] == report["errors"] == 0 and not storage.deletes,
        "Fresh recovery may not retry permanent claims",
    )
    need(
        body_hash(storage, config["bucket"], artifact(record)) == state["body_hash"],
        "Recovery may not alter retained or ambiguous owned data",
    )
    print(
        canonical(
            {
                "recovery_passed": True,
                "sweep": report,
                "body_hash": state["body_hash"],
                "new_process": True,
            }
        )
    )


def execute():
    controller, config, client, proof = clients()
    records = json.loads(Path("/qa/records.json").read_text())["cases"]
    need(
        len(records) == 10 and len({r["identifier"] for r in records}) == 10,
        "Closed ten-case owned inventory required",
    )
    storage = ScopedStorage(client, config["bucket"], keys_for(records))
    # The QA identity is restricted by resourceNames, independently of the Python key fence.
    try:
        proof.kube_request("cps-unowned-00000000-0000-4000-8000-000000000000")
    except urllib.error.HTTPError as error:
        need(error.code == 403, "QA service account must deny unrelated workflows")
    else:
        raise ValueError("Unexpected access to an unrelated workflow")
    report = {
        "version": 1,
        "passed": False,
        "productionQualified": False,
        "controllerSha256": CONTROLLER_SHA,
        "leastPrivilegeUnownedWorkflowDenied": True,
        "scope": "Real SeaweedFS, Argo HTTPS and Kubernetes CAS; controlled synthetic terminal status and per-sweep clocks; no notebook execution",
        "cases": [],
    }
    out = Path("/tmp/retention-report.json")
    out.write_text(canonical(report))
    for record in records:
        identity = record["identifier"]
        workflow = proof.get("cps-" + identity)
        need(
            workflow["metadata"]["uid"] == record["workflow"]["metadata"]["uid"]
            and workflow["spec"]["suspend"] is True
            and workflow["status"]["phase"] == "Succeeded",
            "Exact controlled terminal workflow required",
        )
        key = artifact(record)
        category = "snapshot" if record["days"] == 14 else "executed-notebook"
        body = ("controlled-artifact-" + record["case"] + "-" + identity).encode()
        snapshot_hash = hashlib.sha256(body).hexdigest()
        for prefix in (
            key.rsplit("/", 1)[0] + "/",
            "notebook-provenance/" + identity + "/",
        ):
            pages = storage.paginate(
                Bucket=config["bucket"],
                Prefix=prefix,
                PaginationConfig={"PageSize": 4, "MaxItems": 4},
            )
            need(
                not any(page.get("Contents") for page in pages),
                "Selected QA prefix already contains data; refuse mutation",
            )
        intent = {
            "version": 1,
            "notebook_id": identity,
            "policy_hash": workflow["metadata"]["annotations"][
                "compute.cps.unileoben.ac.at/policy-hash"
            ],
            "owner": workflow["metadata"]["labels"][
                "compute.cps.unileoben.ac.at/owner"
            ],
            "submission_hash": workflow["metadata"]["annotations"][
                "cps.compute/submission-hash"
            ],
            "snapshot_hash": snapshot_hash,
        }
        binding = {
            "version": 1,
            "notebook_id": identity,
            "namespace": "cps-workflows",
            "name": workflow["metadata"]["name"],
            "uid": workflow["metadata"]["uid"],
            "intent_hash": hashlib.sha256(canonical(intent).encode()).hexdigest(),
        }
        for kind, value in (("intent", intent), ("binding", binding)):
            storage.put_object(
                Bucket=config["bucket"],
                Key="notebook-provenance/" + identity + "/" + kind + ".json",
                Body=canonical(value).encode(),
                IfNoneMatch="*",
            )
        tag = "temporary-expirable" if record["days"] == 14 else "run-expirable"
        tags = (
            "retention="
            + tag
            + "&active="
            + ("true" if record["case"] == "active" else "false")
            + "&retained="
            + ("true" if record["case"] == "retained-tag" else "false")
        )
        storage.put_object(
            Bucket=config["bucket"],
            Key=key,
            Body=body,
            Metadata=controller.expected_metadata(workflow, key),
            Tagging=tags,
            IfNoneMatch="*",
        )
        head = storage.head_object(Bucket=config["bucket"], Key=key)
        finished = datetime.fromisoformat(
            workflow["status"]["finishedAt"].replace("Z", "+00:00")
        )
        boundary = max(head["LastModified"], finished) + timedelta(days=record["days"])
        early = sweep(
            controller,
            storage,
            config["bucket"],
            proof,
            record,
            boundary - timedelta(seconds=1),
            apply=False,
        )
        need(
            early["eligible"] == early["deleted"] == early["errors"] == 0,
            "Nothing may qualify before its actual two-age boundary",
        )
        now = boundary if record["case"] == "boundary" else boundary + timedelta(days=1)

        fault_outcome = {}

        class Fault:
            def __getattr__(self, name):
                return getattr(storage, name)

            def delete_object(self, **kwargs):
                if record["case"] == "ambiguous-before":
                    raise TimeoutError("Controlled lost response before send")
                if record["case"] == "etag-conflict":
                    need(
                        kwargs["IfMatch"] == head["ETag"],
                        "Actual observed original ETag required",
                    )
                    storage.replace_owned(
                        Bucket=config["bucket"],
                        Key=key,
                        Body=body + b"-changed",
                        Metadata=head["Metadata"],
                        Tagging=tags,
                        IfMatch=head["ETag"],
                    )
                try:
                    response = storage.delete_object(**kwargs)
                except Exception as error:
                    fault_outcome["deleteHTTPStatus"] = (
                        getattr(error, "response", {})
                        .get("ResponseMetadata", {})
                        .get("HTTPStatusCode")
                    )
                    raise
                if record["case"] == "ambiguous-after":
                    raise TimeoutError(
                        "Controlled loss after actual conditional delete"
                    )
                return response

        result = sweep(controller, Fault(), config["bucket"], proof, record, now)
        present_hash = body_hash(storage, config["bucket"], key)
        after = proof.get(workflow["metadata"]["name"])
        claim = controller.lifecycle(after)["artifacts"].get(category)
        if record["case"] == "boundary":
            need(
                result["eligible"] == result["deleted"] == 1
                and result["errors"] == 0
                and present_hash is None
                and claim["state"] == "deleting"
                and claim["etag"] == head["ETag"],
                "Actual exact-age conditional deletion required",
            )
        elif record["case"] in ("active", "retained-tag", "retained-claim"):
            need(
                result["deleted"] == result["errors"] == 0
                and present_hash == snapshot_hash
                and (claim is None or claim["state"] == "retained"),
                "Active and retained data must survive",
            )
        else:
            need(
                result["deleted"] == 0
                and result["errors"] == 1
                and claim["state"] == "deleting"
                and claim["etag"] == head["ETag"],
                "Ambiguity/conflict must retain its permanent original claim",
            )
            expected_hash = (
                None
                if record["case"] == "ambiguous-after"
                else hashlib.sha256(
                    body + (b"-changed" if record["case"] == "etag-conflict" else b"")
                ).hexdigest()
            )
            need(
                present_hash == expected_hash,
                "Actual server outcome differs from controlled ambiguity",
            )
            if record["case"] == "etag-conflict":
                need(
                    fault_outcome.get("deleteHTTPStatus") == 412,
                    "Actual SeaweedFS stale-ETag precondition rejection required",
                )
        recovery = Path("/tmp/recovery-" + identity + ".json")
        recovery.write_text(
            canonical(
                {
                    "record": record,
                    "now": now.isoformat(),
                    "body_hash": present_hash,
                    "lifecycle": controller.lifecycle(after),
                }
            )
        )
        recovered = subprocess.run(
            [sys.executable, __file__, "--recover", str(recovery)],
            capture_output=True,
            timeout=30,
        )
        need(recovered.returncode == 0, "Fresh-process recovery failed")
        recovery_report = json.loads(recovered.stdout)
        report["cases"].append(
            {
                "case": record["case"],
                "days": record["days"],
                "key": key,
                "workflowUid": workflow["metadata"]["uid"],
                "owner": intent["owner"],
                "objectLastModified": head["LastModified"].isoformat(),
                "actualFinishedAt": workflow["status"]["finishedAt"],
                "testNow": now.isoformat(),
                "beforeBoundary": early,
                "sweep": result,
                "originalEtag": head["ETag"],
                "presentBodySha256": present_hash,
                "lifecycle": controller.lifecycle(after),
                "freshProcessRecovery": recovery_report,
                "faultOutcome": fault_outcome,
            }
        )
        out.write_text(canonical(report))
    report["passed"] = True
    out.write_text(canonical(report))
    print(canonical({"passed": True, "cases": 10, "productionQualified": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recover", type=Path)
    args = parser.parse_args()
    if args.recover:
        recover(args.recover)
    elif args.execute:
        execute()
    else:
        print(
            canonical(
                {"state": "inert", "api_calls": False, "productionQualified": False}
            )
        )
