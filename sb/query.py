import json
from pathlib import Path

from sb.codex_trace import (
    facts_from_chat_archive_db,
    facts_from_dashboard_payload,
    facts_from_raw_codex_logs,
)
from sb.runsheet_bridge import build_runsheet_projection
from sb.todo_graph import analyze_repo_todos


def _resolve_path(path):
    return Path(path).expanduser().resolve()


def _read_json(path, base_dir=None):
    target = _resolve_path(path)
    if base_dir:
        base = _resolve_path(base_dir)
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"path escapes base_dir: {path}") from exc
    with open(target, "r", encoding="utf-8") as handle:
        return json.load(handle)


def list_activity_events(ledger_path, base_dir=None):
    ledger = _read_json(ledger_path, base_dir=base_dir)
    return ledger.get("activity_events", []) if isinstance(ledger, dict) else []


def carryover_summary(state_path, base_dir=None):
    state = _read_json(state_path, base_dir=base_dir)
    return {
        "carryover_threads": state.get("carryover_threads", []),
        "carryover_new_threads": state.get("carryover_new_threads", []),
        "carryover_resolved_threads": state.get("carryover_resolved_threads", []),
        "carryover_age_days": state.get("carryover_age_days", {}),
    }


def provenance(state_path, ledger_path=None, drift_path=None, base_dir=None):
    state = _read_json(state_path, base_dir=base_dir)
    payload = {"sources": state.get("sources", [])}
    if ledger_path:
        ledger = _read_json(ledger_path, base_dir=base_dir)
        payload["activity_ledger"] = ledger.get("provenance", {}) if isinstance(ledger, dict) else {}
    if drift_path:
        drift = _read_json(drift_path, base_dir=base_dir)
        payload["drift"] = drift.get("provenance", {}) if isinstance(drift, dict) else {}
    return payload


def commitment_feed(dashboard_path, base_dir=None):
    payload = _read_json(dashboard_path, base_dir=base_dir)
    return {
        "summary": payload.get("external_commitment_summary", {}),
        "items": payload.get("external_commitments", []),
    }


def completion_candidates(dashboard_path, base_dir=None):
    payload = _read_json(dashboard_path, base_dir=base_dir)
    return {
        "candidates": payload.get("task_completion_candidates", []),
    }


def runsheet_progress(dashboard_path, base_dir=None):
    payload = _read_json(dashboard_path, base_dir=base_dir)
    return {
        "summary": payload.get("runsheet_progress_summary", {}),
        "rows": payload.get("runsheet_progress_rows", []),
    }


def kanboard_sync_report(report_path, base_dir=None):
    payload = _read_json(report_path, base_dir=base_dir)
    if not isinstance(payload, dict):
        return {}
    return {
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "mode": payload.get("mode"),
        "authority_boundary": payload.get("authority_boundary", {}),
        "project": payload.get("project", {}),
        "input_source": payload.get("input_source", {}),
        "artifact": payload.get("artifact", {}),
        "summary": payload.get("summary", {}),
        "progress": payload.get("progress", {}),
        "external_references": payload.get("external_references", {}),
        "errors": payload.get("errors", []),
    }


def latest_kanboard_sync_report(runs_root, base_dir=None):
    root = _resolve_path(runs_root)
    if base_dir:
        base = _resolve_path(base_dir)
        try:
            root.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"path escapes base_dir: {runs_root}") from exc
    candidates = sorted(root.glob("*/outputs/kanboard_sync_report*.json"))
    if not candidates:
        return {"found": False, "path": None, "report": None}
    latest = candidates[-1]
    return {
        "found": True,
        "path": str(latest),
        "report": kanboard_sync_report(latest, base_dir=base_dir),
    }


def kanboard_manager_wave_status(
    status_root,
    stabilization_status_name="status.statibaker-kanboard-stabilization-manager.json",
    base_dir=None,
):
    root = _resolve_path(status_root)
    if base_dir:
        base = _resolve_path(base_dir)
        try:
            root.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"path escapes base_dir: {status_root}") from exc

    status_paths = sorted(root.glob("status.statibaker-kanboard-*-manager.json"))
    stabilization_path = root / stabilization_status_name
    stabilization_state = _read_json(stabilization_path, base_dir=base_dir) if stabilization_path.exists() else {}
    stabilization_remaining = None
    if isinstance(stabilization_state, dict):
        raw_remaining = stabilization_state.get("milestones_remaining", 1)
        try:
            stabilization_remaining = int(raw_remaining)
        except (TypeError, ValueError):
            stabilization_remaining = None
    stabilization_closed = stabilization_remaining == 0

    managers = []
    for status_path in status_paths:
        payload = _read_json(status_path, base_dir=base_dir)
        if not isinstance(payload, dict):
            continue

        name = status_path.name
        heartbeat_path = root / name.replace("status.", "heartbeat.")
        heartbeat = _read_json(heartbeat_path, base_dir=base_dir) if heartbeat_path.exists() else {}

        items = payload.get("runsheet", {}).get("items", [])
        pending = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("status") in {"todo", "in_progress", "blocked"}:
                pending.append(item.get("id") or item.get("title"))

        milestones_remaining = int(payload.get("milestones_remaining", 0) or 0)
        heartbeat_done = (
            isinstance(heartbeat, dict)
            and heartbeat.get("state") == 0
            and heartbeat.get("phase") == "done"
        )
        reconcile_candidate = (
            name != stabilization_status_name
            and milestones_remaining > 0
            and bool(pending)
            and stabilization_closed
            and heartbeat_done
        )
        managers.append(
            {
                "status_file": name,
                "heartbeat_file": heartbeat_path.name if heartbeat_path.exists() else None,
                "phase": payload.get("phase"),
                "milestones_remaining": milestones_remaining,
                "pending_items": pending,
                "heartbeat_done": heartbeat_done,
                "reconcile_candidate": reconcile_candidate,
            }
        )

    return {
        "schema_version": "sb.kanboard_manager_wave_status.v0_1",
        "status_root": str(root),
        "stabilization_status": {
            "status_file": stabilization_status_name,
            "exists": stabilization_path.exists(),
            "closed": stabilization_closed,
            "milestones_remaining": stabilization_remaining,
        },
        "summary": {
            "managers_total": len(managers),
            "pending_managers": sum(1 for item in managers if item["milestones_remaining"] > 0),
            "reconcile_candidates": sum(1 for item in managers if item["reconcile_candidate"]),
        },
        "managers": managers,
    }


def corkysoft_review_feed(dashboard_path, base_dir=None):
    payload = _read_json(dashboard_path, base_dir=base_dir)
    return {
        "summary": payload.get("corkysoft_review_summary", {}),
        "items": payload.get("corkysoft_review_events", []),
    }


def codex_trace_dashboard(dashboard_path, base_dir=None):
    payload = _read_json(dashboard_path, base_dir=base_dir)
    return facts_from_dashboard_payload(payload)


def codex_trace_archive(db_path, canonical_thread_id=None, limit=None, base_dir=None):
    target = _resolve_path(db_path)
    if base_dir:
        base = _resolve_path(base_dir)
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"path escapes base_dir: {db_path}") from exc
    return facts_from_chat_archive_db(target, canonical_thread_id=canonical_thread_id, limit=limit)


def codex_trace_logs(history_path, log_path, canonical_thread_id=None, base_dir=None):
    history_target = _resolve_path(history_path)
    log_target = _resolve_path(log_path)
    if base_dir:
        base = _resolve_path(base_dir)
        for original, target in ((history_path, history_target), (log_path, log_target)):
            try:
                target.relative_to(base)
            except ValueError as exc:
                raise ValueError(f"path escapes base_dir: {original}") from exc
    return facts_from_raw_codex_logs(
        history_path=history_target,
        log_path=log_target,
        canonical_thread_id=canonical_thread_id,
    )


def _resolve_optional_paths(paths, base_dir=None):
    resolved = []
    for path in paths or []:
        target = _resolve_path(path)
        if base_dir:
            base = _resolve_path(base_dir)
            try:
                target.relative_to(base)
            except ValueError as exc:
                raise ValueError(f"path escapes base_dir: {path}") from exc
        resolved.append(target)
    return resolved


def todo_graph(repo_root, todo_paths=None, base_dir=None):
    root = _resolve_path(repo_root)
    if base_dir:
        base = _resolve_path(base_dir)
        try:
            root.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"path escapes base_dir: {repo_root}") from exc
    return analyze_repo_todos(root, todo_paths=_resolve_optional_paths(todo_paths, base_dir=base_dir))


def todo_obligations(repo_root, todo_paths=None, base_dir=None):
    payload = todo_graph(repo_root, todo_paths=todo_paths, base_dir=base_dir)
    return {"obligations": payload.get("obligations", [])}


def todo_obligation(repo_root, obligation_id, todo_paths=None, base_dir=None):
    payload = todo_graph(repo_root, todo_paths=todo_paths, base_dir=base_dir)
    for item in payload.get("evaluations", []):
        obligation = item.get("obligation") if isinstance(item.get("obligation"), dict) else {}
        if str(obligation.get("obligation_id") or "") == str(obligation_id):
            return item
    return None


def todo_candidates(repo_root, todo_paths=None, base_dir=None):
    payload = todo_graph(repo_root, todo_paths=todo_paths, base_dir=base_dir)
    return {"candidates": payload.get("completion_candidates", [])}


def todo_alignment(repo_root, todo_paths=None, base_dir=None):
    payload = todo_graph(repo_root, todo_paths=todo_paths, base_dir=base_dir)
    return payload.get("alignment", {})


def runsheet_projection(state_path, base_dir=None):
    state = _read_json(state_path, base_dir=base_dir)
    if isinstance(state, dict):
        source = state.get("runsheet_source")
        if isinstance(source, dict):
            rel_path = source.get("path")
            if isinstance(rel_path, str) and rel_path.strip():
                state_dir = _resolve_path(Path(state_path).parent)
                loaded = _read_json(str(state_dir / rel_path), base_dir=base_dir)
                if isinstance(loaded, dict):
                    if "tasks" in loaded:
                        state["tasks"] = loaded.get("tasks")
                    elif "timeline_cases" in loaded:
                        state["timeline_cases"] = loaded.get("timeline_cases")
                    else:
                        state["tasks"] = loaded
                else:
                    state["tasks"] = loaded
    return build_runsheet_projection(state if isinstance(state, dict) else {})
