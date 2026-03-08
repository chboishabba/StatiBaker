from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASEY = Path(__file__).resolve().parents[2] / "casey-git-clone" / "src"
sys.path.insert(0, str(CASEY))

from sb.dashboard_store_sqlite import load_itir_overlay_records  # noqa: E402
from sb.itir_ingest import persist_overlays  # noqa: E402
from casey_git_clone.exchange import CaseyOverlayRefs, casey_to_sb_overlay_record  # noqa: E402


def test_casey_to_sb_overlay_end_to_end_reference_only() -> None:
    refs = CaseyOverlayRefs(
        workspace_refs=[
            {
                "ws_id": "ws-1",
                "head_tree_id": "tree-1",
                "selected_path_count": 2,
                "policy_tie_break": "stable_hash",
                "policy_prefer_author": "alice",
            }
        ],
        operation_refs=[
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
        build_refs=[
            {
                "build_id": "build-1",
                "tree_id": "tree-2",
                "selection_digest": "b" * 64,
                "created_at": "2026-03-09T00:00:01Z",
            }
        ],
    )

    overlay = casey_to_sb_overlay_record(
        activity_event_id="evt-1",
        annotation_id="obs:casey:evt-1",
        state_date="2026-03-09",
        provenance={"source": "casey-git-clone", "run_id": "unit"},
        refs=refs,
    )

    assert "candidate_graph" not in overlay
    assert "workspace" not in overlay

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dashboard.sqlite"
        persist_overlays(db_path=db_path, records=[overlay])
        loaded = load_itir_overlay_records(db_path=db_path)

    assert len(loaded) == 1
    row = loaded[0]
    assert row["observer_kind"] == "casey_workspace_v1"
    assert row["workspace_refs"][0]["ws_id"] == "ws-1"
    assert row["operation_refs"][0]["operation_kind"] == "collapse"
    assert row["build_refs"][0]["build_id"] == "build-1"
