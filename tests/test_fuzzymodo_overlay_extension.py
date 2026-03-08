from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb.dashboard_store_sqlite import load_itir_overlay_records  # noqa: E402
from sb.itir_ingest import persist_overlays, validate_overlay  # noqa: E402


def test_fuzzymodo_overlay_accepts_reference_only_payload() -> None:
    record = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:fuzzymodo:evt-1",
        "provenance": {"source": "fuzzymodo", "collected_at": "2026-03-09T00:00:00Z"},
        "state_date": "2026-03-09",
        "observer_kind": "fuzzymodo_selector_v1",
        "status": "linked",
        "confidence": "medium",
        "selector_refs": [
            {
                "selector_hash": "deadbeef" * 8,
                "decision_state": "buffered",
                "matched": 1,
                "policy_hash": "cafebabe" * 8,
                "replay_key": "replay:xyz",
                "created_at": "2026-03-09T00:00:00Z",
            }
        ],
        "reason_codes": [
            {"reason_code": "invalid_regex", "detail": "where.structural.function.name.matches"}
        ],
        "artifact_refs": [
            {
                "artifact_kind": "decision_ledger_ref",
                "artifact_locator": "fuzzymodo_decision_ledger:dec-1",
                "artifact_hash": None,
            }
        ],
    }

    assert validate_overlay(record) == []


def test_fuzzymodo_overlay_persists_extension_tables() -> None:
    record = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:fuzzymodo:evt-1",
        "provenance": {"source": "fuzzymodo", "collected_at": "2026-03-09T00:00:00Z"},
        "state_date": "2026-03-09",
        "observer_kind": "fuzzymodo_selector_v1",
        "selector_refs": [
            {
                "selector_hash": "deadbeef" * 8,
                "decision_state": "approved",
                "matched": 0,
                "policy_hash": None,
                "replay_key": None,
                "created_at": "2026-03-09T00:00:00Z",
            }
        ],
        "reason_codes": [{"reason_code": "policy_gate", "detail": "requires_human"}],
        "artifact_refs": [
            {
                "artifact_kind": "replay_artifact",
                "artifact_locator": "s3://example-bucket/replay.json",
                "artifact_hash": "a" * 64,
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dashboard.sqlite"
        persist_overlays(db_path=db_path, records=[record])
        loaded = load_itir_overlay_records(db_path=db_path)

    assert len(loaded) == 1
    row = loaded[0]
    assert row["observer_kind"] == "fuzzymodo_selector_v1"
    assert row["selector_refs"][0]["selector_hash"] == "deadbeef" * 8
    assert row["reason_codes"][0]["reason_code"] == "policy_gate"
    assert row["artifact_refs"][0]["artifact_kind"] == "replay_artifact"
