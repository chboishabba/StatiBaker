from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb.dashboard_store_sqlite import load_itir_overlay_records  # noqa: E402
from sb.itir_ingest import persist_overlays, validate_overlay  # noqa: E402


def test_casey_overlay_accepts_reference_only_payload() -> None:
    record = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:casey:evt-1",
        "provenance": {"source": "casey-git-clone", "collected_at": "2026-03-09T00:00:00Z"},
        "state_date": "2026-03-09",
        "observer_kind": "casey_workspace_v1",
        "workspace_refs": [
            {
                "ws_id": "ws-1",
                "head_tree_id": "tree-1",
                "selected_path_count": 3,
                "policy_tie_break": "stable_hash",
                "policy_prefer_author": "alice",
            }
        ],
        "operation_refs": [
            {
                "operation_kind": "collapse",
                "path": "src/main.c",
                "tree_id_before": "tree-1",
                "tree_id_after": "tree-2",
                "chosen_fv_id": "fv-a",
                "resolved_fv_id": "fv-b",
                "receipt_hash": "a" * 64,
                "created_at": "2026-03-09T00:00:00Z",
            }
        ],
        "build_refs": [
            {
                "build_id": "build-1",
                "tree_id": "tree-2",
                "selection_digest": "b" * 64,
                "created_at": "2026-03-09T00:00:00Z",
            }
        ],
    }

    assert validate_overlay(record) == []


def test_casey_overlay_persists_extension_tables() -> None:
    record = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:casey:evt-1",
        "provenance": {"source": "casey-git-clone", "collected_at": "2026-03-09T00:00:00Z"},
        "state_date": "2026-03-09",
        "observer_kind": "casey_workspace_v1",
        "workspace_refs": [
            {
                "ws_id": "ws-1",
                "head_tree_id": "tree-1",
                "selected_path_count": 3,
                "policy_tie_break": "stable_hash",
                "policy_prefer_author": "alice",
            }
        ],
        "operation_refs": [],
        "build_refs": [],
    }

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dashboard.sqlite"
        persist_overlays(db_path=db_path, records=[record])
        loaded = load_itir_overlay_records(db_path=db_path)

    assert len(loaded) == 1
    row = loaded[0]
    assert row["observer_kind"] == "casey_workspace_v1"
    assert row["workspace_refs"][0]["ws_id"] == "ws-1"
