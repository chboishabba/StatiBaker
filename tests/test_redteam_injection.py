import json
import os
import tempfile
from pathlib import Path
import unittest

from adapters.wazuh_lifecycle import convert_events
from adapters import prometheus_summary
from sb import query
from sb.bundle import write_manifest, verify_manifest


class TestRedTeamInjection(unittest.TestCase):
    def test_rce_payload_is_inert(self):
        marker = os.path.join(tempfile.gettempdir(), "sb_redteam_marker")
        if os.path.exists(marker):
            os.remove(marker)

        payload = {
            "timestamp": "2026-02-05T12:04:01Z",
            "agent": {"name": "host-01"},
            "rule": {"description": f"Network down $(touch {marker})", "groups": ["network"]},
        }
        records = convert_events([json.dumps(payload)])
        self.assertTrue(records)
        self.assertFalse(os.path.exists(marker))

    def test_query_does_not_leak_env(self):
        os.environ["SB_SECRET"] = "topsecret"
        state = {"sources": []}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as state_f:
            json.dump(state, state_f)
            state_f.flush()
            payload = query.provenance(state_f.name)
        self.assertNotIn("SB_SECRET", json.dumps(payload))

    def test_query_refuses_path_escape(self):
        with tempfile.TemporaryDirectory() as base_dir, \
            tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as state_f:
            json.dump({"carryover_threads": []}, state_f)
            state_f.flush()
            with self.assertRaises(ValueError):
                query.carryover_summary(state_f.name, base_dir=base_dir)

    def test_metric_smuggling_rejects_labels(self):
        values = [1.0, 2.0]
        record = prometheus_summary._build_record("cpu", "s", "e", values)
        self.assertEqual(set(record.keys()), {"t_start", "t_end", "signal", "metric", "summary"})

    def test_manifest_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            state_path = bundle / "state.json"
            drift_path = bundle / "drift.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                handle.write("{}")
            with open(drift_path, "w", encoding="utf-8") as handle:
                handle.write("{}")
            files = ["state.json", "drift.json"]
            write_manifest(bundle, files, sb_version="test")
            # tamper
            with open(state_path, "w", encoding="utf-8") as handle:
                handle.write("{\"tampered\": true}")
            errors = verify_manifest(bundle)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
