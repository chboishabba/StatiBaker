import json
import tempfile
import unittest

from sb import query


class TestQuerySurface(unittest.TestCase):
    def test_carryover_summary(self):
        state = {
            "carryover_threads": ["a"],
            "carryover_new_threads": ["b"],
            "carryover_resolved_threads": [],
            "carryover_age_days": {"a": 2},
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(state, handle)
            handle.flush()
            payload = query.carryover_summary(handle.name)
        self.assertEqual(["a"], payload["carryover_threads"])
        self.assertEqual(["b"], payload["carryover_new_threads"])

    def test_provenance(self):
        state = {"sources": [{"kind": "git", "uri": "x"}]}
        ledger = {"provenance": {"algorithm": "sb.sessionize.v0"}}
        drift = {"provenance": {"algorithm": "sb.drift.v1"}}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as state_f, \
            tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as ledger_f, \
            tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as drift_f:
            json.dump(state, state_f)
            json.dump(ledger, ledger_f)
            json.dump(drift, drift_f)
            state_f.flush()
            ledger_f.flush()
            drift_f.flush()
            payload = query.provenance(state_f.name, ledger_f.name, drift_f.name)
        self.assertEqual("sb.sessionize.v0", payload["activity_ledger"]["algorithm"])
        self.assertEqual("sb.drift.v1", payload["drift"]["algorithm"])


if __name__ == "__main__":
    unittest.main()
