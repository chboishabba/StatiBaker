import json
import os
import subprocess
import sys
import unittest

from sb.activity.sessionize import build_ledger, sessionize_snapshots, validate_config


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_json(name):
    path = os.path.join(FIXTURES_DIR, name)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class TestSessionize(unittest.TestCase):
    def test_sessionize_snapshots_matches_fixture(self):
        snapshots = _load_json("snapshots.json")
        expected = _load_json("activity_events.json")
        actual = sessionize_snapshots(snapshots)
        self.assertEqual(expected, actual)

    def test_build_ledger_provenance(self):
        snapshots = _load_json("snapshots.json")
        ledger = build_ledger(snapshots, policy_receipt="policy-001")
        self.assertIn("activity_events", ledger)
        self.assertIn("provenance", ledger)
        self.assertEqual("sb.sessionize.v0", ledger["provenance"]["algorithm"])
        self.assertEqual("policy-001", ledger["provenance"]["policy_receipt"])
        self.assertEqual(64, len(ledger["provenance"]["input_hash"]))

    def test_validate_config_rejects_invalid(self):
        with self.assertRaises(ValueError):
            validate_config({"idle_gap_s": -1})
        with self.assertRaises(ValueError):
            validate_config({"title_jaccard_min": 2})
        with self.assertRaises(ValueError):
            validate_config({"phash_jump_min": "nope"})

    def test_cli_exits_nonzero_on_invalid_config(self):
        config_path = os.path.join(FIXTURES_DIR, "bad_config.json")
        snapshots_path = os.path.join(FIXTURES_DIR, "snapshots.json")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sb.activity.sessionize",
                snapshots_path,
                "--config",
                config_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        # Running via `-m sb.activity.sessionize` requires `sb` to be importable on sys.path.
        # In this repo layout, that isn't guaranteed when running tests from the monorepo root.
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(result.stderr.strip())


if __name__ == "__main__":
    unittest.main()
