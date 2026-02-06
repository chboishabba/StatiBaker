import copy
import unittest

from sb.fold import apply_minimal_fold


class TestFoldGuardrails(unittest.TestCase):
    def test_fold_only_mutates_carryover_fields(self):
        prev_state = {
            "carryover_threads": ["alpha"],
            "carryover_age_days": {"alpha": 1},
        }
        curr_state = {
            "date": "2026-02-06",
            "events": [{"id": "e1", "text": "raw event"}],
            "artifacts": {"ocr_text": "SHOULD NOT CHANGE"},
            "notes": ["keep me"],
            "carryover_threads": ["alpha", "beta"],
        }
        before = copy.deepcopy(curr_state)

        result = apply_minimal_fold(prev_state, curr_state, "2026-02-06")

        allowed_mutations = {
            "carryover_threads",
            "carryover_new_threads",
            "carryover_resolved_threads",
            "carryover_age_days",
            "carryover_window_counts",
            "labels",
        }

        for key, value in before.items():
            if key in allowed_mutations:
                continue
            self.assertEqual(value, result.get(key), msg=f"unexpected mutation for key: {key}")

        for key in result.keys():
            if key not in before:
                self.assertIn(key, allowed_mutations, msg=f"unexpected new key: {key}")

    def test_fold_does_not_inject_summaries(self):
        prev_state = {"carryover_threads": []}
        curr_state = {
            "date": "2026-02-06",
            "events": [{"id": "e1", "text": "raw event"}],
            "artifacts": {"ocr_text": "verbatim"},
            "carryover_threads": [],
        }
        result = apply_minimal_fold(prev_state, curr_state, "2026-02-06")

        forbidden_keys = {"summary", "summaries", "tokenized", "tokens", "phrases"}
        self.assertTrue(forbidden_keys.isdisjoint(result.keys()))
        for event in result.get("events", []):
            self.assertTrue(forbidden_keys.isdisjoint(event.keys()))


if __name__ == "__main__":
    unittest.main()
