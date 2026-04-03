from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _source_artifact_ids(state: dict[str, Any], date_text: str) -> list[str]:
    sources = state.get("sources")
    canonical_state = f"statiBaker.outputs:{date_text}:state.json"
    artifact_ids: list[str] = [canonical_state]
    if isinstance(sources, list):
        for item in sources:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri")
            if isinstance(uri, str) and uri.strip():
                uri_value = uri.strip()
                if uri_value != canonical_state:
                    artifact_ids.append(uri_value)
    return artifact_ids


def _has_unresolved_pressure(state: dict[str, Any]) -> bool:
    for key in ("alerts", "open_questions", "blocked_tasks"):
        value = state.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def build_compiled_state_normalized_artifact(
    state: dict[str, Any],
    *,
    artifact_ref: str = "outputs/state.json",
    profile_version: str = "statiBaker.compiled_state.v1",
    context_envelope_ref: str | None = "context_envelope.json",
) -> dict[str, Any]:
    date_text = str(state.get("date") or "").strip()
    if not date_text:
        raise ValueError("compiled state artifact requires state['date']")

    unresolved_pressure_status = "follow_needed" if _has_unresolved_pressure(state) else "none"
    follow_obligation: dict[str, Any] | None = None
    if unresolved_pressure_status != "none":
        follow_obligation = {
            "trigger": "compiled_state_unresolved_pressure",
            "scope": f"review unresolved alerts/open questions/blocked tasks for {date_text}",
            "stop_condition": "all unresolved pressure is resolved, explicitly held, or promoted downstream",
        }

    return {
        "schema_version": "itir.normalized.artifact.v1",
        "artifact_role": "compiled_state",
        "artifact_id": f"statiBaker.compiled_state:{date_text}",
        "canonical_identity": {
            "identity_class": "statiBaker_day_state",
            "identity_key": date_text,
            "aliases": [f"sb.day:{date_text}", f"sb.compiled_state:{date_text}"],
        },
        "provenance_anchor": {
            "source_system": "StatiBaker",
            "source_artifact_id": f"statiBaker.outputs:{date_text}:state.json",
            "anchor_kind": "compiled_state_file",
            "anchor_ref": artifact_ref,
        },
        "context_envelope_ref": {
            "envelope_id": f"statiBaker.day_context:{date_text}",
            "envelope_kind": "compiled_day_context",
            **({"envelope_ref": context_envelope_ref} if context_envelope_ref else {}),
        },
        "authority": {
            "authority_class": "state",
            "derived": False,
            "promotion_receipt_ref": None,
        },
        "lineage": {
            "upstream_artifact_ids": _source_artifact_ids(state, date_text),
            "profile_version": profile_version,
        },
        "follow_obligation": follow_obligation,
        "unresolved_pressure_status": unresolved_pressure_status,
        "summary": {
            "producer": "StatiBaker",
            "date": date_text,
            "day_state": state.get("day_state"),
            "human_energy": state.get("human_energy"),
            "priority_count": len(state.get("priorities") or []),
            "alert_count": len(state.get("alerts") or []),
            "open_question_count": len(state.get("open_questions") or []),
            "blocked_task_count": len(state.get("blocked_tasks") or []),
            "event_count": len(state.get("events") or []),
            "source_count": len(state.get("sources") or []),
        },
    }


def write_compiled_state_normalized_artifact(
    out_path: Path,
    state: dict[str, Any],
    *,
    artifact_ref: str = "outputs/state.json",
    profile_version: str = "statiBaker.compiled_state.v1",
    context_envelope_ref: str | None = "context_envelope.json",
) -> dict[str, Any]:
    payload = build_compiled_state_normalized_artifact(
        state,
        artifact_ref=artifact_ref,
        profile_version=profile_version,
        context_envelope_ref=context_envelope_ref,
    )
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload
