from __future__ import annotations

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "statibaker_governance_evidence.py"
_SPEC = importlib.util.spec_from_file_location("statibaker_governance_evidence", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_governance_evidence_projection = _MODULE.build_governance_evidence_projection


def test_implemented_does_not_imply_validated() -> None:
    projection = build_governance_evidence_projection(
        subject_ref="service:inv1",
        execution_refs=["run:123"],
        service_change_state="implemented",
        evidence_state="compile_checked",
        incident_refs=[],
        problem_refs=[],
        change_refs=["change:inv1"],
        release_refs=[],
        provenance_refs=["state:2026-10-03"],
    )
    assert projection["service_change_state"] == "implemented"
    assert projection["evidence_state"] == "compile_checked"
    assert projection["validated"] is False
    assert projection["creates_compliance_authority"] is False


def test_failed_external_sync_becomes_incident_evidence_without_local_state_corruption() -> None:
    projection = build_governance_evidence_projection(
        subject_ref="service:sync",
        execution_refs=["run:sync-1"],
        service_change_state="incident",
        evidence_state="runtime_observed",
        incident_refs=["incident:external-sync-timeout"],
        problem_refs=["problem:provider-unreachable"],
        change_refs=[],
        release_refs=[],
        provenance_refs=["local-state:sha256:abc"],
        external_sync_status="failed",
        canonical_local_state_unchanged=True,
    )
    assert projection["incident_refs"] == ["incident:external-sync-timeout"]
    assert projection["canonical_local_state_unchanged"] is True
    assert projection["external_sync_failure_changes_semantic_truth"] is False


def test_absent_validation_receipt_cannot_promote_validation_state() -> None:
    projection = build_governance_evidence_projection(
        subject_ref="service:inv1",
        execution_refs=["run:123"],
        service_change_state="validated",
        evidence_state="runtime_observed",
        incident_refs=[],
        problem_refs=[],
        change_refs=["change:1"],
        release_refs=[],
        provenance_refs=["state:1"],
        validation_receipt_refs=[],
    )
    assert projection["service_change_state"] == "implemented"
    assert projection["validation_promotion_blocked"] is True
