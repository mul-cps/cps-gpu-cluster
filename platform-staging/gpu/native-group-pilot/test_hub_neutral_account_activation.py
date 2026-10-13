"""Secret-byte custody and executed config semantics, with no live access."""

import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid

import yaml

import native_group_approval_renderer as renderer


def fixture(source="cps"):
    owners = (
        ["cpsnativegroupa", "cpsnativegroupb"]
        if source == "cps"
        else ["citnativegroupa"]
    )
    auth = (
        (Path(__file__).parent / "tests-fixtures/hub-neutral-inline-auth.py")
        .read_text()
        .replace("OWNERS", repr(owners))
    )
    role = {
        "name": source + "-admin-api",
        "scopes": [
            "read:users:name",
            "read:users:groups",
            "read:roles:users",
            "read:servers",
            "list:users",
        ],
        "services": [source + "-admin"],
        "users": [],
        "groups": [],
    }
    tail = (
        "_native_services = "
        + repr([{"name": source + "-admin", "roles": [source + "-admin-api"]}])
        + "\n"
    )
    tail += "for _native_preserved in " + repr([role]) + ":\n    pass\n"
    tail += "_native_retained_tail = ['unchanged-owner-scopes', 'unchanged-storage']\n"
    values = {
        "hub": {
            "extraConfig": {
                "zy-native-group-access": auth + tail,
                "zz-native-group-pilot": "unchanged native execution configuration",
            },
            "config": {
                "JupyterHub": {
                    "authenticator_class": "oauthenticator.generic.GenericOAuthenticator"
                }
            },
            "services": {source + "-admin": {"apiToken": "private-example"}},
            "image": {"name": "unchanged-image-config", "tag": "unchanged"},
        }
    }
    data = {
        "values.yaml": base64.b64encode(
            yaml.safe_dump(values, sort_keys=False).encode()
        ).decode(),
        "hub.config.CryptKeeper.keys": base64.b64encode(
            b"private-example-key"
        ).decode(),
    }
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {
            "name": "hub",
            "namespace": "jupyterhub" if source == "cps" else "cit-jhub",
            "uid": str(uuid.UUID(int=1)),
            "resourceVersion": "123",
        },
        "data": data,
    }
    backup = b"actual controlled backup fixture bytes"
    return {
        "version": 1,
        "source": source,
        "target_image": "ghcr.io/mul-cps/cps-compute@sha256:466b8398285a513499440dd00aaf0abc377cc49afe05f19e5556e79908106486",
        "secret": secret,
        "secret_sha256": renderer.canonical_sha256(secret),
        "neutral_owners": owners,
        "legacy_owners": owners,
        "services": {
            source + "-admin": {
                "kind": "service",
                "name": source + "-admin",
                "roles": [source + "-admin-api"],
            }
        },
        "roles": {source + "-admin-api": role},
        "backup": {
            "sha256": hashlib.sha256(backup).hexdigest(),
            "bytes": len(backup),
            "source": source,
            "hub_version": "5.5.2",
            "secret_uid": secret["metadata"]["uid"],
            "values_sha256": hashlib.sha256(
                base64.b64decode(data["values.yaml"])
            ).hexdigest(),
        },
    }, backup


class ActivationTests(unittest.TestCase):
    def set_values(self, request, raw):
        request["secret"]["data"]["values.yaml"] = base64.b64encode(raw).decode()
        request["secret_sha256"] = renderer.canonical_sha256(request["secret"])
        request["backup"]["values_sha256"] = hashlib.sha256(raw).hexdigest()

    def compile(self, request, backup):
        import hub_neutral_account_activation as activation

        return activation.compile_intent(
            request,
            backup_sha256=hashlib.sha256(backup).hexdigest(),
            backup_bytes=len(backup),
        )

    def test_only_auth_block_and_own_service_scope_change_with_complete_secret_cas(
        self,
    ):
        for source in ("cps", "cit"):
            request, backup = fixture(source)
            intent = self.compile(request, backup)
            self.assertFalse(intent["live_applied"])
            patch = intent["secret_patch"]
            self.assertEqual(
                [item["op"] for item in patch],
                ["test", "test", "test", "test", "replace"],
            )
            self.assertEqual(patch[3]["value"], request["secret"]["data"])
            old = yaml.safe_load(
                base64.b64decode(request["secret"]["data"]["values.yaml"])
            )
            new = yaml.safe_load(base64.b64decode(patch[-1]["value"]["values.yaml"]))
            old_code = old["hub"]["extraConfig"].pop("zy-native-group-access")
            new_code = new["hub"]["extraConfig"].pop("zy-native-group-access")
            self.assertEqual(old, new)
            self.assertEqual(
                request["secret"]["data"]["hub.config.CryptKeeper.keys"],
                patch[-1]["value"]["hub.config.CryptKeeper.keys"],
            )
            self.assertIn("install_workspace_account_provisioning", new_code)
            self.assertNotIn("class CPSNativeLoginGuard", new_code)
            self.assertEqual(
                new_code.count("custom:cps:provision:workspace-account"), 1
            )
            self.assertIn(
                "_native_retained_tail = ['unchanged-owner-scopes', 'unchanged-storage']",
                new_code,
            )
            self.assertIn(
                "_native_retained_tail = ['unchanged-owner-scopes', 'unchanged-storage']",
                old_code,
            )

    def test_backup_identity_image_uid_and_source_service_binding_are_closed(self):
        for fault in (
            "no-backup",
            "wrong-backup",
            "wrong-uid",
            "wrong-values",
            "wrong-image",
            "foreign-service",
            "user-service",
            "wrong-role",
            "missing-owner",
            "extra-key",
        ):
            request, backup = fixture()
            if fault == "no-backup":
                del request["backup"]
            elif fault == "wrong-backup":
                request["backup"]["sha256"] = "f" * 64
            elif fault == "wrong-uid":
                request["backup"]["secret_uid"] = str(uuid.UUID(int=2))
            elif fault == "wrong-values":
                request["backup"]["values_sha256"] = "f" * 64
            elif fault == "wrong-image":
                request["target_image"] = request["target_image"].replace(
                    "466b", "ffff"
                )
            elif fault == "foreign-service":
                request["services"]["cps-admin"]["name"] = "cit-admin"
            elif fault == "user-service":
                request["services"]["cps-admin"]["kind"] = "user"
            elif fault == "wrong-role":
                request["roles"]["cps-admin-api"]["services"] = ["foreign"]
            elif fault == "missing-owner":
                request["neutral_owners"].pop()
            else:
                request["arbitrary_gpu_owner_allowlist"] = ["new-owner"]
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                self.compile(request, backup)

    def test_modified_inline_guard_or_role_scope_cannot_be_silently_overwritten(self):
        for fault in ("class", "scope"):
            request, backup = fixture()
            values = yaml.safe_load(
                base64.b64decode(request["secret"]["data"]["values.yaml"])
            )
            code = values["hub"]["extraConfig"]["zy-native-group-access"]
            code = (
                code.replace("return False", "return True", 1)
                if fault == "class"
                else code.replace("read:servers", "admin:users")
            )
            values["hub"]["extraConfig"]["zy-native-group-access"] = code
            encoded = yaml.safe_dump(values, sort_keys=False).encode()
            request["secret"]["data"]["values.yaml"] = base64.b64encode(
                encoded
            ).decode()
            request["secret_sha256"] = renderer.canonical_sha256(request["secret"])
            request["backup"]["values_sha256"] = hashlib.sha256(encoded).hexdigest()
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                self.compile(request, backup)

    def test_cli_defaults_are_inert_and_private_backup_is_required(self):
        import hub_neutral_account_activation as activation

        self.assertEqual(activation.main([]), 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup"
            path.write_bytes(b"backup")
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                activation.backup_digest(path)

    def test_unrelated_yaml_bytes_are_preserved(self):
        request, backup = fixture()
        raw = base64.b64decode(request["secret"]["data"]["values.yaml"])
        prefix = b"# retained non-auth configuration comment\n"
        suffix = b"# retained trailing comment\n"
        self.set_values(request, prefix + raw + suffix)
        intent = self.compile(request, backup)
        target = base64.b64decode(intent["secret_patch"][-1]["value"]["values.yaml"])
        self.assertTrue(target.startswith(prefix))
        self.assertTrue(target.endswith(suffix))

    def test_duplicate_configuration_anchors_and_role_keys_are_rejected(self):
        for fault in (
            "owner",
            "annotated-owner",
            "authenticator",
            "annotated-authenticator",
            "chained-authenticator",
            "role-scopes",
            "yaml-hub",
            "yaml-extraConfig",
            "yaml-zy",
        ):
            request, backup = fixture()
            raw = base64.b64decode(request["secret"]["data"]["values.yaml"])
            values = yaml.safe_load(raw)
            code = values["hub"]["extraConfig"]["zy-native-group-access"]
            if fault == "owner":
                code += (
                    "\n_native_owners = frozenset("
                    + repr(request["neutral_owners"])
                    + ")\n"
                )
            elif fault == "annotated-owner":
                code += (
                    "\n_native_owners: object = frozenset("
                    + repr(request["neutral_owners"])
                    + ")\n"
                )
            elif fault == "authenticator":
                code += "\nc.JupyterHub.authenticator_class = CPSNativeLoginGuard\n"
            elif fault == "annotated-authenticator":
                code += (
                    "\nc.JupyterHub.authenticator_class: object = CPSNativeLoginGuard\n"
                )
            elif fault == "chained-authenticator":
                code += (
                    "\nextra = c.JupyterHub.authenticator_class = CPSNativeLoginGuard\n"
                )
            elif fault == "role-scopes":
                code = code.replace("'scopes': [", "'scopes': [], 'scopes': [", 1)
            if fault.startswith("yaml-"):
                text = raw.decode()
                if fault == "yaml-hub":
                    text = "hub: {}\n" + text
                elif fault == "yaml-extraConfig":
                    text = text.replace(
                        "  extraConfig:\n", "  extraConfig: {}\n  extraConfig:\n", 1
                    )
                else:
                    text = text.replace(
                        "    zy-native-group-access:",
                        "    zy-native-group-access: ignored\n    zy-native-group-access:",
                        1,
                    )
                raw = text.encode()
            else:
                values["hub"]["extraConfig"]["zy-native-group-access"] = code
                raw = yaml.safe_dump(values, sort_keys=False).encode()
            self.set_values(request, raw)
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                self.compile(request, backup)


if __name__ == "__main__":
    unittest.main()
