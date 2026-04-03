import unittest

from sb.drift import compute_drift


class TestDriftSignals(unittest.TestCase):
    def test_empty_state(self):
        drift = compute_drift({"events": [], "carryover_age_days": {}})
        self.assertEqual(0, drift["counters"]["stale_carryover_threads"])
        self.assertEqual(0, drift["counters"]["low_signal_events"])
        self.assertEqual([], drift["flags"])
        self.assertEqual(0.0, drift["counters"]["dominant_thread_fraction"])
        self.assertIsNone(drift["counters"]["dominant_thread_id"])

    def test_high_activity_low_diversity_flag(self):
        events = [{"source": "git", "type": "commit", "text": "c"}] * 25
        drift = compute_drift({"events": events, "carryover_age_days": {}})
        self.assertIn("high_activity_low_diversity", drift["flags"])

    def test_context_dominance_flag(self):
        events = [{"thread_id": "st", "source": "git", "type": "commit"} for _ in range(10)]
        drift = compute_drift({"events": events, "carryover_age_days": {}})
        self.assertIn("context_dominance", drift["flags"])
        self.assertEqual(1.0, drift["counters"]["dominant_thread_fraction"])
        self.assertEqual("st", drift["counters"]["dominant_thread_id"])


if __name__ == "__main__":
    unittest.main()
