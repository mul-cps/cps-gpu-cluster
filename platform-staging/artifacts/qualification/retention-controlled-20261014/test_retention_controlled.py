import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).parent


def module(name):
    path = HERE / name
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Guards(unittest.TestCase):
    def test_storage_rejects_any_other_bucket_key_or_prefix_before_client_call(self):
        fixture = module("fixture.py")
        calls = []

        class Client:
            def head_object(self, **kw):
                calls.append(kw)
                return kw

            def get_paginator(self, name):
                raise AssertionError("Unexpected list initialization")

        storage = fixture.ScopedStorage(
            Client(), "qa-bucket", {"notebook-inputs/123/snapshot.tar"}
        )
        storage.head_object(Bucket="qa-bucket", Key="notebook-inputs/123/snapshot.tar")
        for kw in (
            {"Bucket": "other", "Key": "notebook-inputs/123/snapshot.tar"},
            {"Bucket": "qa-bucket", "Key": "notebook-inputs/production/snapshot.tar"},
        ):
            with self.assertRaises(ValueError):
                storage.head_object(**kw)
        self.assertEqual(len(calls), 1)
        for prefix in (
            None,
            "notebook-inputs/",
            "notebook-inputs/123",
            "run-artifacts/123/",
        ):
            with self.assertRaises(ValueError):
                list(storage.paginate(Bucket="qa-bucket", Prefix=prefix))

    def test_initial_object_creation_is_conditional_and_mutation_cannot_widen_scope(
        self,
    ):
        fixture = module("fixture.py")

        class Client:
            def put_object(self, **kw):
                return kw

        storage = fixture.ScopedStorage(
            Client(), "qa-bucket", {"notebook-inputs/123/snapshot.tar"}
        )
        with self.assertRaises(ValueError):
            storage.put_object(
                Bucket="qa-bucket", Key="notebook-inputs/123/snapshot.tar", Body=b"x"
            )
        self.assertEqual(
            storage.put_object(
                Bucket="qa-bucket",
                Key="notebook-inputs/123/snapshot.tar",
                Body=b"x",
                IfNoneMatch="*",
            )["IfNoneMatch"],
            "*",
        )

    def test_workflow_role_has_only_named_get_patch_and_pod_has_no_automount(self):
        runner = module("run.py")
        names = [
            "cps-11111111-2222-4333-8444-555555555555",
            "cps-22222222-2222-4333-8444-555555555555",
        ]
        resources = runner.authorization("qa-retention", names)
        role = next(item for item in resources if item["kind"] == "Role")
        self.assertEqual(
            role["rules"],
            [
                {
                    "apiGroups": ["argoproj.io"],
                    "resources": ["workflows"],
                    "resourceNames": names,
                    "verbs": ["get", "patch"],
                }
            ],
        )
        sa = next(item for item in resources if item["kind"] == "ServiceAccount")
        self.assertFalse(sa["automountServiceAccountToken"])
        binding = next(item for item in resources if item["kind"] == "RoleBinding")
        self.assertEqual(
            binding["subjects"],
            [
                {
                    "kind": "ServiceAccount",
                    "name": "qa-retention",
                    "namespace": "cps-compute",
                }
            ],
        )

    def test_case_inventory_covers_both_exact_ages_and_protective_states(self):
        runner = module("run.py")
        cases = runner.case_inventory()
        self.assertEqual(len(cases), 10)
        self.assertEqual({case["days"] for case in cases}, {14, 90})
        self.assertEqual(
            {case["case"] for case in cases},
            {
                "boundary",
                "active",
                "retained-tag",
                "retained-claim",
                "etag-conflict",
                "ambiguous-before",
                "ambiguous-after",
            },
        )
        self.assertEqual(len({case["identifier"] for case in cases}), len(cases))


if __name__ == "__main__":
    unittest.main()
