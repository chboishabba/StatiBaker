import unittest

from sb.fold import apply_minimal_fold


class TestCarryoverSaturation(unittest.TestCase):
    def test_label_added_when_saturated(self):
        prev_state = {"carryover_threads": []}
        curr_state = {"carryover_threads": [f"t{i}" for i in range(20)]}
        result = apply_minimal_fold(prev_state, curr_state, "2026-02-05")
        self.assertIn("carryover_saturation", result.get("labels", []))


if __name__ == "__main__":
    unittest.main()
