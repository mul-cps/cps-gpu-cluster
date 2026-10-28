import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("verify_same_pod", HERE / "verify_same_pod.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def evidence():
    pod_uid = "11111111-2222-3333-4444-555555555555"
    gpu = "GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cgroup = "/kubepods/pod11111111-2222-3333-4444-555555555555/containers/abc"
    return (
        {
            "schema": "native-shared-mps-host-attribution/v1",
            "runId": "samepod-01",
            "observedAtStart": "2026-10-29T10:00:10Z",
            "observedAtFinish": "2026-10-29T10:00:12Z",
            "servers": [{"pid": 101, "clients": [201, 202]}],
            "processes": [
                {"pid": 101, "namespacePids": [101], "cgroup": cgroup, "gpuUuids": [gpu]},
                {"pid": 201, "namespacePids": [201], "cgroup": cgroup, "gpuUuids": []},
                {"pid": 202, "namespacePids": [202], "cgroup": cgroup, "gpuUuids": []},
            ],
        },
        {
            "runId": "samepod-01", "podUid": pod_uid,
            "containerId": "containerd://abc", "cgroup": cgroup,
            "gpuUuid": gpu, "gpuMemoryCapBytes": 5368709120,
            "gpuMemoryCapEvidence": "native MPS readback soft=hard=5368709120",
        },
        {
            "runId": "samepod-01", "podUid": pod_uid,
            "probeSucceeded": True, "capBytes": 5368709120,
            "holdStartedAt": "2026-10-29T10:00:00Z",
            "holdFinishedAt": "2026-10-29T10:00:30Z",
            "survivor": {"namespacePid": 201, "heldBytes": 3221225472,
                         "progressBefore": 12, "progressAfter": 99},
            "challenger": {"namespacePid": 202, "overCapRequestedBytes": 4294967296,
                           "overCapRejected": True,
                           "recoveryBytes": 134217728,
                           "recoverySucceeded": True},
        },
    )


class SamePodMpsVerificationTests(unittest.TestCase):
    def test_accepts_two_clients_in_one_reviewed_pod_with_cap_and_peer_progress(self):
        capture, pod, workload = evidence()
        result = verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)
        self.assertTrue(result["samePodCgroup"])
        self.assertTrue(result["overCapRejected"])
        self.assertTrue(result["survivorProgressed"])
        self.assertFalse(result["productionQualified"])

    def test_rejects_clients_in_different_cgroups(self):
        capture, pod, workload = evidence()
        capture["processes"][2]["cgroup"] += "/other"
        with self.assertRaisesRegex(ValueError, "same container cgroup"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)

    def test_rejects_capture_without_two_distinct_clients(self):
        capture, pod, workload = evidence()
        capture["servers"][0]["clients"] = [201]
        with self.assertRaisesRegex(ValueError, "exactly two distinct clients"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)

    def test_rejects_mismatched_pod_or_run_identity(self):
        capture, pod, workload = evidence()
        pod["podUid"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        with self.assertRaisesRegex(ValueError, "Pod UID"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)
        capture, pod, workload = evidence()
        workload["runId"] = "other"
        with self.assertRaisesRegex(ValueError, "run ID"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)

    def test_rejects_wrong_cap_or_failed_workload_assertion(self):
        capture, pod, workload = evidence()
        pod["gpuMemoryCapBytes"] = 10737418240
        with self.assertRaisesRegex(ValueError, "GPU memory cap"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)

    def test_rejects_container_id_that_does_not_match_cgroup(self):
        capture, pod, workload = evidence()
        pod["containerId"] = "containerd://different"
        with self.assertRaisesRegex(ValueError, "container ID"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)
        capture, pod, workload = evidence()
        workload["challenger"]["overCapRejected"] = False
        with self.assertRaisesRegex(ValueError, "over-cap rejection"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)

    def test_requires_a_failed_allocation_that_exceeds_cap_only_in_aggregate(self):
        capture, pod, workload = evidence()
        workload["challenger"]["overCapRequestedBytes"] = 1073741824
        with self.assertRaisesRegex(ValueError, "aggregate cap"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)
        workload["survivor"]["heldBytes"] = 3221225472
        workload["challenger"]["overCapRequestedBytes"] = 3221225472
        workload["challenger"]["recoveryBytes"] = 134217728
        verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)

    def test_rejects_survivor_that_did_not_progress(self):
        capture, pod, workload = evidence()
        workload["survivor"]["progressAfter"] = 12
        with self.assertRaisesRegex(ValueError, "survivor progress"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)

    def test_rejects_host_capture_outside_the_live_two_client_hold(self):
        capture, pod, workload = evidence()
        capture["observedAtStart"] = "2026-10-29T10:01:00Z"
        capture["observedAtFinish"] = "2026-10-29T10:01:02Z"
        with self.assertRaisesRegex(ValueError, "did not overlap"):
            verifier.verify(capture, pod, workload, expected_cap_bytes=5368709120)


if __name__ == "__main__":
    unittest.main()
