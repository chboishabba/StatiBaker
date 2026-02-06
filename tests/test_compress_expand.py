import unittest

from sb.compress import collapse_low_signal_events, expand_low_signal_events


class TestCompressionExpand(unittest.TestCase):
    def test_expand_roundtrip(self):
        events = [
            {"id": "e1", "source": "sys", "type": "noise", "text": "ping", "low_signal": True},
            {"id": "e2", "source": "sys", "type": "noise", "text": "ping", "low_signal": True},
            {"id": "e3", "source": "sys", "type": "noise", "text": "pong", "low_signal": True},
            {"id": "e4", "source": "git", "type": "commit", "text": "c1"},
        ]
        compressed, _ = collapse_low_signal_events(events)
        expanded = expand_low_signal_events(compressed)
        self.assertEqual(4, len(expanded))
        self.assertEqual(["e1", "e2", "e3", "e4"], [e["id"] for e in expanded])
        self.assertEqual(["ping", "ping", "pong", "c1"], [e["text"] for e in expanded])


if __name__ == "__main__":
    unittest.main()
