import json
import tempfile
import unittest
from pathlib import Path

from sb.bundle import write_manifest, verify_manifest
from sb.drift import compute_drift


class TestBundle(unittest.TestCase):
    def test_manifest_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            (bundle / "state.json").write_text("{}", encoding="utf-8")
            (bundle / "drift.json").write_text("{}", encoding="utf-8")
            files = ["state.json", "drift.json"]
            write_manifest(bundle, files, sb_version="test")
            errors = verify_manifest(bundle)
            self.assertEqual([], errors)

    def test_verify_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            state = {"events": [], "carryover_age_days": {}}
            drift = compute_drift(state)
            (bundle / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (bundle / "drift.json").write_text(json.dumps(drift), encoding="utf-8")
            files = ["state.json", "drift.json"]
            write_manifest(bundle, files, sb_version="test")
            errors = verify_manifest(bundle)
            self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
