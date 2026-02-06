import unittest

from sb.itir_ingest import validate_overlay


class TestITIRIngestContract(unittest.TestCase):
    def test_valid_overlay(self):
        record = {
            "activity_event_id": "ae-123",
            "annotation_id": "ann-1",
            "provenance": {"actor": "user", "ts": "2026-02-05T00:00:00Z"},
            "state_date": "2026-02-05",
        }
        self.assertEqual([], validate_overlay(record))

    def test_missing_fields(self):
        record = {"annotation_id": "ann-1", "provenance": {"actor": "user"}}
        errors = validate_overlay(record)
        self.assertTrue(errors)

    def test_forbidden_fields(self):
        record = {
            "activity_event_id": "ae-123",
            "annotation_id": "ann-1",
            "provenance": {"actor": "user"},
            "state_date": "2026-02-05",
            "activity_events": [],
        }
        errors = validate_overlay(record)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
