"""Offline contract tests: dangerous scope changes must fail before output."""
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
NODE_UID = "22222222-2222-4222-8222-222222222222"
GPU_UUID = "GPU-33333333-3333-4333-8333-333333333333"
PROTECTED_UID = "a663ab6b-e927-418f-9671-fc0b36a27b3a"


def fixtures():
    config = {
        "schemaVersion": 1,
        "status": "disabled-unqualified",
        "activation": {"enabled": False, "fleet": False, "modeChanges": False,
                       "workloadSubmission": False, "productionCatalog": False},
        "target": {"nodeName": "k3s-wk-gpu2", "nodeUID": NODE_UID,
                   "gpuUUID": GPU_UUID, "gpuIndex": 1},
        "geometry": {"3g.20gb": 1, "2g.10gb": 1, "1g.5gb": 2},
        "plannedNodeLabels": {"compute.cps.unileoben.ac.at/gpu-mode": "mig-pilot"},
        "exclusiveJobSelectors": [
            {"name": "whole-gpu-batch", "nodeSelector": {
                "compute.cps.unileoben.ac.at/gpu-mode": "full-gpu"}}],
    }
    preflight = {
        "schemaVersion": 1,
        "capturedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "nodeName": "k3s-wk-gpu2", "nodeUID": NODE_UID,
        "inventoryComplete": True,
        "cards": [{"gpuIndex": 0, "uuid": "GPU-44444444-4444-4444-8444-444444444444",
                   "productName": "NVIDIA A100-PCIE-40GB", "migMode": "Disabled"},
                  {"gpuIndex": 1, "uuid": GPU_UUID,
                   "productName": "NVIDIA A100-PCIE-40GB", "migMode": "Disabled"}],
        "activeGpuWorkloads": [], "activeGpuProcesses": [],
        "protectedWorkload": {"nodeName": "k3s-wk-gpu1", "name": "jupyter-bjoern",
                              "uid": PROTECTED_UID, "untouched": True},
        "exclusiveSelectorInventoryComplete": True,
    }
    return config, preflight


class RenderTests(unittest.TestCase):
    def run_renderer(self, config=None, preflight=None):
        base_config, base_preflight = fixtures()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "config.json").write_text(json.dumps(config if config is not None else base_config))
            (directory / "preflight.json").write_text(json.dumps(preflight if preflight is not None else base_preflight))
            return subprocess.run(["python3", str(ROOT / "render.py"), "--config",
                                   str(directory / "config.json"), "--preflight",
                                   str(directory / "preflight.json")], text=True, capture_output=True)

    def assert_rejected(self, config=None, preflight=None, field=None):
        result = self.run_renderer(config, preflight)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        if field:
            self.assertIn(field, result.stderr)

    def test_review_manifest_is_inert_and_targets_one_observed_card(self):
        # A renderer emitting a controller, activating label, or another index fails.
        result = self.run_renderer()
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["kind"], "ConfigMap")
        self.assertNotIn("nvidia.com/mig.config", document["metadata"].get("labels", {}))
        self.assertNotIn("spec", document)
        self.assertEqual(document["metadata"]["annotations"]["compute.cps.unileoben.ac.at/enabled"], "false")
        partition = json.loads(document["data"]["mig-parted-candidate.yaml"])
        self.assertEqual(list(partition["mig-configs"]), ["cps-gpu2-one-card-review"])
        self.assertEqual(partition["mig-configs"]["cps-gpu2-one-card-review"], [
            {"devices": [1], "mig-enabled": True,
             "mig-devices": {"3g.20gb": 1, "2g.10gb": 1, "1g.5gb": 2}}])
        rollback = json.loads(document["data"]["mig-parted-rollback-candidate.yaml"])
        self.assertEqual(rollback["mig-configs"], {"cps-gpu2-one-card-disabled-review": [
            {"devices": [1], "mig-enabled": False}]})
        plugin = json.loads(document["data"]["device-plugin-candidate.yaml"])
        self.assertEqual(plugin["flags"]["migStrategy"], "mixed")
        self.assertNotIn("sharing", plugin)
        report = json.loads(document["data"]["review.json"])
        self.assertFalse(any(report["activation"].values()))
        self.assertFalse(any(report["qualification"].values()))
        self.assertEqual(report["target"]["gpuUUID"], GPU_UUID)
        self.assertEqual(report["physicalFractions"]["totalSm"], "1")
        self.assertEqual(report["physicalFractions"]["totalMemory"], "1")
        self.assertEqual(report["physicalFractions"]["instances"]["3g.20gb"]["sm"], "3/7")
        self.assertEqual(report["physicalFractions"]["instances"]["3g.20gb"]["memory"], "1/2")

    def test_fleet_has_no_automatic_activation_artifact(self):
        # Automatic wiring or a manager-recognized config.yaml would break this boundary.
        result = self.run_renderer()
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["kind"], "ConfigMap")
        self.assertNotIn("config.yaml", document["data"])
        report = json.loads(document["data"]["review.json"])
        self.assertIs(report["activation"]["fleet"], False)
        self.assertFalse((ROOT / "fleet.yaml").exists())
        self.assertFalse((ROOT / "kustomization.yaml").exists())

    def test_missing_uuid_does_not_render(self):
        config, _ = fixtures()
        config["target"]["gpuUUID"] = None
        self.assert_rejected(config=config, field="gpuUUID")

    def test_protected_gpu1_target_does_not_render(self):
        config, preflight = fixtures()
        config["target"]["nodeName"] = preflight["nodeName"] = "k3s-wk-gpu1"
        self.assert_rejected(config, preflight, "nodeName")

    def test_uuid_and_index_must_refer_to_same_inventory_card(self):
        config, _ = fixtures()
        config["target"]["gpuIndex"] = 0
        self.assert_rejected(config=config, field="gpuIndex")

    def test_multi_card_and_all_card_targets_do_not_render(self):
        for index in ("all", [0, 1], True):
            with self.subTest(index=index):
                config, _ = fixtures()
                config["target"]["gpuIndex"] = index
                self.assert_rejected(config=config, field="gpuIndex")
        config, _ = fixtures()
        config["target"]["gpuUUID"] = [GPU_UUID, "GPU-44444444-4444-4444-8444-444444444444"]
        self.assert_rejected(config=config, field="gpuUUID")

    def test_unreviewed_selector_extension_does_not_render(self):
        config, _ = fixtures()
        config["target"]["nodeSelector"] = {"nvidia.com/gpu.present": "true"}
        self.assert_rejected(config=config, field="target")

    def test_incompatible_whole_gpu_batch_selectors_do_not_render(self):
        for selector in ({}, {"kubernetes.io/hostname": "k3s-wk-gpu2"},
                         {"compute.cps.unileoben.ac.at/gpu-mode": "mig-pilot"}):
            with self.subTest(selector=selector):
                config, _ = fixtures()
                config["exclusiveJobSelectors"][0]["nodeSelector"] = selector
                self.assert_rejected(config=config, field="exclusiveJobSelectors")

    def test_missing_exclusive_template_inventory_does_not_render(self):
        _, preflight = fixtures()
        preflight["exclusiveSelectorInventoryComplete"] = False
        self.assert_rejected(preflight=preflight, field="exclusiveSelectorInventoryComplete")

    def test_every_activation_switch_must_stay_false(self):
        config, _ = fixtures()
        for key in config["activation"]:
            with self.subTest(key=key):
                changed = copy.deepcopy(config)
                changed["activation"][key] = True
                self.assert_rejected(config=changed, field="activation")

    def test_existing_gpu_use_or_mig_mode_does_not_render(self):
        for field in ("activeGpuWorkloads", "activeGpuProcesses"):
            _, preflight = fixtures()
            preflight[field] = [{"name": "busy"}]
            self.assert_rejected(preflight=preflight, field=field)
        _, preflight = fixtures()
        preflight["cards"][1]["migMode"] = "Enabled"
        self.assert_rejected(preflight=preflight, field="migMode")

    def test_incomplete_inventory_or_stale_snapshot_does_not_render(self):
        _, preflight = fixtures()
        preflight["inventoryComplete"] = False
        self.assert_rejected(preflight=preflight, field="inventoryComplete")
        _, preflight = fixtures()
        preflight["capturedAt"] = "2020-01-01T00:00:00+00:00"
        self.assert_rejected(preflight=preflight, field="capturedAt")

    def test_unknown_model_or_duplicate_inventory_identity_does_not_render(self):
        _, preflight = fixtures()
        preflight["cards"][1]["productName"] = "NVIDIA A100-SXM4-80GB"
        self.assert_rejected(preflight=preflight, field="productName")
        _, preflight = fixtures()
        preflight["cards"].append(copy.deepcopy(preflight["cards"][1]))
        self.assert_rejected(preflight=preflight, field="cards")

    def test_geometry_cannot_be_repacked_without_another_review(self):
        config, _ = fixtures()
        config["geometry"] = {"1g.5gb": 8}
        self.assert_rejected(config=config, field="geometry")

    def test_protected_workload_identity_cannot_be_replaced(self):
        _, preflight = fixtures()
        preflight["protectedWorkload"]["uid"] = NODE_UID
        self.assert_rejected(preflight=preflight, field="protectedWorkload")

    def test_protected_workload_requires_explicit_true_declaration(self):
        _, preflight = fixtures()
        preflight["protectedWorkload"]["untouched"] = 1
        self.assert_rejected(preflight=preflight, field="protectedWorkload")

    def test_checked_in_config_and_example_cannot_activate_or_render(self):
        config = json.loads((ROOT / "pilot.json").read_text())
        preflight = json.loads((ROOT / "preflight.example.json").read_text())
        self.assertFalse(any(config["activation"].values()))
        self.assert_rejected(config, preflight, "nodeUID")


if __name__ == "__main__":
    unittest.main()
