"""Contract checks for the opt-in, separately provisioned NVMe StorageClass."""

from pathlib import Path
import subprocess
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "cluster-maintenance/clusters/cit-cps-gpu/system/storage/fast-scratch-isolated"
RELEASE = "fast-scratch-isolated"
NAMESPACE = "fast-scratch-system"
PROVISIONER = "storage.cps.local/fast-scratch-isolated"
GPU_NODES = ("k3s-wk-gpu1", "k3s-wk-gpu2", "k3s-wk-gpu3", "k3s-wk-gpu4")
CONTROLLER_IMAGE = (
    "rancher/local-path-provisioner:v0.0.36"
    "@sha256:1eba82e9c386038b4af6d69cca7519fac738c28c42735ed48ce70c882ad0d80f"
)
HELPER_IMAGE = (
    "rancher/mirrored-library-busybox:1.37.0"
    "@sha256:101b4afd76732482eff9b95cae5f94bcf295e521fbec4e01b69c5421f3f3f3e5"
)


class FastScratchIsolatedRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rendered = subprocess.run(
            ["helm", "template", RELEASE, "./chart", "--namespace", NAMESPACE,
             "--values", "values.yaml"],
            cwd=BUNDLE,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        cls.objects = [obj for obj in yaml.safe_load_all(rendered) if obj]
        cls.by_kind_name = {(obj["kind"], obj["metadata"]["name"]): obj for obj in cls.objects}

    def test_new_storage_class_is_opt_in_and_uses_its_private_provisioner(self):
        sc = self.by_kind_name[("StorageClass", "fast-scratch-isolated")]
        self.assertEqual(sc["provisioner"], PROVISIONER)
        self.assertEqual(sc["volumeBindingMode"], "WaitForFirstConsumer")
        self.assertEqual(sc["reclaimPolicy"], "Delete")
        self.assertEqual(sc["metadata"]["annotations"]["storageclass.kubernetes.io/is-default-class"], "false")
        self.assertEqual(
            sc["allowedTopologies"][0]["matchLabelExpressions"][0]["values"],
            list(GPU_NODES),
        )
        self.assertEqual(
            sc["allowedTopologies"][0]["matchLabelExpressions"][0]["values"],
            list(GPU_NODES),
        )
        self.assertNotIn(("StorageClass", "fast-scratch"), self.by_kind_name)
        self.assertNotIn(("StorageClass", "local-path"), self.by_kind_name)

    def test_private_controller_uses_a_distinct_config_and_provisioner_name(self):
        deployment = next(obj for obj in self.objects if obj["kind"] == "Deployment")
        self.assertEqual(deployment["metadata"]["namespace"], NAMESPACE)
        self.assertNotEqual(deployment["metadata"]["name"], "local-path-provisioner")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["image"], CONTROLLER_IMAGE)
        command = container["command"]
        self.assertIn(PROVISIONER, command)
        self.assertIn("fast-scratch-isolated-config", command)
        helper = self.by_kind_name[("ConfigMap", "fast-scratch-isolated-config")]["data"]["helperPod.yaml"]
        self.assertIn(HELPER_IMAGE, helper)
        config_volume = next(v for v in deployment["spec"]["template"]["spec"]["volumes"]
                             if v["name"] == "config-volume")
        self.assertEqual(config_volume["configMap"]["name"], "fast-scratch-isolated-config")
        self.assertIn(("ConfigMap", "fast-scratch-isolated-config"), self.by_kind_name)
        self.assertNotIn(("ConfigMap", "local-path-config"), self.by_kind_name)
        self.assertIn(("ServiceAccount", "fast-scratch-isolated-provisioner"), self.by_kind_name)
        self.assertIn(("ClusterRole", "fast-scratch-isolated-provisioner"), self.by_kind_name)
        self.assertIn(("ClusterRoleBinding", "fast-scratch-isolated-provisioner"), self.by_kind_name)

    def test_config_allows_nvme_only_on_gpu_workers(self):
        cm = self.by_kind_name[("ConfigMap", "fast-scratch-isolated-config")]
        import json

        node_paths = json.loads(cm["data"]["config.json"])["nodePathMap"]
        self.assertEqual(node_paths[0], {
            "node": "DEFAULT_PATH_FOR_NON_LISTED_NODES", "paths": []
        })
        self.assertEqual(
            {entry["node"]: entry["paths"] for entry in node_paths[1:]},
            {node: ["/mnt/nvme/scratch"] for node in GPU_NODES},
        )

    def test_legacy_fast_scratch_and_existing_release_source_remain_intact(self):
        storage_classes = ROOT / "cluster-maintenance/clusters/cit-cps-gpu/system/storage/storageclasses"
        self.assertTrue((storage_classes / "local-path-config.yaml").exists())
        fleet = yaml.safe_load((storage_classes / "fleet.yaml").read_text())
        self.assertIs(fleet["helm"]["force"], False)
        self.assertIs(fleet["helm"]["takeOwnership"], True)

        bootstrap = (ROOT / "bootstrap-cluster/ansible/playbooks/03-storage.yml").read_text()
        self.assertIn("name: {{ scratch_storage_class_name }}", bootstrap)
        self.assertIn("provisioner: rancher.io/local-path", bootstrap)
        self.assertIn("nodePath: {{ scratch_path }}", bootstrap)

        chart = yaml.safe_load((BUNDLE / "chart/Chart.yaml").read_text())
        self.assertEqual(chart["version"], "0.0.36")
        self.assertEqual(chart["appVersion"], "v0.0.36")
        values = yaml.safe_load((BUNDLE / "values.yaml").read_text())
        self.assertEqual(values["image"]["tag"], CONTROLLER_IMAGE.split(":", 1)[1])
        self.assertEqual(values["helperImage"]["tag"], HELPER_IMAGE.split(":", 1)[1])
        isolated_fleet = yaml.safe_load((BUNDLE / "fleet.yaml").read_text())
        self.assertNotIn("dependsOn", isolated_fleet)


if __name__ == "__main__":
    unittest.main()
