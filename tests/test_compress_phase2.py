import unittest

from sb.compress import collapse_low_signal_events


class TestPhase2Compression(unittest.TestCase):
    def test_collapse_low_signal_events(self):
        events = [
            {"id": "e1", "source": "sys", "type": "noise", "text": "ping", "low_signal": True},
            {"id": "e2", "source": "sys", "type": "noise", "text": "ping", "low_signal": True},
            {"id": "e3", "source": "sys", "type": "noise", "text": "pong", "low_signal": True},
            {"id": "e4", "source": "git", "type": "commit", "text": "c1"},
        ]
        compressed, loss_profiles = collapse_low_signal_events(events)
        self.assertEqual(3, len(compressed))
        self.assertEqual(2, compressed[0]["collapsed_count"])
        self.assertEqual(["e1", "e2"], compressed[0]["collapsed_ids"])
        self.assertEqual("pong", compressed[1]["text"])
        self.assertEqual(1, compressed[1]["collapsed_count"])
        self.assertTrue(loss_profiles)

    def test_no_low_signal_changes(self):
        events = [{"id": "e1", "source": "git", "type": "commit", "text": "c1"}]
        compressed, loss_profiles = collapse_low_signal_events(events)
        self.assertEqual(events, compressed)
        self.assertEqual([], loss_profiles)


if __name__ == "__main__":
    unittest.main()
