from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JoinedOverlay:
    """Overlay record enriched with optional, read-only ledger lookups."""

    overlay: dict[str, Any]
    fuzzymodo_decisions: dict[str, Any] | None = None
    casey_operation: dict[str, Any] | None = None
    casey_build: dict[str, Any] | None = None


def _index_artifacts_by_kind(artifact_refs: object) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(artifact_refs, list):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for item in artifact_refs:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("artifact_kind") or "").strip()
        if not kind:
            continue
        out.setdefault(kind, []).append(item)
    return out


def join_overlay_ledgers(
    *,
    overlay: dict[str, Any],
    fuzzymodo_ledger_db_path: Path | None = None,
    casey_ledger_db_path: Path | None = None,
) -> JoinedOverlay:
    """Join overlay refs to external ledgers.

    This is read-only enrichment. If ledger DB paths are not provided (or refs are
    absent), the joined fields remain None.
    """

    kind = str(overlay.get("observer_kind") or "").strip()
    artifacts = _index_artifacts_by_kind(overlay.get("artifact_refs"))

    fuzz_decision: dict[str, Any] | None = None
    if kind in {"fuzzymodo_selector_v1", "fuzzymodo_codex_trace_v1"} and fuzzymodo_ledger_db_path is not None:
        # Artifact locators are emitted as: "fuzzymodo_decision_ledger:<decision_id>"
        decision_refs = artifacts.get("decision_ledger_ref", [])
        decision_id = None
        for ref in decision_refs:
            locator = str(ref.get("artifact_locator") or "")
            if locator.startswith("fuzzymodo_decision_ledger:"):
                decision_id = locator.split(":", 1)[1]
                break
        if decision_id:
            from selector_dsl.decision_ledger_sqlite import load_decision  # local import

            fuzz_decision = load_decision(db_path=fuzzymodo_ledger_db_path, decision_id=decision_id)

    casey_op: dict[str, Any] | None = None
    casey_build: dict[str, Any] | None = None
    if kind == "casey_workspace_v1" and casey_ledger_db_path is not None:
        # Locators are stored on refs (Path 1) as:
        # - operation_refs[].operation_ledger_locator == "casey_operation_ledger:<id>"
        # - build_refs[].build_ledger_locator == "casey_build_ledger:<id>"
        op_id = None
        for op in overlay.get("operation_refs") if isinstance(overlay.get("operation_refs"), list) else []:
            if not isinstance(op, dict):
                continue
            locator = str(op.get("operation_ledger_locator") or "")
            if locator.startswith("casey_operation_ledger:"):
                op_id = locator.split(":", 1)[1]
                break
        build_id = None
        for b in overlay.get("build_refs") if isinstance(overlay.get("build_refs"), list) else []:
            if not isinstance(b, dict):
                continue
            locator = str(b.get("build_ledger_locator") or "")
            if locator.startswith("casey_build_ledger:"):
                build_id = locator.split(":", 1)[1]
                break

        if op_id:
            from casey_git_clone.ledger_sqlite import load_operation  # local import

            casey_op = load_operation(db_path=casey_ledger_db_path, operation_id=op_id)
        if build_id:
            from casey_git_clone.ledger_sqlite import load_build  # local import

            casey_build = load_build(db_path=casey_ledger_db_path, build_id=build_id)

    return JoinedOverlay(
        overlay=dict(overlay),
        fuzzymodo_decisions=fuzz_decision,
        casey_operation=casey_op,
        casey_build=casey_build,
    )
