import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("collector", HERE / "collect_host_attribution.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class HostAttributionParsingTests(unittest.TestCase):
    def test_mps_pids_reject_duplicates_and_non_pids(self):
        self.assertEqual(collector.parse_pids("12\n34\n"), [12, 34])
        for value in ("12 12", "0", "12x", "12 server"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                collector.parse_pids(value)

    def test_compute_apps_preserve_pid_to_gpu_mapping(self):
        self.assertEqual(collector.parse_compute_apps(
            "12, GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa\n"
            "12, GPU-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb\n"
            "34, GPU-cccccccc-cccc-cccc-cccc-cccccccccccc\n"),
            {12: ["GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                  "GPU-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
             34: ["GPU-cccccccc-cccc-cccc-cccc-cccccccccccc"]})
        with self.assertRaises(ValueError):
            collector.parse_compute_apps("12, not-a-uuid\n")

    def test_mps_clients_may_be_absent_from_nvidia_smi_rows(self):
        collector.validate_compute_app_coverage([12], {12: ["GPU-a"]})
        with self.assertRaisesRegex(ValueError, "server PIDs absent"):
            collector.validate_compute_app_coverage([12], {})

    def test_proc_start_ticks_handles_spaces_in_command(self):
        fields = "S 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 98765 21"
        self.assertEqual(collector.proc_start_ticks(f"42 (worker (cuda)) {fields}", 42), 98765)
        with self.assertRaises(ValueError):
            collector.proc_start_ticks("43 (other) S 1 2", 42)

    def test_status_requires_all_identity_fields(self):
        parsed = collector.parse_status("Uid:\t1000 1000 1000 1000\nGid:\t100 100 100 100\nNSpid:\t222 1\n")
        self.assertEqual(parsed["Uid"], [1000] * 4)
        self.assertEqual(parsed["NSpid"], [222, 1])
        with self.assertRaises(ValueError):
            collector.parse_status("Uid:\t1000\nGid:\t100\n")

    def test_run_id_is_safe_for_evidence_filename(self):
        self.assertEqual(collector.safe_name("run-20261028_01"), "run-20261028_01")
        for value in ("../escape", "", "has space"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                collector.safe_name(value)


if __name__ == "__main__":
    unittest.main()
