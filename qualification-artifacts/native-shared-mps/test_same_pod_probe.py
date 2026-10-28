import importlib.util
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("same_pod_probe", HERE / "same_pod_probe.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class SamePodProbeValidationTests(unittest.TestCase):
    def test_builds_receipt_for_aggregate_oom_recovery_and_peer_progress(self):
        plan = probe.validate_plan(5 * 1024**3, 3 * 1024**3, 3 * 1024**3, 128 * 1024**2)
        receipt = probe.build_workload_receipt(
            "run-01", "11111111-2222-3333-4444-555555555555", plan,
        {"namespacePid": 17, "heldBytes": 3 * 1024**3,
         "progressBefore": 10, "progressAfter": 40},
        {"namespacePid": 18, "overCapRequestedBytes": 3 * 1024**3,
         "overCapRejected": True, "recoveryBytes": 128 * 1024**2,
         "recoverySucceeded": True},
        )
        self.assertTrue(receipt["probeSucceeded"])
        self.assertEqual(receipt["survivor"]["namespacePid"], 17)
        self.assertEqual(receipt["challenger"]["namespacePid"], 18)

    def test_requires_individually_in_cap_requests_whose_sum_exceeds_cap(self):
        self.assertRaises(ValueError, probe.validate_plan, 5, 3, 2, 1)
        self.assertRaises(ValueError, probe.validate_plan, 5, 6, 1, 1)
        self.assertRaises(ValueError, probe.validate_plan, 5, 3, 6, 1)
        self.assertRaises(ValueError, probe.validate_plan, 5, 3, 3, 3)

    def test_receipt_rejects_missing_peer_progress_oom_or_recovery(self):
        plan = probe.validate_plan(500, 300, 300, 50)
        survivor = {"namespacePid": 17, "heldBytes": 300,
                    "progressBefore": 10, "progressAfter": 20}
        challenger = {"namespacePid": 18, "overCapRequestedBytes": 300,
                      "overCapRejected": True, "recoverySucceeded": True}
        for change in ("progress", "oom", "recovery", "pid"):
            with self.subTest(change=change):
                s, c = dict(survivor), dict(challenger)
                if change == "progress":
                    s["progressAfter"] = s["progressBefore"]
                elif change == "oom":
                    c["overCapRejected"] = False
                elif change == "recovery":
                    c["recoverySucceeded"] = False
                else:
                    c["namespacePid"] = s["namespacePid"]
                with self.assertRaises(ValueError):
                    probe.build_workload_receipt("run", "pod-uid", plan, s, c)

    def test_receipt_file_is_private_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence" / "receipt.json"
            probe.write_private(output, {"probeSucceeded": True})
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                probe.write_private(output, {"probeSucceeded": False})

    def test_live_runner_stops_at_mps_preflight_without_starting_children(self):
        plan = probe.validate_plan(500, 300, 300, 50)
        with patch.dict(os.environ, {"CUDA_MPS_PIPE_DIRECTORY": ""}):
            with self.assertRaisesRegex(RuntimeError, "MPS pipe directory"):
                probe.run_probe("run-01", "pod-uid", plan, timeout=1,
                                peer_hold_seconds=0)


if __name__ == "__main__":
    unittest.main()
