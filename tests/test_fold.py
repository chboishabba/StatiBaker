import unittest

from sb.fold import apply_minimal_fold, previous_date


class TestFold(unittest.TestCase):
    def test_apply_minimal_fold_tracks_new_and_resolved(self):
        prev_state = {
            "carryover_threads": ["thread-a", "thread-b"],
            "carryover_age_days": {"thread-a": 2, "thread-b": 1},
        }
        curr_state = {"carryover_threads": ["thread-b", "thread-c"]}

        actual = apply_minimal_fold(prev_state, curr_state, "2026-02-05")

        self.assertEqual(["thread-b", "thread-c"], actual["carryover_threads"])
        self.assertEqual(["thread-c"], actual["carryover_new_threads"])
        self.assertEqual(["thread-a"], actual["carryover_resolved_threads"])
        self.assertEqual({"thread-b": 2, "thread-c": 0}, actual["carryover_age_days"])

    def test_apply_minimal_fold_inherits_previous_if_missing(self):
        prev_state = {
            "carryover_threads": ["thread-a"],
            "carryover_age_days": {"thread-a": 4},
        }
        curr_state = {"carryover_threads": []}

        actual = apply_minimal_fold(prev_state, curr_state, "2026-02-06")

        self.assertEqual(["thread-a"], actual["carryover_threads"])
        self.assertEqual([], actual["carryover_new_threads"])
        self.assertEqual([], actual["carryover_resolved_threads"])
        self.assertEqual({"thread-a": 5}, actual["carryover_age_days"])

    def test_previous_date(self):
        self.assertEqual("2026-02-04", previous_date("2026-02-05"))


if __name__ == "__main__":
    unittest.main()
