import unittest
from datetime import UTC, datetime

from adapters import pr_events_github


class TestPrEventsGithubAdapter(unittest.TestCase):
    def test_parse_github_repo_from_url(self):
        self.assertEqual(
            "owner/repo",
            pr_events_github.parse_github_repo_from_url("git@github.com:owner/repo.git"),
        )
        self.assertEqual(
            "owner/repo",
            pr_events_github.parse_github_repo_from_url("https://github.com/owner/repo"),
        )
        self.assertIsNone(
            pr_events_github.parse_github_repo_from_url("https://example.com/owner/repo")
        )

    def test_build_events(self):
        start = datetime(2026, 2, 8, 0, 0, tzinfo=UTC)
        end = datetime(2026, 2, 9, 0, 0, tzinfo=UTC)
        collected_at = datetime(2026, 2, 8, 7, 0, tzinfo=UTC)
        pulls = [
            {
                "number": 10,
                "state": "closed",
                "created_at": "2026-02-08T01:00:00Z",
                "merged_at": "2026-02-08T02:00:00Z",
                "closed_at": "2026-02-08T02:00:00Z",
                "user": {"login": "alice"},
            },
            {
                "number": 11,
                "state": "closed",
                "created_at": "2026-02-07T01:00:00Z",
                "merged_at": None,
                "closed_at": "2026-02-08T03:00:00Z",
                "user": {"login": "bob"},
            },
        ]
        comments = [
            {
                "created_at": "2026-02-08T04:00:00Z",
                "pull_request_url": "https://api.github.com/repos/owner/repo/pulls/10",
                "user": {"login": "carol"},
            },
            {
                "created_at": "2026-02-07T04:00:00Z",
                "pull_request_url": "https://api.github.com/repos/owner/repo/pulls/10",
                "user": {"login": "carol"},
            },
        ]
        events = pr_events_github.build_events(
            repo="owner/repo",
            start=start,
            end=end,
            pulls=pulls,
            comments=comments,
            collected_at=collected_at,
        )
        event_types = [row["event_type"] for row in events]
        self.assertIn("pr_received", event_types)
        self.assertIn("pr_merged", event_types)
        self.assertIn("pr_closed", event_types)
        self.assertIn("pr_commented", event_types)
        self.assertEqual(
            1, len([row for row in events if row["event_type"] == "pr_commented"])
        )


if __name__ == "__main__":
    unittest.main()

