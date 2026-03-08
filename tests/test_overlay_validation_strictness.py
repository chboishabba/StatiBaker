from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb.itir_ingest import validate_overlay  # noqa: E402


def test_fuzzymodo_overlay_rejects_missing_selector_hash() -> None:
    record = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:fuzzymodo:evt-1",
        "provenance": {"source": "fuzzymodo"},
        "state_date": "2026-03-09",
        "observer_kind": "fuzzymodo_selector_v1",
        "selector_refs": [{"matched": 1}],
    }
    errs = validate_overlay(record)
    assert any("selector_hash required" in e for e in errs)


def test_casey_overlay_rejects_missing_ws_id() -> None:
    record = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:casey:evt-1",
        "provenance": {"source": "casey-git-clone"},
        "state_date": "2026-03-09",
        "observer_kind": "casey_workspace_v1",
        "workspace_refs": [{"head_tree_id": "tree-1"}],
        "operation_refs": [],
        "build_refs": [],
    }
    errs = validate_overlay(record)
    assert any("ws_id required" in e for e in errs)


def test_casey_overlay_rejects_missing_build_ref_fields() -> None:
    record = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:casey:evt-1",
        "provenance": {"source": "casey-git-clone"},
        "state_date": "2026-03-09",
        "observer_kind": "casey_workspace_v1",
        "workspace_refs": [{"ws_id": "ws-1"}],
        "operation_refs": [],
        "build_refs": [{"build_id": "build-1"}],
    }
    errs = validate_overlay(record)
    assert any("tree_id required" in e for e in errs)
    assert any("selection_digest required" in e for e in errs)
