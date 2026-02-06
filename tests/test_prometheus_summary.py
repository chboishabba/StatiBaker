import unittest

from adapters import prometheus_summary


class TestPrometheusSummary(unittest.TestCase):
    def test_summarize_deterministic(self):
        values = [0.1, 0.2, 0.3, 0.4]
        summary = prometheus_summary._summarize(values)
        self.assertAlmostEqual(0.25, summary["mean"], places=6)
        self.assertEqual(0.3, summary["p95"])
        self.assertEqual(4, summary["samples"])

    def test_percentile_empty(self):
        self.assertEqual(0.0, prometheus_summary._percentile([], 0.95))


if __name__ == "__main__":
    unittest.main()
