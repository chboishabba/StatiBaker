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

    def test_commitment_feed(self):
        dashboard = {
            "external_commitment_summary": {"items_total": 1},
            "external_commitments": [{"external_item_id": "task-1"}],
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(dashboard, handle)
            handle.flush()
            payload = query.commitment_feed(handle.name)
        self.assertEqual(1, payload["summary"]["items_total"])
        self.assertEqual("task-1", payload["items"][0]["external_item_id"])

    def test_completion_candidates(self):
        dashboard = {
            "task_completion_candidates": [{"candidate_id": "cand-1"}],
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(dashboard, handle)
            handle.flush()
            payload = query.completion_candidates(handle.name)
        self.assertEqual("cand-1", payload["candidates"][0]["candidate_id"])


if __name__ == "__main__":
    unittest.main()
