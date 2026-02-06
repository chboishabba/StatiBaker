import os
import subprocess
import unittest
from pathlib import Path


class TestBundleReplay(unittest.TestCase):
    def test_export_and_verify_bundle(self):
        root = Path("/home/c/Documents/code/ITIR-suite/StatiBaker")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)

        date = "2026-02-11"
        subprocess.check_call([
            "bash",
            str(root / "scripts" / "run_day.sh"),
            date,
        ], env=env)

        run_dir = root / "runs" / date / "outputs"
        bundle_dir = root / "runs" / date / "bundle"
        subprocess.check_call([
            str(root / "scripts" / "bundle_export.py"),
            "--run-dir",
            str(run_dir),
            "--out",
            str(bundle_dir),
            "--sb-version",
            "test",
        ], env=env)

        subprocess.check_call([
            str(root / "scripts" / "verify_bundle.py"),
            "--bundle",
            str(bundle_dir),
        ], env=env)


if __name__ == "__main__":
    unittest.main()
