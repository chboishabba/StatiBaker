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

        selector_refs = record.get("selector_refs") if isinstance(record.get("selector_refs"), list) else []
        for i, sref in enumerate(selector_refs):
            if not isinstance(sref, dict):
                continue
            if not str(sref.get("selector_hash") or "").strip():
                errors.append(f"fuzzymodo selector_refs[{i}].selector_hash required")
            matched = sref.get("matched")
            if matched is not None and matched not in {0, 1}:
                errors.append(f"fuzzymodo selector_refs[{i}].matched must be 0 or 1")

        reason_codes = record.get("reason_codes") if isinstance(record.get("reason_codes"), list) else []
        for i, rc in enumerate(reason_codes):
            if not isinstance(rc, dict):
                continue
            if not str(rc.get("reason_code") or "").strip():
                errors.append(f"fuzzymodo reason_codes[{i}].reason_code required")

        artifact_refs = record.get("artifact_refs") if isinstance(record.get("artifact_refs"), list) else []
        for i, ar in enumerate(artifact_refs):
            if not isinstance(ar, dict):
                continue
            if not str(ar.get("artifact_kind") or "").strip():
                errors.append(f"fuzzymodo artifact_refs[{i}].artifact_kind required")
            if not str(ar.get("artifact_locator") or "").strip():
                errors.append(f"fuzzymodo artifact_refs[{i}].artifact_locator required")

        selector_refs = record.get("selector_refs") if isinstance(record.get("selector_refs"), list) else []
        for i, s in enumerate(selector_refs):
            if not isinstance(s, dict):
                continue
            if not str(s.get("selector_hash") or "").strip():
                errors.append(f"fuzzymodo selector_refs[{i}].selector_hash required")

        reason_codes = record.get("reason_codes") if isinstance(record.get("reason_codes"), list) else []
        for i, r in enumerate(reason_codes):
            if not isinstance(r, dict):
                continue
            if not str(r.get("reason_code") or "").strip():
                errors.append(f"fuzzymodo reason_codes[{i}].reason_code required")

        artifact_refs = record.get("artifact_refs") if isinstance(record.get("artifact_refs"), list) else []
        for i, a in enumerate(artifact_refs):
            if not isinstance(a, dict):
                continue
            if not str(a.get("artifact_kind") or "").strip():
                errors.append(f"fuzzymodo artifact_refs[{i}].artifact_kind required")
            if not str(a.get("artifact_locator") or "").strip():
                errors.append(f"fuzzymodo artifact_refs[{i}].artifact_locator required")

    if kind == "casey_workspace_v1":
        # Reference-only: IDs, digests, receipts.
        if "workspace" in record or "candidate_graph" in record:
            errors.append("casey workspace overlays must not include mutable workspace/candidate payloads")
        for field in ("workspace_refs", "operation_refs", "build_refs"):
            if field in record and not isinstance(record.get(field), list):
                errors.append(f"casey workspace overlay {field} must be a list")

        workspace_refs = record.get("workspace_refs") if isinstance(record.get("workspace_refs"), list) else []
        for i, w in enumerate(workspace_refs):
            if not isinstance(w, dict):
                continue
            if not str(w.get("ws_id") or "").strip():
                errors.append(f"casey workspace_refs[{i}].ws_id required")

        operation_refs = record.get("operation_refs") if isinstance(record.get("operation_refs"), list) else []
        for i, op in enumerate(operation_refs):
            if not isinstance(op, dict):
                continue
            if not str(op.get("operation_kind") or "").strip():
                errors.append(f"casey operation_refs[{i}].operation_kind required")
            receipt_hash = op.get("receipt_hash")
            if receipt_hash is not None and len(str(receipt_hash)) not in {0, 64}:
                errors.append(f"casey operation_refs[{i}].receipt_hash must be 64 hex chars")

        build_refs = record.get("build_refs") if isinstance(record.get("build_refs"), list) else []
        for i, b in enumerate(build_refs):
            if not isinstance(b, dict):
                continue
            if not str(b.get("build_id") or "").strip():
                errors.append(f"casey build_refs[{i}].build_id required")
            if not str(b.get("tree_id") or "").strip():
                errors.append(f"casey build_refs[{i}].tree_id required")
            if not str(b.get("selection_digest") or "").strip():
                errors.append(f"casey build_refs[{i}].selection_digest required")

    if kind == "casey_workspace_v1":
        # Reference-only: no mutable workspace graphs.
        for forbidden in ("workspace", "candidates", "candidate_graph", "blobs"):
            if forbidden in record:
                errors.append("casey overlays must not include mutable workspace payloads")
                break
        if "workspace_refs" in record and not isinstance(record.get("workspace_refs"), list):
            errors.append("casey overlay workspace_refs must be a list")
        if "operation_refs" in record and not isinstance(record.get("operation_refs"), list):
            errors.append("casey overlay operation_refs must be a list")
        if "build_refs" in record and not isinstance(record.get("build_refs"), list):
            errors.append("casey overlay build_refs must be a list")

    if kind == "jmd_runtime_v1":
        for forbidden in ("object", "graph", "receipt", "nodes", "edges", "raw_text", "text"):
            if forbidden in record:
                errors.append("jmd runtime overlays must stay reference-heavy")
                break
        for field in ("receipt_refs", "object_refs", "graph_refs"):
            if field in record and not isinstance(record.get(field), list):
                errors.append(f"jmd runtime overlay {field} must be a list")

        receipt_refs = record.get("receipt_refs") if isinstance(record.get("receipt_refs"), list) else []
        for i, receipt_ref in enumerate(receipt_refs):
            if not isinstance(receipt_ref, dict):
                continue
            if not str(receipt_ref.get("receipt_id") or "").strip():
                errors.append(f"jmd runtime receipt_refs[{i}].receipt_id required")

        object_refs = record.get("object_refs") if isinstance(record.get("object_refs"), list) else []
        for i, object_ref in enumerate(object_refs):
            if not isinstance(object_ref, dict):
                continue
            if not str(object_ref.get("object_id") or "").strip():
                errors.append(f"jmd runtime object_refs[{i}].object_id required")
            if not str(object_ref.get("locator") or "").strip():
                errors.append(f"jmd runtime object_refs[{i}].locator required")

        graph_refs = record.get("graph_refs") if isinstance(record.get("graph_refs"), list) else []
        for i, graph_ref in enumerate(graph_refs):
            if not isinstance(graph_ref, dict):
                continue
            if not str(graph_ref.get("graph_id") or "").strip():
                errors.append(f"jmd runtime graph_refs[{i}].graph_id required")

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
