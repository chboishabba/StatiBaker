import unittest

from adapters import pr_events


class TestPrEventsAdapter(unittest.TestCase):
    def test_normalize_record(self):
        raw = {
            "ts": "2026-02-08T06:12:10Z",
            "event_type": "pr_commented",
            "repo": "ITIR-suite",
            "pr_number": 42,
            "actor": "octocat",
            "state": "open",
            "collected_at": "2026-02-08T06:12:11Z",
        }
        out = pr_events.normalize_record(raw, "test_source")
        self.assertEqual("pr_event", out["signal"])
        self.assertEqual("pr_commented", out["event_type"])
        self.assertEqual(42, out["pr_number"])
        self.assertIn("actor_hash", out)
        self.assertIn("pr_key_hash", out)
        self.assertEqual("test_source", out["provenance"]["source"])

    def test_alias_event_name(self):
        raw = {
            "ts": "2026-02-08T06:12:10Z",
            "event": "merged",
            "repo": "ITIR-suite",
            "number": 7,
            "collected_at": "2026-02-08T06:12:11Z",
        }
        out = pr_events.normalize_record(raw, "test_source")
        self.assertEqual("pr_merged", out["event_type"])

    def test_reject_missing_repo(self):
        raw = {
            "ts": "2026-02-08T06:12:10Z",
            "event_type": "pr_received",
            "pr_number": 1,
            "collected_at": "2026-02-08T06:12:11Z",
        }
        with self.assertRaises(ValueError):
            pr_events.normalize_record(raw, "test_source")


if __name__ == "__main__":
    unittest.main()

