from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb.corkysoft_ingest import persist_review_events, review_event_to_overlay, validate_review_event  # noqa: E402
from sb.dashboard_store_sqlite import load_itir_overlay_records  # noqa: E402
from sb.itir_ingest import validate_overlay  # noqa: E402


def _planning_snapshot_event() -> dict[str, object]:
    return {
        "event_id": "corkysoft:plan:2026-03-27",
        "event_family": "planning_snapshot",
        "event_time": "2026-03-27T08:15:00Z",
        "source_system": "corkysoft",
        "actor_ref": "planner:ops",
        "authority_class": "reviewed_summary",
        "correlation_key": "plan:day:2026-03-27",
        "summary": "Day plan reviewed with two unresolved vehicle constraints.",
        "status": "reviewed",
        "object_refs": [
            {"job_id": "JOB-1001"},
            {"segment_id": "SEG-2001"},
        ],
        "provenance_refs": [
            {"ref_kind": "ui_route", "ref_uri": "/planner?date=2026-03-27"},
        ],
        "evidence_refs": [
            {"event_id": "observer-1", "source_id": "corkysoft-ui", "ref_kind": "planner_snapshot"},
        ],
        "payload": {
            "window": "day",
            "exception_count": 2,
        },
    }


def test_validate_review_event_accepts_reference_heavy_payload() -> None:
    assert validate_review_event(_planning_snapshot_event()) == []


def test_review_event_to_overlay_produces_persistable_overlay() -> None:
    overlay = review_event_to_overlay(_planning_snapshot_event())
    assert overlay["observer_kind"] == "corkysoft_review_event_v1"
    assert overlay["annotation_id"] == "obs:corkysoft:corkysoft:plan:2026-03-27"
    assert overlay["state_date"] == "2026-03-27"
    assert validate_overlay(overlay) == []


def test_persist_review_events_round_trips_corkysoft_fields() -> None:
    event = _planning_snapshot_event()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dashboard.sqlite"
        result = persist_review_events(db_path=db_path, records=[event])
        assert result["accepted_count"] == 1
        rows = load_itir_overlay_records(db_path=db_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["observer_kind"] == "corkysoft_review_event_v1"
    assert row["event_family"] == "planning_snapshot"
    assert row["authority_class"] == "reviewed_summary"
    assert row["object_refs"][0]["job_id"] == "JOB-1001"
    assert row["provenance_refs"][0]["ref_kind"] == "ui_route"
    assert row["payload"]["exception_count"] == 2


def test_validate_review_event_rejects_unknown_family() -> None:
    event = _planning_snapshot_event()
    event["event_family"] = "mystery_family"
    errors = validate_review_event(event)
    assert any("unsupported event_family" in error for error in errors)
