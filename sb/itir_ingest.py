import json
import re


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

MAX_TOP_LEVEL_STRING_LEN = 512
MAX_ID_STRING_LEN = 256
MAX_NOTE_LEN = 4096
MAX_PATH_LEN = 2048
MAX_LIST_ITEMS = 256
MAX_REFS_ITEMS = 128
MAX_HASH_HEX_LEN = 128
MAX_HASH_SHA256_LEN = 64
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_SMALL_TEXT_LEN = 1024


def _check_str(value, *, field: str, errors: list[str], required: bool = False, max_len: int = MAX_TOP_LEVEL_STRING_LEN) -> None:
    if value is None:
        if required:
            errors.append(f"{field} required")
        return
    if not isinstance(value, str):
        if required:
            errors.append(f"{field} required")
        else:
            errors.append(f"{field} must be a string")
        return
    if required and not value.strip():
        errors.append(f"{field} required")
    if len(value) > max_len:
        errors.append(f"{field} exceeds max length {max_len}")


def _check_json_payload(value, *, field: str, errors: list[str], max_bytes: int = MAX_PAYLOAD_BYTES) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{field} must be a dict")
        return
    try:
        encoded = json.dumps(value, sort_keys=True)
    except Exception:
        errors.append(f"{field} must be JSON-serializable")
        return
    if len(encoded.encode("utf-8")) > max_bytes:
        errors.append(f"{field} exceeds max size {max_bytes} bytes")


def _check_hex(value: str, *, field: str, errors: list[str], required_len: int | None = None) -> None:
    if value is None:
        errors.append(f"{field} required")
        return
    if not isinstance(value, str):
        errors.append(f"{field} required")
        return
    if required_len is not None and len(value) != required_len:
        errors.append(f"{field} must be {required_len} characters")
        return
    if len(value) > MAX_HASH_HEX_LEN:
        errors.append(f"{field} exceeds max length {MAX_HASH_HEX_LEN}")
        return
    if not re.fullmatch(r"[0-9a-fA-F]+", value or ""):
        errors.append(f"{field} must be hex")


def _check_int(value, *, field: str, errors: list[str], min_value: int = 0, max_value: int = 10_000_000) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{field} must be an integer")
        return
    if value < min_value or value > max_value:
        errors.append(f"{field} must be between {min_value} and {max_value}")


def _check_list(value, *, field: str, errors: list[str], max_items: int = MAX_LIST_ITEMS) -> list[object] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return None
    if len(value) > max_items:
        errors.append(f"{field} exceeds max list items ({max_items})")
    return value


def validate_overlay(record):
    if not isinstance(record, dict):
        return ["overlay must be a dict"]

    errors: list[str] = []
    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    if not ("sb_state_id" in record or "state_date" in record):
        errors.append("missing sb_state_id or state_date")

    forbidden = FORBIDDEN_FIELDS.intersection(record.keys())
    kind = record.get("observer_kind")
    if kind == "corkysoft_review_event_v1":
        forbidden = {field for field in forbidden if field != "summary"}
    if forbidden:
        errors.append(f"forbidden fields present: {sorted(forbidden)}")

    _check_str(record.get("activity_event_id"), field="activity_event_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
    _check_str(record.get("annotation_id"), field="annotation_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
    _check_str(record.get("observer_kind"), field="observer_kind", errors=errors, max_len=MAX_ID_STRING_LEN)
    _check_str(record.get("status"), field="status", errors=errors, max_len=64)
    _check_str(record.get("confidence"), field="confidence", errors=errors, max_len=64)
    _check_str(record.get("note"), field="note", errors=errors, max_len=MAX_NOTE_LEN)
    _check_str(record.get("sb_state_id"), field="sb_state_id", errors=errors, max_len=MAX_ID_STRING_LEN)
    _check_str(record.get("state_date"), field="state_date", errors=errors, max_len=MAX_TOP_LEVEL_STRING_LEN)
    _check_json_payload(record.get("provenance"), field="provenance", errors=errors)

    if kind == "itir_mission_graph_v1":
        if "mission_refs" not in record:
            errors.append("mission observer overlay missing mission_refs")
        if "evidence_refs" not in record:
            errors.append("mission observer overlay missing evidence_refs")
        if "threads" in record or "events" in record:
            errors.append("mission observer overlays must stay reference-heavy and may not inject threads/events")

        mission_refs = _check_list(record.get("mission_refs"), field="mission_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        evidence_refs = _check_list(record.get("evidence_refs"), field="evidence_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []

        for i, item in enumerate(mission_refs):
            if not isinstance(item, dict):
                errors.append(f"mission mission_refs[{i}] must be a dict")
                continue
            _check_str(item.get("mission_id"), field=f"mission_refs[{i}].mission_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("node_kind"), field=f"mission_refs[{i}].node_kind", errors=errors, max_len=64)
            _check_str(item.get("topic_label"), field=f"mission_refs[{i}].topic_label", errors=errors, max_len=MAX_SMALL_TEXT_LEN)
            _check_str(item.get("ref_type"), field=f"mission_refs[{i}].ref_type", errors=errors, max_len=64)

        for i, item in enumerate(evidence_refs):
            if not isinstance(item, dict):
                errors.append(f"mission evidence_refs[{i}] must be a dict")
                continue
            _check_str(item.get("event_id"), field=f"evidence_refs[{i}].event_id", errors=errors, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("source_id"), field=f"evidence_refs[{i}].source_id", errors=errors, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("ref_kind"), field=f"evidence_refs[{i}].ref_kind", errors=errors, max_len=MAX_ID_STRING_LEN)

    elif kind in {"fuzzymodo_selector_v1", "fuzzymodo_codex_trace_v1"}:
        # Extension tables are optional at ingest boundary; we just ensure the base
        # overlay stays reference-heavy.
        if "selector" in record or "norm_constraints" in record:
            errors.append("fuzzymodo selector overlays must not include selector or norm payloads")

        selector_refs = _check_list(record.get("selector_refs"), field="selector_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        reason_codes = _check_list(record.get("reason_codes"), field="reason_codes", errors=errors, max_items=MAX_REFS_ITEMS) or []
        artifact_refs = _check_list(record.get("artifact_refs"), field="artifact_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []

        for i, item in enumerate(selector_refs):
            if not isinstance(item, dict):
                errors.append(f"fuzzymodo selector_refs[{i}] must be a dict")
                continue
            _check_str(item.get("selector_hash"), field=f"selector_refs[{i}].selector_hash", errors=errors, required=True, max_len=MAX_HASH_SHA256_LEN)
            _check_str(item.get("decision_state"), field=f"selector_refs[{i}].decision_state", errors=errors, max_len=64)
            _check_str(item.get("policy_hash"), field=f"selector_refs[{i}].policy_hash", errors=errors, max_len=MAX_HASH_SHA256_LEN)
            _check_str(item.get("replay_key"), field=f"selector_refs[{i}].replay_key", errors=errors, max_len=MAX_PATH_LEN)
            _check_str(item.get("created_at"), field=f"selector_refs[{i}].created_at", errors=errors, max_len=64)
            if "matched" in item:
                matched = item.get("matched")
                if matched not in {0, 1}:
                    errors.append(f"fuzzymodo selector_refs[{i}].matched must be 0 or 1")

        for i, item in enumerate(reason_codes):
            if not isinstance(item, dict):
                errors.append(f"fuzzymodo reason_codes[{i}] must be a dict")
                continue
            _check_str(item.get("reason_code"), field=f"reason_codes[{i}].reason_code", errors=errors, required=True, max_len=MAX_SMALL_TEXT_LEN)
            _check_str(item.get("detail"), field=f"reason_codes[{i}].detail", errors=errors, max_len=MAX_SMALL_TEXT_LEN)

        for i, item in enumerate(artifact_refs):
            if not isinstance(item, dict):
                errors.append(f"fuzzymodo artifact_refs[{i}] must be a dict")
                continue
            _check_str(item.get("artifact_kind"), field=f"artifact_refs[{i}].artifact_kind", errors=errors, required=True, max_len=MAX_SMALL_TEXT_LEN)
            _check_str(item.get("artifact_locator"), field=f"artifact_refs[{i}].artifact_locator", errors=errors, required=True, max_len=MAX_PATH_LEN)
            if item.get("artifact_hash") is not None:
                _check_hex(
                    item.get("artifact_hash"),
                    field=f"artifact_refs[{i}].artifact_hash",
                    errors=errors,
                    required_len=MAX_HASH_SHA256_LEN,
                )

    elif kind == "casey_workspace_v1":
        # Reference-only: no mutable workspace graphs.
        for forbidden in ("workspace", "candidates", "candidate_graph", "blobs"):
            if forbidden in record:
                errors.append("casey overlays must not include mutable workspace payloads")
                break

        workspace_refs = _check_list(record.get("workspace_refs"), field="workspace_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        operation_refs = _check_list(record.get("operation_refs"), field="operation_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        build_refs = _check_list(record.get("build_refs"), field="build_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []

        for i, item in enumerate(workspace_refs):
            if not isinstance(item, dict):
                errors.append(f"casey workspace_refs[{i}] must be a dict")
                continue
            _check_str(item.get("ws_id"), field=f"workspace_refs[{i}].ws_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("head_tree_id"), field=f"workspace_refs[{i}].head_tree_id", errors=errors, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("policy_tie_break"), field=f"workspace_refs[{i}].policy_tie_break", errors=errors, max_len=128)
            _check_str(item.get("policy_prefer_author"), field=f"workspace_refs[{i}].policy_prefer_author", errors=errors, max_len=128)
            _check_int(item.get("selected_path_count"), field=f"workspace_refs[{i}].selected_path_count", errors=errors, min_value=0, max_value=10_000_000)

        for i, item in enumerate(operation_refs):
            if not isinstance(item, dict):
                errors.append(f"casey operation_refs[{i}] must be a dict")
                continue
            _check_str(item.get("operation_kind"), field=f"operation_refs[{i}].operation_kind", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("path"), field=f"operation_refs[{i}].path", errors=errors, max_len=MAX_PATH_LEN)
            _check_str(item.get("tree_id_before"), field=f"operation_refs[{i}].tree_id_before", errors=errors, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("tree_id_after"), field=f"operation_refs[{i}].tree_id_after", errors=errors, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("chosen_fv_id"), field=f"operation_refs[{i}].chosen_fv_id", errors=errors, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("resolved_fv_id"), field=f"operation_refs[{i}].resolved_fv_id", errors=errors, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("created_at"), field=f"operation_refs[{i}].created_at", errors=errors, max_len=64)
            if item.get("receipt_hash") is not None:
                _check_hex(
                    item.get("receipt_hash"),
                    field=f"operation_refs[{i}].receipt_hash",
                    errors=errors,
                    required_len=MAX_HASH_SHA256_LEN,
                )

        for i, item in enumerate(build_refs):
            if not isinstance(item, dict):
                errors.append(f"casey build_refs[{i}] must be a dict")
                continue
            _check_str(item.get("build_id"), field=f"build_refs[{i}].build_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("tree_id"), field=f"build_refs[{i}].tree_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("created_at"), field=f"build_refs[{i}].created_at", errors=errors, max_len=64)
            _check_hex(
                item.get("selection_digest"),
                field=f"build_refs[{i}].selection_digest",
                errors=errors,
                required_len=MAX_HASH_SHA256_LEN,
            )

    elif kind == "jmd_runtime_v1":
        for forbidden in ("object", "graph", "receipt", "nodes", "edges", "raw_text", "text"):
            if forbidden in record:
                errors.append("jmd runtime overlays must stay reference-heavy")
                break

        receipt_refs = _check_list(record.get("receipt_refs"), field="receipt_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        object_refs = _check_list(record.get("object_refs"), field="object_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        graph_refs = _check_list(record.get("graph_refs"), field="graph_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []

        for i, item in enumerate(receipt_refs):
            if not isinstance(item, dict):
                errors.append(f"jmd runtime receipt_refs[{i}] must be a dict")
                continue
            _check_str(item.get("receipt_id"), field=f"receipt_refs[{i}].receipt_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)

        for i, item in enumerate(object_refs):
            if not isinstance(item, dict):
                errors.append(f"jmd runtime object_refs[{i}] must be a dict")
                continue
            _check_str(item.get("object_id"), field=f"object_refs[{i}].object_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
            _check_str(item.get("locator"), field=f"object_refs[{i}].locator", errors=errors, required=True, max_len=MAX_PATH_LEN)

        for i, item in enumerate(graph_refs):
            if not isinstance(item, dict):
                errors.append(f"jmd runtime graph_refs[{i}] must be a dict")
                continue
            _check_str(item.get("graph_id"), field=f"graph_refs[{i}].graph_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)

    elif kind == "corkysoft_review_event_v1":
        required = (
            "event_id",
            "event_family",
            "event_time",
            "source_system",
            "actor_ref",
            "authority_class",
            "correlation_key",
            "summary",
            "object_refs",
            "provenance_refs",
            "evidence_refs",
            "payload",
        )
        for field in required:
            if field not in record:
                errors.append(f"corkysoft review overlay missing {field}")

        if "activity_events" in record or "state" in record or "threads" in record or "events" in record or "shipments" in record or "jobs" in record:
            errors.append("corkysoft review overlays must stay reference-heavy and may not inject mutable workflow state")

        _check_str(record.get("event_id"), field="corkysoft review overlay event_id", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
        _check_str(record.get("event_family"), field="corkysoft review overlay event_family", errors=errors, required=True, max_len=64)
        _check_str(record.get("event_time"), field="corkysoft review overlay event_time", errors=errors, required=True, max_len=64)
        _check_str(record.get("source_system"), field="corkysoft review overlay source_system", errors=errors, required=True, max_len=128)
        _check_str(record.get("actor_ref"), field="corkysoft review overlay actor_ref", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
        _check_str(record.get("authority_class"), field="corkysoft review overlay authority_class", errors=errors, required=True, max_len=128)
        _check_str(record.get("correlation_key"), field="corkysoft review overlay correlation_key", errors=errors, required=True, max_len=MAX_ID_STRING_LEN)
        _check_str(record.get("summary"), field="corkysoft review overlay summary", errors=errors, required=True, max_len=MAX_NOTE_LEN)

        object_refs = _check_list(record.get("object_refs"), field="object_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        provenance_refs = _check_list(record.get("provenance_refs"), field="provenance_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []
        evidence_refs = _check_list(record.get("evidence_refs"), field="evidence_refs", errors=errors, max_items=MAX_REFS_ITEMS) or []

        if not isinstance(record.get("payload"), dict):
            errors.append("corkysoft review overlay payload must be a dict")
        elif record.get("payload") is not None:
            _check_json_payload(record.get("payload"), field="corkysoft review overlay payload", errors=errors)

        for i, item in enumerate(object_refs):
            if not isinstance(item, dict):
                errors.append(f"corkysoft object_refs[{i}] must be a dict")

        for i, item in enumerate(provenance_refs):
            if not isinstance(item, dict):
                errors.append(f"corkysoft provenance_refs[{i}] must be a dict")

        for i, item in enumerate(evidence_refs):
            if not isinstance(item, dict):
                errors.append(f"corkysoft evidence_refs[{i}] must be a dict")

    return errors


def persist_overlays(*, db_path, records):
    from pathlib import Path
    import sqlite3

    from sb.dashboard_store_sqlite import upsert_itir_overlay_records

    accepted = []
    for record in records:
        errors = validate_overlay(record)
        if errors:
            raise ValueError("; ".join(errors))
        accepted.append(dict(record))
    try:
        upsert_itir_overlay_records(db_path=Path(db_path), records=accepted)
    except sqlite3.IntegrityError as exc:
        raise ValueError("overlay annotation_id conflict") from exc
    return {"accepted_count": len(accepted)}
