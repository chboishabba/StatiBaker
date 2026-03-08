import unittest

from sb.itir_ingest import validate_overlay


class TestRedTeamBoundary(unittest.TestCase):
    def test_resegmentation_attempt_rejected(self):
        record = {
            "activity_event_id": "ae-1",
            "annotation_id": "ann-1",
            "provenance": {"actor": "attacker"},
            "state_date": "2026-02-05",
            "activity_events": [{"id": "ae-evil"}],
        }
        errors = validate_overlay(record)
        self.assertTrue(errors)

    def test_overlay_rejects_state_fields(self):
        record = {
            "activity_event_id": "ae-1",
            "annotation_id": "ann-1",
            "provenance": {"actor": "attacker"},
            "state_date": "2026-02-05",
            "threads": [{"id": "thread-1"}],
        }
        errors = validate_overlay(record)
        self.assertTrue(errors)

    def test_mission_overlay_rejects_thread_dump_fields(self):
        record = {
            "activity_event_id": "ae-1",
            "annotation_id": "obs:mission:1",
            "provenance": {"actor": "attacker"},
            "sb_state_id": "itir:mission:test",
            "observer_kind": "itir_mission_graph_v1",
            "mission_refs": [{"mission_id": "mission:test:feature"}],
            "evidence_refs": [{"event_id": "ae-1"}],
            "threads": [{"id": "thread-1", "messages": ["full dump"]}],
        }
        errors = validate_overlay(record)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
