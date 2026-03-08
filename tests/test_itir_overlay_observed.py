from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb.dashboard_store_sqlite import load_itir_overlay_records
from sb.itir_ingest import persist_overlays, validate_overlay


def test_itir_overlay_accepts_observed_annotation():
    record = {
        "activity_event_id": "signal-abc123",
        "annotation_id": "obs:browser_usage",
        "provenance": {"source": "itir", "collected_at": "2026-02-06T10:00:00Z"},
        "state_date": "2026-02-06",
    }
    assert validate_overlay(record) == []


def test_itir_overlay_accepts_reference_heavy_mission_observer_overlay():
    record = {
        "activity_event_id": "msg-123",
        "annotation_id": "obs:mission:msg-123",
        "provenance": {"source": "SensibLaw", "run_id": "transcript-semantic-demo-v1"},
        "sb_state_id": "itir:mission:transcript-semantic-demo-v1",
        "observer_kind": "itir_mission_graph_v1",
        "status": "linked",
        "confidence": "medium",
        "mission_refs": [
            {
                "mission_id": "mission:demo_chat_1:notification_routing_feature",
                "node_kind": "task",
                "topic_label": "notification routing feature",
                "ref_type": "followup_resolution",
            }
        ],
        "evidence_refs": [
            {
                "event_id": "msg-123",
                "source_id": "demo-chat-1",
                "ref_kind": "followup_message",
            }
        ],
    }
    assert validate_overlay(record) == []


def test_itir_overlay_persists_to_db_backed_store():
    record = {
        "activity_event_id": "msg-123",
        "annotation_id": "obs:mission:msg-123",
        "provenance": {"source": "SensibLaw", "run_id": "transcript-semantic-demo-v1"},
        "sb_state_id": "itir:mission:transcript-semantic-demo-v1",
        "observer_kind": "itir_mission_graph_v1",
        "status": "linked",
        "confidence": "medium",
        "mission_refs": [
            {
                "mission_id": "mission:demo_chat_1:notification_routing_feature",
                "node_kind": "task",
                "topic_label": "notification routing feature",
                "ref_type": "followup_resolution",
            }
        ],
        "evidence_refs": [
            {
                "event_id": "msg-123",
                "source_id": "demo-chat-1",
                "ref_kind": "followup_message",
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dashboard.sqlite"
        result = persist_overlays(db_path=db_path, records=[record])
        assert result["accepted_count"] == 1
        loaded = load_itir_overlay_records(db_path=db_path)
        assert len(loaded) == 1
        assert loaded[0]["annotation_id"] == "obs:mission:msg-123"
        assert loaded[0]["mission_refs"][0]["mission_id"] == "mission:demo_chat_1:notification_routing_feature"
