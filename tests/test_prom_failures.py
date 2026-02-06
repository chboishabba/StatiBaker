import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestPromFailures(unittest.TestCase):
    def test_prom_failure_sets_label(self):
        root = Path("/home/c/Documents/code/ITIR-suite/StatiBaker")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        date = "2026-02-12"
        subprocess.check_call(
            [
                "bash",
                str(root / "scripts" / "run_day.sh"),
                date,
                str(root),
                "",
                "",
                "http://127.0.0.1:9999",
            ],
            env=env,
        )
        state_path = root / "runs" / date / "outputs" / "state.json"
        state = state_path.read_text(encoding="utf-8")
        self.assertIn("prometheus_missing", state)


if __name__ == "__main__":
    unittest.main()
