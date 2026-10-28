"""Guard the non-destructive first stage of the local-path ConfigMap handover."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "cluster-maintenance/clusters/cit-cps-gpu/system/storage/storageclasses"
CONFIG_MAP = STORAGE / "local-path-config.yaml"
BASELINE = ROOT / "tests/storage/fixtures/local-path-config-release-97.yaml"


class LocalPathConfigHandoverStage1Tests(unittest.TestCase):
    def test_stage1_adds_only_keep_policy_to_the_release_manifest_object(self):
        current = yaml.safe_load(CONFIG_MAP.read_text())
        baseline = yaml.safe_load(BASELINE.read_text())

        self.assertEqual((current["kind"], current["metadata"]["name"], current["metadata"]["namespace"]),
                         (baseline["kind"], baseline["metadata"]["name"], baseline["metadata"]["namespace"]))
        self.assertEqual(current["data"], baseline["data"])
        self.assertEqual(current["metadata"]["annotations"], {"helm.sh/resource-policy": "keep"})

        # Fleet must patch, not force-replace, the live ConfigMap in this stage.
        fleet = yaml.safe_load((STORAGE / "fleet.yaml").read_text())
        self.assertIs(fleet["helm"]["force"], False)

    def test_new_provisioner_does_not_depend_on_handover(self):
        isolated = yaml.safe_load((ROOT / "cluster-maintenance/clusters/cit-cps-gpu/system/storage/fast-scratch-isolated/fleet.yaml").read_text())
        self.assertNotIn("dependsOn", isolated)

    def test_stage1_storage_bundle_has_no_prerequisite_gate(self):
        storage = yaml.safe_load((STORAGE / "fleet.yaml").read_text())
        self.assertNotIn("dependsOn", storage)
        self.assertIs(storage["helm"]["force"], False)


if __name__ == "__main__":
    unittest.main()
