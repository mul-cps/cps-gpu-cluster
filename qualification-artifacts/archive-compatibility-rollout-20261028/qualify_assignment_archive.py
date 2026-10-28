#!/usr/bin/env python3
"""Offline acceptance fixture for the archived Source and gateway wheels.

Default execution is a dry-run plan. ``--in-process`` exercises the pinned
wheel route handlers against temporary SQLite and FastAPI ASGI fixtures only;
this utility has no live mode and accepts no credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import zipfile

if "--in-process" in sys.argv:
    from tornado.testing import AsyncHTTPTestCase as _TestBase
else:
    _TestBase = unittest.TestCase


ROOT = Path(__file__).resolve().parent
SOURCE_WHEEL_NAME = "e2x_course_hub-0.1.2-py3-none-any.whl"
GATEWAY_WHEEL_NAME = "cps_compute-0.1.1-py3-none-any.whl"
SOURCE_WHEEL_SHA256 = "a582d48a333d2aaf1eeb8edf5d9fa5041799b8a992baa954a1336c6b389093a5"
GATEWAY_WHEEL_SHA256 = "ac7ccb12aed2832a79e93df7968a236ce77fc050ef54c2848d026dd5f14befff"
SOURCE_WHEEL: Path | None = None
GATEWAY_WHEEL: Path | None = None
WHEEL_TEMP: tempfile.TemporaryDirectory | None = None

ACTOR = "archive-qualification-admin"
COURSE = "cit-archive-qualification-course"
TERM = "cit-archive-qualification-term"
ASSIGNMENT = "cit-archive-qualification-assignment"
PEOPLE = (
    ("archive-qualification-person-a", "00000000-0000-4000-8000-0000000000a1"),
    ("archive-qualification-person-b", "00000000-0000-4000-8000-0000000000b2"),
)
GROUPS = (f"{ASSIGNMENT}-group-a", f"{ASSIGNMENT}-group-b")
WORKSPACES = ("cit-archive-qualification-ws-a", "cit-archive-qualification-ws-b")
NEUTRAL_USERS = ("archive-qualification-neutral-a", "archive-qualification-neutral-b")
CEILING = {"cpu": "2", "memory": "4Gi"}


def print_dry_run() -> None:
    plan = {
        "mode": "dry-run",
        "api": "pinned Source 0.1.2 and gateway 0.1.1 wheels; no credentials or network",
        "fixture": "two synthetic CIT identities, two manual groups, two CPU workspaces",
        "source_routes": [
            {"method": "POST", "path": "/api/local/courses", "body": {
                "id": COURSE, "resource_ceiling": CEILING,
                "workspace_bindings": [
                    {"group_id": group, "hub_user": user, "hub_server": "rtc",
                     "namespace": "cit-jhub", "pod": user}
                    for group, user in zip(GROUPS, NEUTRAL_USERS)
                ],
            }},
            {"method": "POST", "path": "/api/local/terms", "body": {
                "id": TERM, "course_id": COURSE, "term_id": TERM,
            }},
            {"method": "POST", "path": "/api/identities", "body": {
                "mappings": [{
                    "hub": "cit", "username": username, "person_id": person,
                    "authority": "reviewed_account_alias", "administrator_reviewed": True,
                    "review_reason": "Synthetic offline archive fixture identity",
                } for username, person in PEOPLE],
            }},
            *[{
                "method": "POST", "path": "/api/local/memberships", "body": {
                    "id": f"fixture-membership-{index}", "course_id": COURSE,
                    "term_id": TERM, "person_id": username,
                    "canonical_person_id": person, "role": "student",
                },
            } for index, (username, person) in enumerate(PEOPLE, 1)],
            {"method": "POST", "path": "/api/assignments/allocate", "body": {
                "id": ASSIGNMENT, "course_id": COURSE, "term_id": TERM,
                "mode": "manual",
                "rows": {"group-a": [PEOPLE[0][0]], "group-b": [PEOPLE[1][0]]},
            }},
            *[{
                "method": "POST", "path": "/api/workspaces/create", "body": {
                    "id": workspace, "course_id": COURSE, "term_id": TERM,
                    "group_id": group, "hub_user": user, "hub_server": "rtc",
                    "profile": "interactive-cpu", "course_ceiling": CEILING,
                },
            } for workspace, group, user in zip(WORKSPACES, GROUPS, NEUTRAL_USERS)],
            *[{
                "method": "POST", "path": f"/api/workspaces/{workspace}/start", "body": {},
            } for workspace in WORKSPACES],
            {"method": "POST", "path": f"/api/assignments/{ASSIGNMENT}/close", "body": {}},
        ],
        "closure_retry": "first archive call deliberately fails for group-b; retry re-verifies group-a and closes both",
        "live_prerequisite": "WorkspaceCreateHandler stores a stopped Source record; POST /api/workspaces/{id}/start is required to provision the neutral account, register and provision CPU storage before closure. The offline fixture seeds fake gateway registrations instead.",
        "live_mutation": "not supported by this script",
    }
    print(json.dumps(plan, indent=2))


def load_pinned_wheels(wheel_dir: Path) -> None:
    """Verify and unpack the pinned wheels to temporary import directories."""
    global WHEEL_TEMP, SOURCE_WHEEL, GATEWAY_WHEEL
    SOURCE_WHEEL = wheel_dir / SOURCE_WHEEL_NAME
    GATEWAY_WHEEL = wheel_dir / GATEWAY_WHEEL_NAME
    expected = ((SOURCE_WHEEL, SOURCE_WHEEL_SHA256), (GATEWAY_WHEEL, GATEWAY_WHEEL_SHA256))
    for wheel, digest in expected:
        if not wheel.is_file():
            raise ValueError(f"required wheel is missing: {wheel.name}")
        actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"wheel digest mismatch: {wheel.name}")
    WHEEL_TEMP = tempfile.TemporaryDirectory(prefix="archive-wheel-fixture-")
    root = Path(WHEEL_TEMP.name)
    for wheel in (SOURCE_WHEEL, GATEWAY_WHEEL):
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(root / wheel.stem)
        sys.path.insert(0, str(root / wheel.stem))


class AssignmentArchiveOfflineQualification(_TestBase):
    """Use the pinned Source handlers and gateway archive route in-process."""

    def get_app(self):
        from cps_compute.internal import ControlStore, ServiceIdentity, install_internal
        from cps_compute.reservations import Reservations
        from cps_compute.storage import binding
        from e2x_course_hub.cps.filesystem import CourseServiceFilesystemAdapter
        from e2x_course_hub.cps.platform_handlers import (
            AssignmentCloseHandler, AssignmentHandler, IdentityMappingHandler,
            WorkspaceCreateHandler,
        )
        from e2x_course_hub.cps.handlers import RecordsHandler
        from e2x_course_hub.cps.providers import LocalCourseProvider
        from e2x_course_hub.cps.workspaces import WorkspaceService
        from tornado import web
        import httpx

        self.temp = tempfile.TemporaryDirectory(prefix="cit-archive-qualification-")
        temp_path = Path(self.temp.name)
        self.provider = LocalCourseProvider(temp_path / "source.sqlite", "cit")
        self.archive_calls: list[str] = []
        self.fail_group_b = True
        self.service_identity = ServiceIdentity("console", "cit")
        self.store = ControlStore(temp_path / "control")
        reservations = Reservations(temp_path / "reservations")

        for workspace, group, neutral in zip(WORKSPACES, GROUPS, NEUTRAL_USERS):
            self.store.put_workspace({
                "workspace": workspace,
                "group_id": group,
                "owner": neutral,
                "server": "rtc",
                "policy_hash": "offline-fixture-policy",
                "storage": {
                    "pv": f"pv-{group}", "pvc": f"pvc-{group}",
                    "namespace": "cit-jhub", "path": binding("cit", group)[1],
                    "state": "active",
                },
            }, self.service_identity, reservations)

        outer = self

        class ArchiveBackend:
            async def archive(inner, source, workspaces, actor):
                group = workspaces[0]["group_id"]
                outer.archive_calls.append(group)
                if group == GROUPS[1] and outer.fail_group_b:
                    raise RuntimeError("synthetic second-group failure")
                return {"state": "archived", "read_only_verified": True,
                        "evidence": {"synthetic_group": group}}

        async def gateway_auth(token):
            if token != "offline-fixture-token":
                raise PermissionError("unexpected fixture token")
            return self.service_identity

        async def yes(*args, **kwargs):
            return True

        gateway_app = __import__("fastapi").FastAPI()
        install_internal(
            gateway_app, self.store, reservations, gateway_auth, yes,
            SimpleNamespace(hash="offline-fixture-policy"),
            workspace_owner_check=yes, storage_controller=ArchiveBackend(),
        )
        self.gateway_client = httpx.AsyncClient(
            base_url="https://gateway.fixture",
            transport=httpx.ASGITransport(app=gateway_app),
            headers={"Authorization": "Bearer offline-fixture-token"},
        )
        self.adapter = CourseServiceFilesystemAdapter.__new__(CourseServiceFilesystemAdapter)
        self.adapter.client = self.gateway_client

        class Compute:
            async def validate_workspace(inner, *args, **kwargs):
                return {"policy_hash": "offline-fixture-policy"}

            async def reservation_state(inner, workspace):
                return {"active": False, "attempt": None}

            async def release_after_shutdown(inner, *args, **kwargs):
                return None

        class Hub:
            async def stop_confirmed(inner, workspace):
                return None

            async def revoke_shares(inner, workspace):
                return None

        self.service = WorkspaceService(self.provider, Compute(), Hub(), filesystem=self.adapter)

        class HubAPI:
            async def get_user(inner, username):
                return {"name": username, "admin": username == ACTOR}

        api = SimpleNamespace(course_api=SimpleNamespace(hub_api=HubAPI()))

        class Authenticated:
            def get_current_user(inner):
                return {"name": ACTOR}

            async def authorize(inner, *args, **kwargs):
                return ACTOR

        class LocalRecords(Authenticated, RecordsHandler):
            async def authorize_record(inner, kind, data, *, read=False):
                return ACTOR

        class Identities(Authenticated, IdentityMappingHandler):
            pass

        class Allocation(Authenticated, AssignmentHandler):
            pass

        class CreateWorkspace(Authenticated, WorkspaceCreateHandler):
            pass

        class CloseAssignment(Authenticated, AssignmentCloseHandler):
            pass

        return web.Application([
            (r"/api/local/(courses|terms|memberships|groups|groupings|projects|assignments|workspaces|audit)", LocalRecords),
            (r"/api/identities", Identities),
            (r"/api/assignments/allocate", Allocation),
            (r"/api/workspaces/create", CreateWorkspace),
            (r"/api/assignments/([^/]+)/close", CloseAssignment),
        ], cookie_secret="offline-fixture", xsrf_cookies=False,
            course_provider=self.provider, workspace_service=self.service, api=api,
            console_owner="cit", last_config_check=10**12)

    def tearDown(self) -> None:
        self.io_loop.run_sync(self.gateway_client.aclose)
        self.provider.db.close()
        self.temp.cleanup()
        super().tearDown()

    def post_json(self, path: str, body: dict):
        from tornado.escape import json_encode
        return self.fetch(path, method="POST", body=json_encode(body))

    def test_manual_assignment_archive_retries_cleanly(self) -> None:
        from cps_compute.internal import ControlStore

        bindings = [
            {"group_id": group, "hub_user": neutral, "hub_server": "rtc",
             "namespace": "cit-jhub", "pod": neutral}
            for group, neutral in zip(GROUPS, NEUTRAL_USERS)
        ]
        response = self.post_json("/api/local/courses", {
            "id": COURSE, "name": "Synthetic CIT archive qualification",
            "resource_ceiling": CEILING, "workspace_bindings": bindings,
        })
        self.assertEqual(response.code, 200, response.body.decode())
        response = self.post_json("/api/local/terms", {
            "id": TERM, "course_id": COURSE, "term_id": TERM,
            "name": "Synthetic qualification term",
        })
        self.assertEqual(response.code, 200, response.body.decode())

        response = self.post_json("/api/identities", {"mappings": [
            {"hub": "cit", "username": username, "person_id": person,
             "authority": "reviewed_account_alias", "administrator_reviewed": True,
             "review_reason": "Synthetic offline archive fixture identity"}
            for username, person in PEOPLE
        ]})
        self.assertEqual(response.code, 200, response.body.decode())
        for index, (username, person) in enumerate(PEOPLE, 1):
            response = self.post_json("/api/local/memberships", {
                "id": f"fixture-membership-{index}", "course_id": COURSE,
                "term_id": TERM, "person_id": username,
                "canonical_person_id": person, "role": "student",
            })
            self.assertEqual(response.code, 200, response.body.decode())

        response = self.post_json("/api/assignments/allocate", {
            "id": ASSIGNMENT, "course_id": COURSE, "term_id": TERM,
            "mode": "manual",
            "rows": {"group-a": [PEOPLE[0][0]], "group-b": [PEOPLE[1][0]]},
        })
        self.assertEqual(response.code, 200, response.body.decode())
        allocated = json.loads(response.body)
        self.assertEqual(set(allocated["groups"]), {"group-a", "group-b"})
        self.assertEqual(set(allocated["groups"]["group-a"]), {PEOPLE[0][0]})
        self.assertEqual(set(allocated["groups"]["group-b"]), {PEOPLE[1][0]})

        for workspace, group, neutral in zip(WORKSPACES, GROUPS, NEUTRAL_USERS):
            response = self.post_json("/api/workspaces/create", {
                "id": workspace, "course_id": COURSE, "term_id": TERM,
                "group_id": group, "hub_user": neutral, "hub_server": "rtc",
                "profile": "interactive-cpu", "course_ceiling": CEILING,
            })
            self.assertEqual(response.code, 200, response.body.decode())

        response = self.fetch(f"/api/assignments/{ASSIGNMENT}/close", method="POST", body="{}")
        self.assertEqual(response.code, 503, response.body.decode())
        assignment = self.io_loop.run_sync(lambda: self.provider.list("assignments"))[0]
        self.assertTrue(assignment["archive_pending"])
        self.assertFalse(assignment.get("archived", False))
        workspaces = self.io_loop.run_sync(lambda: self.provider.list("workspaces"))
        self.assertEqual(len(workspaces), 2)
        self.assertTrue(all(w["archive_pending"] and not w.get("archived", False)
                            for w in workspaces))
        self.assertEqual(self.store.workspace("cit", WORKSPACES[0])["storage"]["state"], "archived")
        self.assertEqual(self.store.workspace("cit", WORKSPACES[1])["storage"]["state"], "archiving")
        self.assertNotIn("synthetic second-group failure", response.body.decode())
        self.assertEqual(self.archive_calls, [GROUPS[0], GROUPS[1]])

        # A retry re-verifies the already archived first group and completes the second.
        self.fail_group_b = False
        response = self.fetch(f"/api/assignments/{ASSIGNMENT}/close", method="POST", body="{}")
        self.assertEqual(response.code, 200, response.body.decode())
        result = json.loads(response.body)
        self.assertTrue(result["assignment"]["archived"])
        self.assertFalse(result["assignment"]["archive_pending"])
        self.assertEqual(self.archive_calls,
                         [GROUPS[0], GROUPS[1], GROUPS[0], GROUPS[1]])
        self.assertEqual(self.store.workspace("cit", WORKSPACES[0])["storage"]["state"], "archived")
        self.assertEqual(self.store.workspace("cit", WORKSPACES[1])["storage"]["state"], "archived")
        workspaces = self.io_loop.run_sync(lambda: self.provider.list("workspaces"))
        self.assertTrue(all(w["archived"] and not w["archive_pending"]
                            for w in workspaces))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-process", action="store_true",
                        help="run local Source/Tornado and gateway/FastAPI fixture")
    parser.add_argument("--wheel-dir", type=Path, default=ROOT / "wheels",
                        help="directory containing the two SHA-pinned wheels (default: sibling wheels/)")
    args = parser.parse_args()
    if not args.in_process:
        print_dry_run()
        return 0
    try:
        load_pinned_wheels(args.wheel_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AssignmentArchiveOfflineQualification)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
