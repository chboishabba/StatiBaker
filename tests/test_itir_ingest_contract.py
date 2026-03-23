import unittest

from adapters.jmd_runtime import receipt_to_overlay_record
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

    def test_mission_overlay_requires_reference_fields(self):
        record = {
            "activity_event_id": "ae-123",
            "annotation_id": "obs:mission:ann-1",
            "provenance": {"actor": "user"},
            "sb_state_id": "itir:mission:test",
            "observer_kind": "itir_mission_graph_v1",
        }
        errors = validate_overlay(record)
        self.assertTrue(any("mission_refs" in error for error in errors))
        self.assertTrue(any("evidence_refs" in error for error in errors))

    def test_jmd_runtime_overlay_requires_reference_fields(self):
        receipt = {
            "receipt_id": "jmd-receipt:1234",
            "provider_kind": "pastebin",
            "provider_name": "kant-zk-pastebin",
            "object_refs": [{"object_id": "jmd:erdfa:shard:note-0001", "locator": "https://pastebin.xware.online/raw/note-0001"}],
            "graph_refs": [{"graph_id": "jmd-graph:1234", "source_object_id": "jmd:erdfa:shard:note-0001"}],
        }
        overlay = receipt_to_overlay_record(
            receipt=receipt,
            activity_event_id="ae-123",
            annotation_id="obs:jmd:ann-1",
            state_date="2026-03-22",
            provenance={"actor": "user"},
        )
        self.assertEqual([], validate_overlay(overlay))

    def test_jmd_runtime_overlay_rejects_embedded_payloads(self):
        record = {
            "activity_event_id": "ae-123",
            "annotation_id": "obs:jmd:ann-1",
            "provenance": {"actor": "user"},
            "state_date": "2026-03-22",
            "observer_kind": "jmd_runtime_v1",
            "receipt_refs": [{"receipt_id": "jmd-receipt:1234"}],
            "object": {"object_id": "jmd:erdfa:shard:note-0001"},
        }
        errors = validate_overlay(record)
        self.assertTrue(any("reference-heavy" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
