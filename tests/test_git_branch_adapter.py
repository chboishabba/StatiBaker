import unittest

from adapters import git_branch


class TestGitBranchAdapter(unittest.TestCase):
    def test_parse_selector_ts(self):
        dt = git_branch._parse_selector_ts("HEAD@{2026-02-07T14:15:00+10:00}")
        self.assertIsNotNone(dt)
        self.assertEqual("2026-02-07T04:15:00+00:00", dt.isoformat())

    def test_event_type_checkout(self):
        evt, details = git_branch._event_type("checkout: moving from main to feature/x")
        self.assertEqual("branch_checkout", evt)
        self.assertEqual("main", details["from_ref"])
        self.assertEqual("feature/x", details["to_ref"])

    def test_event_type_merge(self):
        evt, details = git_branch._event_type("merge feature branch")
        self.assertEqual("branch_merge", evt)
        self.assertEqual({}, details)


if __name__ == "__main__":
    unittest.main()

