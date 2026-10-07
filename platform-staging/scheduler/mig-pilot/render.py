#!/usr/bin/env python3
"""Render an inert review ConfigMap from explicit offline inventory; never apply."""
import argparse
import datetime as dt
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys


PILOT_NODE = "k3s-wk-gpu2"
MODE_LABEL = "compute.cps.unileoben.ac.at/gpu-mode"
GEOMETRY = {"3g.20gb": 1, "2g.10gb": 1, "1g.5gb": 2}
PROTECTED = {"nodeName": "k3s-wk-gpu1", "name": "jupyter-bjoern",
             "uid": "a663ab6b-e927-418f-9671-fc0b36a27b3a", "untouched": True}
UUID_PATTERN = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
ACTIVATION_FIELDS = {"enabled", "fleet", "modeChanges", "workloadSubmission", "productionCatalog"}


def require(condition, field, reason):
    if not condition:
        raise ValueError(f"{field}: {reason}")


def object_keys(value, expected, field):
    require(isinstance(value, dict) and set(value) == set(expected), field,
            "only the explicitly reviewed fields are permitted")


def valid_uuid(value, prefix=""):
    return isinstance(value, str) and re.fullmatch(prefix + UUID_PATTERN, value) is not None


def validate(config, preflight, now):
    object_keys(config, {"schemaVersion", "status", "activation", "target", "geometry",
                         "plannedNodeLabels", "exclusiveJobSelectors"}, "config")
    require(type(config["schemaVersion"]) is int and config["schemaVersion"] == 1,
            "schemaVersion", "unsupported config version")
    require(config["status"] == "disabled-unqualified", "status", "pilot must remain disabled")
    object_keys(config["activation"], ACTIVATION_FIELDS, "activation")
    require(all(value is False for value in config["activation"].values()), "activation",
            "this renderer supports review artifacts only; every switch must be false")
    target = config["target"]
    object_keys(target, {"nodeName", "nodeUID", "gpuUUID", "gpuIndex"}, "target")
    require(target["nodeName"] == PILOT_NODE, "nodeName", "only GPU2 is in reviewed scope; GPU1 is protected")
    require(valid_uuid(target["nodeUID"]), "nodeUID", "explicit observed node UUID required")
    require(valid_uuid(target["gpuUUID"], "GPU-"), "gpuUUID", "one explicit physical GPU UUID required")
    require(type(target["gpuIndex"]) is int and target["gpuIndex"] >= 0, "gpuIndex",
            "one integer inventory index required; lists/all/selectors are forbidden")
    require(config["geometry"] == GEOMETRY and all(type(n) is int for n in config["geometry"].values()),
            "geometry", "only reviewed A100 40GB 3-2-1-1 geometry is permitted")
    require(config["plannedNodeLabels"] == {MODE_LABEL: "mig-pilot"}, "plannedNodeLabels",
            "reviewed pilot pool must be distinct from the full-gpu pool")
    selectors = config["exclusiveJobSelectors"]
    require(isinstance(selectors, list) and bool(selectors), "exclusiveJobSelectors",
            "complete explicit whole-GPU template inventory required")
    names = set()
    for entry in selectors:
        object_keys(entry, {"name", "nodeSelector"}, "exclusiveJobSelectors")
        require(isinstance(entry["name"], str) and entry["name"].strip()
                and not entry["name"].startswith("REVIEW-") and entry["name"] not in names,
                "exclusiveJobSelectors", "each observed template needs a unique real name")
        names.add(entry["name"])
        selector = entry["nodeSelector"]
        require(isinstance(selector, dict) and selector.get(MODE_LABEL) == "full-gpu"
                and all(isinstance(k, str) and isinstance(v, str) for k, v in selector.items()),
                "exclusiveJobSelectors", "whole-GPU jobs must require the disjoint full-gpu pool")

    object_keys(preflight, {"schemaVersion", "capturedAt", "nodeName", "nodeUID", "inventoryComplete",
                            "cards", "activeGpuWorkloads", "activeGpuProcesses", "protectedWorkload",
                            "exclusiveSelectorInventoryComplete"}, "preflight")
    require(type(preflight["schemaVersion"]) is int and preflight["schemaVersion"] == 1,
            "schemaVersion", "unsupported preflight version")
    require(preflight["nodeName"] == target["nodeName"] and preflight["nodeUID"] == target["nodeUID"],
            "nodeUID", "preflight node identity must match the target")
    try:
        captured = dt.datetime.fromisoformat(preflight["capturedAt"].replace("Z", "+00:00"))
        age = (now - captured).total_seconds()
    except (AttributeError, TypeError, ValueError):
        raise ValueError("capturedAt: timezone-aware fresh UTC snapshot required") from None
    require(captured.utcoffset() == dt.timedelta(0) and 0 <= age <= 900, "capturedAt",
            "UTC preflight must be at most 15 minutes old and not in the future")
    require(preflight["inventoryComplete"] is True, "inventoryComplete", "complete node card inventory required")
    require(preflight["exclusiveSelectorInventoryComplete"] is True, "exclusiveSelectorInventoryComplete",
            "all full-GPU workload templates must be reviewed")
    for field in ("activeGpuWorkloads", "activeGpuProcesses"):
        require(preflight[field] == [], field, "whole pilot node must be idle; no automatic eviction permitted")
    require(preflight["protectedWorkload"] == PROTECTED
            and preflight["protectedWorkload"].get("untouched") is True, "protectedWorkload",
            "the exact protected GPU1 session must be recorded untouched")
    cards = preflight["cards"]
    require(isinstance(cards, list) and bool(cards), "cards", "explicit card inventory required")
    indexes, uuids = set(), set()
    for card in cards:
        object_keys(card, {"gpuIndex", "uuid", "productName", "migMode"}, "cards")
        require(type(card["gpuIndex"]) is int and card["gpuIndex"] >= 0 and valid_uuid(card["uuid"], "GPU-"),
                "cards", "every inventory card needs a physical UUID and integer index")
        require(card["gpuIndex"] not in indexes and card["uuid"] not in uuids,
                "cards", "duplicate UUID or index makes targeting ambiguous")
        indexes.add(card["gpuIndex"])
        uuids.add(card["uuid"])
    selected = [card for card in cards if card["uuid"] == target["gpuUUID"]]
    require(len(selected) == 1, "gpuUUID", "target UUID must be present exactly once in inventory")
    card = selected[0]
    require(card["gpuIndex"] == target["gpuIndex"], "gpuIndex", "UUID/index association differs from inventory")
    require(card["productName"] in {"NVIDIA A100-PCIE-40GB", "NVIDIA A100-SXM4-40GB",
                                    "A100-PCIE-40GB", "A100-SXM4-40GB"},
            "productName", "this geometry is reviewed only for an A100 40GB card")
    require(card["migMode"] == "Disabled", "migMode", "existing MIG geometry requires a separate review")


def render(config, preflight, now=None):
    validate(config, preflight, now or dt.datetime.now(dt.timezone.utc))
    target = config["target"]
    candidate = {"version": "v1", "mig-configs": {"cps-gpu2-one-card-review": [
        {"devices": [target["gpuIndex"]], "mig-enabled": True, "mig-devices": GEOMETRY}]}}
    rollback = {"version": "v1", "mig-configs": {"cps-gpu2-one-card-disabled-review": [
        {"devices": [target["gpuIndex"]], "mig-enabled": False}]}}
    fractions = {"3g.20gb": {"count": 1, "sm": "3/7", "memory": "1/2"},
                 "2g.10gb": {"count": 1, "sm": "2/7", "memory": "1/4"},
                 "1g.5gb": {"count": 2, "sm": "1/7", "memory": "1/8"}}
    report = {"status": config["status"], "activation": config["activation"], "target": target,
              "preflightCapturedAt": preflight["capturedAt"],
              "preflightSha256": hashlib.sha256(json.dumps(preflight, sort_keys=True).encode()).hexdigest(),
              "protectedWorkload": PROTECTED,
              "qualification": {"hardwareIsolation": False, "usableMemory": False, "kaiPlacement": False,
                                "kaiPhysicalFractionAccounting": False, "fairness": False,
                                "gangScheduling": False, "exclusiveBatchCompatibility": False,
                                "activationAuthorized": False},
              "physicalFractions": {"instances": fractions,
                  "totalSm": str(sum(Fraction(v["sm"]) * v["count"] for v in fractions.values())),
                  "totalMemory": str(sum(Fraction(v["memory"]) * v["count"] for v in fractions.values()))},
              "plannedNodeLabels": config["plannedNodeLabels"],
              "exclusiveJobSelectors": config["exclusiveJobSelectors"],
              "limitations": ["Operator-declared offline inventory is not live validation or activation permission",
                              "Profile names are nominal GB, not guaranteed 5/10/20 GiB usable quotas",
                              "Index selectors require immediate UUID/index revalidation before any manual use",
                              "MIG Manager can stop node GPU clients beyond the selected card",
                              "KAI MIG resource recognition does not qualify policy accounting, placement or fairness"]}
    # JSON is a YAML subset. The nonstandard candidate key intentionally is NOT
    # GPU Operator's required config.yaml; this ConfigMap is not wired to a consumer.
    dump = lambda value: json.dumps(value, indent=2) + "\n"
    return {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {
        "name": "cps-mig-pilot-offline-review", "namespace": "cps-compute-qualification",
        "annotations": {"compute.cps.unileoben.ac.at/enabled": "false",
                        "compute.cps.unileoben.ac.at/status": "disabled-unqualified",
                        "compute.cps.unileoben.ac.at/target-node": target["nodeName"],
                        "compute.cps.unileoben.ac.at/target-node-uid": target["nodeUID"],
                        "compute.cps.unileoben.ac.at/target-gpu-uuid": target["gpuUUID"]}},
        "data": {"mig-parted-candidate.yaml": dump(candidate),
                 "mig-parted-rollback-candidate.yaml": dump(rollback),
                 "device-plugin-candidate.yaml": dump({"version": "v1", "flags": {
                     "migStrategy": "mixed", "failOnInitError": True,
                     "plugin": {"deviceIDStrategy": "uuid"}}}),
                 "review.json": dump(report)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("pilot.json"))
    parser.add_argument("--preflight", type=Path, required=True, help="fresh operator-created offline JSON")
    args = parser.parse_args()
    try:
        result = render(json.loads(args.config.read_text()), json.loads(args.preflight.read_text()))
    except (OSError, ValueError, TypeError) as error:
        print(f"MIG pilot render refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
