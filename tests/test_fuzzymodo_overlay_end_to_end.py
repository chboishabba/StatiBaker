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
