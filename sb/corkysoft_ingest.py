from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from sb.dashboard_store_sqlite import upsert_itir_overlay_records


ALLOWED_EVENT_FAMILIES = {
    "planning_snapshot",
    "diary_task_event",
    "job_usage_review",
    "vehicle_usage_review",
    "staff_usage_review",
    "customer_invoice_review",
    "subcontractor_bill_review",
    "reconciliation_exception",
    "compliance_gap_flag",
}

ALLOWED_AUTHORITY_CLASSES = {
    "operational_truth",
    "reviewed_summary",
    "observed_actual",
    "downstream_projection",
}


def _require_non_empty_str(record: Mapping[str, Any], field: str, errors: list[str]) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} is required")
        return ""
    return value.strip()


def _require_list(record: Mapping[str, Any], field: str, errors: list[str]) -> list[Any]:
    value = record.get(field)
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return []
    return value


def _derive_state_date(event_time: str) -> str:
    normalized = event_time.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).date().isoformat()


def validate_review_event(record: Mapping[str, Any]) -> list[str]:
    if not isinstance(record, Mapping):
        return ["review event must be a dict"]

    errors: list[str] = []
    event_id = _require_non_empty_str(record, "event_id", errors)
    event_family = _require_non_empty_str(record, "event_family", errors)
    event_time = _require_non_empty_str(record, "event_time", errors)
    _require_non_empty_str(record, "source_system", errors)
    _require_non_empty_str(record, "actor_ref", errors)
    authority_class = _require_non_empty_str(record, "authority_class", errors)
    _require_non_empty_str(record, "correlation_key", errors)
    _require_non_empty_str(record, "summary", errors)
    _require_non_empty_str(record, "status", errors)

    object_refs = _require_list(record, "object_refs", errors)
    provenance_refs = _require_list(record, "provenance_refs", errors)
    evidence_refs = _require_list(record, "evidence_refs", errors)

    payload = record.get("payload")
    if not isinstance(payload, dict):
        errors.append("payload must be a dict")

    if event_family and event_family not in ALLOWED_EVENT_FAMILIES:
        errors.append(f"unsupported event_family: {event_family}")
    if authority_class and authority_class not in ALLOWED_AUTHORITY_CLASSES:
        errors.append(f"unsupported authority_class: {authority_class}")
    if event_time:
        try:
            _derive_state_date(event_time)
        except ValueError:
            errors.append("event_time must be ISO-8601")

    for field_name, items in (
        ("object_refs", object_refs),
        ("provenance_refs", provenance_refs),
        ("evidence_refs", evidence_refs),
    ):
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{field_name}[{idx}] must be a dict")

    if event_id and any(field in record for field in ("activity_events", "state", "threads", "events")):
        errors.append("review events must stay reference-heavy and may not inject mutable SB state fields")

    return errors


def review_event_to_overlay(
    record: Mapping[str, Any],
    *,
    annotation_id: str | None = None,
    activity_event_id: str | None = None,
    sb_state_id: str | None = None,
    state_date: str | None = None,
) -> dict[str, Any]:
    errors = validate_review_event(record)
    if errors:
        raise ValueError("; ".join(errors))

    event_id = str(record["event_id"]).strip()
    family = str(record["event_family"]).strip()
    summary = str(record["summary"]).strip()
    return {
        "activity_event_id": activity_event_id or event_id,
        "annotation_id": annotation_id or f"obs:corkysoft:{event_id}",
        "sb_state_id": sb_state_id or f"corkysoft:{family}",
        "state_date": state_date or _derive_state_date(str(record["event_time"])),
        "observer_kind": "corkysoft_review_event_v1",
        "status": str(record["status"]).strip(),
        "confidence": str(record["authority_class"]).strip(),
        "provenance": {
            "source": str(record["source_system"]).strip(),
            "event_time": str(record["event_time"]).strip(),
            "actor_ref": str(record["actor_ref"]).strip(),
            "correlation_key": str(record["correlation_key"]).strip(),
        },
        "note": summary,
        "event_id": event_id,
        "event_family": family,
        "event_time": str(record["event_time"]).strip(),
        "source_system": str(record["source_system"]).strip(),
        "actor_ref": str(record["actor_ref"]).strip(),
        "authority_class": str(record["authority_class"]).strip(),
        "correlation_key": str(record["correlation_key"]).strip(),
        "summary": summary,
        "object_refs": [dict(item) for item in record["object_refs"]],
        "provenance_refs": [dict(item) for item in record["provenance_refs"]],
        "evidence_refs": [dict(item) for item in record["evidence_refs"]],
        "payload": dict(record["payload"]),
    }


def persist_review_events(*, db_path, records: list[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [review_event_to_overlay(record) for record in records]
    upsert_itir_overlay_records(db_path=db_path, records=normalized)
    return {"accepted_count": len(normalized)}
