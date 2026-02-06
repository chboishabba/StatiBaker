import json
import unittest

from adapters.wazuh_lifecycle import convert_events


class TestWazuhLifecycleAdapter(unittest.TestCase):
    def test_convert_events_filters_and_maps(self):
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-02-05T12:04:01Z",
                    "agent": {"name": "host-01"},
                    "rule": {"description": "Network down detected", "groups": ["network"]},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-02-05T12:10:01Z",
                    "agent": {"name": "host-01"},
                    "rule": {"description": "Service restart", "groups": ["service"]},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-02-05T12:20:01Z",
                    "agent": {"name": "host-01"},
                    "rule": {"description": "Unrelated alert", "groups": ["auth"]},
                }
            ),
        ]

        records = convert_events(lines)
        self.assertEqual(2, len(records))
        self.assertEqual("network_down", records[0]["kind"])
        self.assertEqual("service_restart", records[1]["kind"])
        for record in records:
            self.assertEqual("system", record["signal"])
            self.assertEqual("wazuh_lifecycle", record["event"])
            self.assertEqual("wazuh", record["source"])
            self.assertEqual("host-01", record["agent"])

    def test_determinism_same_input_same_output(self):
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-02-05T12:04:01Z",
                    "agent": {"name": "host-01"},
                    "rule": {"description": "Network down detected", "groups": ["network"]},
                }
            )
        ]
        first = convert_events(lines)
        second = convert_events(lines)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
