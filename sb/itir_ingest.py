REQUIRED_FIELDS = {"activity_event_id", "annotation_id", "provenance"}
OPTIONAL_FIELDS = {"sb_state_id", "state_date", "observer_kind", "status", "confidence", "note"}
FORBIDDEN_FIELDS = {
    "activity_events",
    "activity_ledger",
    "drift",
    "events",
    "segments",
    "summary",
    "summary_segments",
    "summary_text",
    "snapshots",
    "state",
    "threads",
    "mutations",
}


def validate_overlay(record):
    if not isinstance(record, dict):
        return ["overlay must be a dict"]

    errors = []
    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    if not ("sb_state_id" in record or "state_date" in record):
        errors.append("missing sb_state_id or state_date")

    forbidden = FORBIDDEN_FIELDS.intersection(record.keys())
    if forbidden:
        errors.append(f"forbidden fields present: {sorted(forbidden)}")

    kind = record.get("observer_kind")

    if kind == "itir_mission_graph_v1":
        if "mission_refs" not in record:
            errors.append("mission observer overlay missing mission_refs")
        if "evidence_refs" not in record:
            errors.append("mission observer overlay missing evidence_refs")
        if "threads" in record or "events" in record:
            errors.append("mission observer overlays must stay reference-heavy and may not inject threads/events")

    if kind == "fuzzymodo_selector_v1":
        # Extension tables are optional at ingest boundary; we just ensure the base
        # overlay stays reference-heavy.
        if "selector" in record or "norm_constraints" in record:
            errors.append("fuzzymodo selector overlays must not include selector or norm payloads")
        if "selector_refs" in record and not isinstance(record.get("selector_refs"), list):
            errors.append("fuzzymodo selector overlay selector_refs must be a list")
        if "reason_codes" in record and not isinstance(record.get("reason_codes"), list):
            errors.append("fuzzymodo selector overlay reason_codes must be a list")
        if "artifact_refs" in record and not isinstance(record.get("artifact_refs"), list):
            errors.append("fuzzymodo selector overlay artifact_refs must be a list")

    return errors


def persist_overlays(*, db_path, records):
    from pathlib import Path

    from sb.dashboard_store_sqlite import upsert_itir_overlay_records

    accepted = []
    for record in records:
        errors = validate_overlay(record)
        if errors:
            raise ValueError("; ".join(errors))
        accepted.append(dict(record))
    upsert_itir_overlay_records(db_path=Path(db_path), records=accepted)
    return {"accepted_count": len(accepted)}
