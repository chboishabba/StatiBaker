import unittest

from sb.drift import compute_drift


class TestTimeHygiene(unittest.TestCase):
    def test_stale_carryover_threshold(self):
        state = {"events": [], "carryover_age_days": {"a": 7, "b": 3}}
        drift = compute_drift(state)
        self.assertEqual(1, drift["counters"]["stale_carryover_threads"])


if __name__ == "__main__":
    unittest.main()
