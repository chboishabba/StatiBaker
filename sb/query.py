import json
from pathlib import Path

from sb.codex_trace import (
    facts_from_chat_archive_db,
    facts_from_dashboard_payload,
    facts_from_raw_codex_logs,
)
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
