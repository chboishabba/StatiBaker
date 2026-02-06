import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestInactivityRuns(unittest.TestCase):
    def test_run_day_with_empty_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir(parents=True)
            subprocess.check_call(["git", "init"], cwd=repo)
            run_dir = Path("/home/c/Documents/code/ITIR-suite/StatiBaker")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(run_dir)
            subprocess.check_call(
                ["bash", str(run_dir / "scripts" / "run_day.sh"), "2026-02-10", str(repo)],
                env=env,
            )
            state_path = run_dir / "runs" / "2026-02-10" / "outputs" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual([], state.get("events", []))


if __name__ == "__main__":
    unittest.main()
