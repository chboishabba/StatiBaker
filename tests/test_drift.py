import unittest

from sb.drift import compute_drift


class TestDriftSignals(unittest.TestCase):
    def test_empty_state(self):
        drift = compute_drift({"events": [], "carryover_age_days": {}})
        self.assertEqual(0, drift["counters"]["stale_carryover_threads"])
        self.assertEqual(0, drift["counters"]["low_signal_events"])
        self.assertEqual([], drift["flags"])

    def test_high_activity_low_diversity_flag(self):
        events = [{"source": "git", "type": "commit", "text": "c"}] * 25
        drift = compute_drift({"events": events, "carryover_age_days": {}})
        self.assertIn("high_activity_low_diversity", drift["flags"])


if __name__ == "__main__":
    unittest.main()
