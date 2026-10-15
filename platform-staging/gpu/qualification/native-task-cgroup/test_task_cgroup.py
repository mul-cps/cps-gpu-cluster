"""CPU-only lifetime checks; no real tasks, cgroups, driver or CUDA calls."""
import pathlib
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).parent


class TaskCgroupTest(unittest.TestCase):
    def test_retained_lookup_lifetimes(self):
        self.assertTrue((HERE / "task_cgroup_get.c").exists(), "Retained helper absent")
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "task-cgroup-test"
            subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I" + str(HERE),
                 str(HERE / "task_cgroup_test.c"), "-o", str(binary)],
                check=True, timeout=30,
            )
            subprocess.run([str(binary)], check=True, timeout=10)

    def test_unavailable_misc_backend_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "no-misc-test"
            subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I" + str(HERE),
                 str(HERE / "no_misc_test.c"), "-o", str(binary)],
                check=True, timeout=30,
            )
            subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
