from __future__ import annotations

from typing import Any, Iterable

SERVICE_CHANGE_STATES = {
    "proposed",
    "implemented",
    "verified",
    "validated",
    "released",
    "observed",
    "incident",
    "rolled_back",
}
EVIDENCE_STATES = {
    "source_written",
    "compile_checked",
    "fixture_checked",
    "runtime_observed",
    "production_observed",
}


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _refs(values: Iterable[Any]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def build_governance_evidence_projection(
    *,
    subject_ref: str,
    execution_refs: Iterable[Any],
    service_change_state: str,
    evidence_state: str,
    incident_refs: Iterable[Any],
    problem_refs: Iterable[Any],
    change_refs: Iterable[Any],
    release_refs: Iterable[Any],
    provenance_refs: Iterable[Any],
    validation_receipt_refs: Iterable[Any] = (),
    external_sync_status: str | None = None,
    canonical_local_state_unchanged: bool = True,
) -> dict[str, Any]:
    subject = _text(subject_ref, "subject_ref")
    executions = _refs(execution_refs)
    provenance = _refs(provenance_refs)
    if not executions or not provenance:
        raise ValueError("execution_refs and provenance_refs are required")
    requested_service_state = _text(service_change_state, "service_change_state")
    evidence = _text(evidence_state, "evidence_state")
    if requested_service_state not in SERVICE_CHANGE_STATES:
        raise ValueError(f"unsupported service_change_state: {requested_service_state}")
    if evidence not in EVIDENCE_STATES:
        raise ValueError(f"unsupported evidence_state: {evidence}")

    validations = _refs(validation_receipt_refs)
    promotion_blocked = requested_service_state == "validated" and not validations
    effective_service_state = "implemented" if promotion_blocked else requested_service_state

    return {
        "schema_version": "statibaker.gov1.execution_evidence.v0_1",
        "subject_ref": subject,
        "execution_refs": executions,
        "service_change_state": effective_service_state,
        "requested_service_change_state": requested_service_state,
        "evidence_state": evidence,
        "incident_refs": _refs(incident_refs),
        "problem_refs": _refs(problem_refs),
        "change_refs": _refs(change_refs),
        "release_refs": _refs(release_refs),
        "validation_receipt_refs": validations,
        "provenance_refs": provenance,
        "external_sync_status": str(external_sync_status or "unknown"),
        "canonical_local_state_unchanged": bool(canonical_local_state_unchanged),
        "validation_promotion_blocked": promotion_blocked,
        "validated": effective_service_state == "validated" and bool(validations),
        "external_sync_failure_changes_semantic_truth": False,
        "creates_compliance_authority": False,
        "creates_semantic_authority": False,
        "creates_user_priority": False,
    }


__all__ = [
    "SERVICE_CHANGE_STATES",
    "EVIDENCE_STATES",
    "build_governance_evidence_projection",
]
