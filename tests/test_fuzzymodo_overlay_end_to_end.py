from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FUZZY = Path(__file__).resolve().parents[2] / "fuzzymodo" / "src"
sys.path.insert(0, str(FUZZY))

from sb.dashboard_store_sqlite import load_itir_overlay_records  # noqa: E402
from sb.itir_ingest import persist_overlays  # noqa: E402
from selector_dsl.exchange import (  # noqa: E402
    decision_egress_to_sb_overlay_record,
    evaluate_to_decision_egress,
)
from selector_dsl.codex_trace import emit_codex_trace_observer_artifacts  # noqa: E402


def test_fuzzymodo_to_sb_overlay_end_to_end_reference_only() -> None:
    selector = {
        "dsl_version": "0.1",
        "selector": {
            "all_of": [
                {"graph": "structural", "where": {"function.name": {"eq": "parse"}}}
            ]
        },
    }
    facts = {"structural": {"function.name": "parse"}}

    decision = evaluate_to_decision_egress(selector, facts=facts)

    overlay = decision_egress_to_sb_overlay_record(
        decision,
        activity_event_id="evt-1",
        annotation_id="obs:fuzzymodo:evt-1",
        state_date="2026-03-09",
        provenance={"source": "fuzzymodo", "run_id": "unit"},
        decision_state="buffered",
        decision_ledger_id="dec-1",
        replay_key="replay:abc",
        artifacts=[
            {
                "artifact_kind": "replay_artifact",
                "artifact_locator": "artifacts/fuzzymodo/runs/x/replay.json",
                "artifact_hash": "a" * 64,
            }
        ],
    )

    # Hard boundary: we do not transfer selector or norms into SB overlay payload.
    assert "selector" not in overlay
    assert "norm_constraints" not in overlay

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dashboard.sqlite"
        persist_overlays(db_path=db_path, records=[overlay])
        loaded = load_itir_overlay_records(db_path=db_path)

    assert len(loaded) == 1
    row = loaded[0]
    assert row["observer_kind"] == "fuzzymodo_selector_v1"
    assert row["selector_refs"][0]["selector_hash"] == decision.selector_hash

    kinds = {a["artifact_kind"] for a in row["artifact_refs"]}
    assert "decision_ledger_ref" in kinds
    assert "replay_artifact" in kinds

    # Still reference-only after persistence: no selector DSL stored.
    assert "selector" not in row
    assert "norm_constraints" not in row


def test_fuzzymodo_codex_trace_overlay_end_to_end_reference_only() -> None:
    selector = {
        "dsl_version": "0.1",
        "selector": {
            "all_of": [
                {"graph": "execution", "where": {"exec_command_count": {"gte": 1}}},
            ]
        },
    }
    facts = {
        "fact_digest": "sha256:facts",
        "graphs": {
            "tool_use": {"exec_command_count": 1},
            "outcomes": {
                "completion_candidates": [{"candidate_id": "cand-1"}],
                "open_commitments": [],
                "completed_commitments": [],
                "evidence_gaps": [],
                "unresolved_blockers": [],
            },
        },
        "outcomes": {
            "completion_candidates": [{"candidate_id": "cand-1"}],
            "open_commitments": [],
            "completed_commitments": [],
            "evidence_gaps": [],
            "unresolved_blockers": [],
        },
        "evidence_refs": [{"ref_kind": "chat_archive_message", "source_id": "codex_1"}],
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        overlay = emit_codex_trace_observer_artifacts(
            decision_ledger_db_path=tmp_path / "ledger.sqlite",
            decision_id="dec-trace-1",
            selector_payload=selector,
            facts=facts,
            activity_event_id="evt-2",
            annotation_id="obs:fuzzymodo:trace:evt-2",
            state_date="2026-03-24",
            provenance={"source": "fuzzymodo", "run_id": "unit"},
            decision_state="proposed",
            evaluation_mode="forward_state_build",
            replay_out_root=tmp_path / "runs",
        )

        persist_overlays(db_path=tmp_path / "dashboard.sqlite", records=[overlay])
        loaded = load_itir_overlay_records(db_path=tmp_path / "dashboard.sqlite")

    assert len(loaded) == 1
    row = loaded[0]
    assert row["observer_kind"] == "fuzzymodo_codex_trace_v1"
    assert row["selector_refs"][0]["selector_hash"]
    assert any(item["artifact_kind"] == "codex_trace_proposal" for item in row["artifact_refs"])
