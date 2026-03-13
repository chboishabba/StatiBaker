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
        self.assertEqual(
            [
                {"window_days": 7, "count": 2},
                {"window_days": 14, "count": 2},
                {"window_days": 30, "count": 2},
            ],
            actual["carryover_window_counts"],
        )
        self.assertIn("fold_policy", actual)
        self.assertEqual("sb.fold.minimal.v1", actual["fold_policy"]["policy_receipt"]["policy_id"])
        self.assertEqual("2026-02-05", actual["fold_policy"]["policy_receipt"]["applied_on"])
        self.assertEqual("", actual["fold_policy"]["policy_receipt"]["receipt_id"])
        flags = actual["fold_policy"]["mechanical_should_flags"]
        self.assertTrue(flags["preserve_carryover_continuity"])
        self.assertTrue(flags["flag_carryover_saturation"])
        self.assertEqual("sb.fold.loss_profile.v1", actual["fold_policy"]["loss_profile"]["profile_id"])

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
        self.assertEqual(
            [
                {"window_days": 7, "count": 1},
                {"window_days": 14, "count": 1},
                {"window_days": 30, "count": 1},
            ],
            actual["carryover_window_counts"],
        )

    def test_apply_minimal_fold_supports_policy_receipt_and_flags(self):
        prev_state = {
            "carryover_threads": [],
            "carryover_age_days": {},
        }
        curr_state = {"carryover_threads": [f"thread-{i}" for i in range(21)]}
        actual = apply_minimal_fold(
            prev_state,
            curr_state,
            "2026-02-06",
            policy_receipt="rcpt:fold-policy-v1",
            mechanical_should_flags={"flag_carryover_saturation": False},
        )
        self.assertEqual("rcpt:fold-policy-v1", actual["fold_policy"]["policy_receipt"]["receipt_id"])
        self.assertFalse(actual["fold_policy"]["mechanical_should_flags"]["flag_carryover_saturation"])
        self.assertNotIn("carryover_saturation", actual["labels"])

    def test_previous_date(self):
        self.assertEqual("2026-02-04", previous_date("2026-02-05"))


if __name__ == "__main__":
    unittest.main()
