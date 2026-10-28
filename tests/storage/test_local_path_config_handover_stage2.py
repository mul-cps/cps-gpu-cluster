"""Ensure stage two releases the packaged K3s ConfigMap from Fleet."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "cluster-maintenance/clusters/cit-cps-gpu/system/storage/storageclasses"


class LocalPathConfigHandoverStage2Tests(unittest.TestCase):
    def test_storage_bundle_omits_k3s_owned_configmap(self):
        self.assertFalse((STORAGE / "local-path-config.yaml").exists())
        for path in STORAGE.glob("*.yaml"):
            for document in yaml.safe_load_all(path.read_text()):
                if isinstance(document, dict):
                    self.assertFalse(document.get("kind") == "ConfigMap" and
                                     document.get("metadata", {}).get("name") == "local-path-config")

    def test_fleet_does_not_force_or_take_ownership(self):
        fleet = yaml.safe_load((STORAGE / "fleet.yaml").read_text())
        self.assertIs(fleet["helm"]["force"], False)
        self.assertFalse(fleet["helm"].get("takeOwnership", False))


if __name__ == "__main__":
    unittest.main()
