from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FUZZY = Path(__file__).resolve().parents[2] / "fuzzymodo" / "src"
sys.path.insert(0, str(FUZZY))

CASEY = Path(__file__).resolve().parents[2] / "casey-git-clone" / "src"
sys.path.insert(0, str(CASEY))

from sb.overlay_join import join_overlay_ledgers  # noqa: E402

from selector_dsl.decision_ledger_sqlite import (  # noqa: E402
    DecisionLedgerRecord,
    upsert_decision,
)

from casey_git_clone.ledger_sqlite import (  # noqa: E402
    BuildLedgerRecord,
    OperationLedgerRecord,
    upsert_build,
    upsert_operation,
)


def test_join_overlay_ledgers_fuzzymodo_decision_lookup() -> None:
    overlay = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:fuzzymodo:evt-1",
        "provenance": {"source": "unit"},
        "state_date": "2026-03-09",
        "observer_kind": "fuzzymodo_selector_v1",
        "selector_refs": [{"selector_hash": "sel:abc", "matched": 1}],
        "artifact_refs": [
            {
                "artifact_kind": "decision_ledger_ref",
                "artifact_locator": "fuzzymodo_decision_ledger:dec-1",
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "fuzzymodo.sqlite"
        upsert_decision(
            db_path=ledger,
            record=DecisionLedgerRecord(
                decision_id="dec-1",
                selector_hash="sel:abc",
                decision_state="buffered",
                matched=1,
                policy_hash=None,
                replay_key=None,
                fact_digest=None,
                created_at="2026-03-09T00:00:00Z",
                decided_by=None,
                source_tool="fuzzymodo",
            ),
            reason_codes=(),
            artifacts=(),
        )

        joined = join_overlay_ledgers(overlay=overlay, fuzzymodo_ledger_db_path=ledger)

    assert joined.fuzzymodo_decisions
    assert joined.fuzzymodo_decisions["decision_id"] == "dec-1"
    assert joined.fuzzymodo_decisions["selector_hash"] == "sel:abc"


def test_join_overlay_ledgers_casey_operation_and_build_lookup() -> None:
    overlay = {
        "activity_event_id": "evt-1",
        "annotation_id": "obs:casey:evt-1",
        "provenance": {"source": "unit"},
        "state_date": "2026-03-09",
        "observer_kind": "casey_workspace_v1",
        "operation_refs": [
            {
                "operation_kind": "collapse",
                "receipt_hash": "a" * 64,
                "operation_ledger_locator": "casey_operation_ledger:op-1",
            }
        ],
        "build_refs": [
            {
                "build_id": "build-1",
                "tree_id": "tree-2",
                "selection_digest": "b" * 64,
                "build_ledger_locator": "casey_build_ledger:build-1",
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "casey.sqlite"
        upsert_operation(
            db_path=ledger,
            record=OperationLedgerRecord(
                operation_id="op-1",
                operation_kind="collapse",
                ws_id="ws-1",
                path="src/main.c",
                tree_id_before="tree-1",
                tree_id_after="tree-2",
                chosen_fv_id="fv-a",
                resolved_fv_id="fv-b",
                actor="alice",
                created_at="2026-03-09T00:00:00Z",
                receipt_hash="a" * 64,
            ),
        )
        upsert_build(
            db_path=ledger,
            record=BuildLedgerRecord(
                build_id="build-1",
                tree_id="tree-2",
                selection_digest="b" * 64,
                created_at="2026-03-09T00:00:01Z",
                source_operation_id="op-1",
            ),
            selection_refs=[{"path": "src/main.c", "fv_id": "fv-b"}],
        )

        joined = join_overlay_ledgers(overlay=overlay, casey_ledger_db_path=ledger)

    assert joined.casey_operation
    assert joined.casey_operation["operation_id"] == "op-1"
    assert joined.casey_build
    assert joined.casey_build["build_id"] == "build-1"
