from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


TOOLCALL_RE = re.compile(r"ToolCall:\s*(\w+)\s+(\{.*\})")
THREAD_RE = re.compile(r"thread_id=([0-9a-f-]{36})")
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[0-9:.]+Z?)\s+")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), UTC)
        except (TypeError, ValueError, OSError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _hash_payload(payload: object) -> str:
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _empty_bins() -> list[int]:
    return [0] * 24


def _tool_name_from_text(text: object) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    return raw.split(None, 1)[0]


def _command_sample(command: object, limit: int = 6) -> list[str]:
    if not isinstance(command, list):
        return []
    values = [str(item).strip() for item in command if str(item).strip()]
    return values[:limit]


def _normalize_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized.append(
            {
                "canonical_thread_id": str(row.get("canonical_thread_id") or ""),
                "platform": str(row.get("platform") or ""),
                "account_id": str(row.get("account_id") or ""),
                "ts": str(row.get("ts") or ""),
                "role": str(row.get("role") or ""),
                "text": str(row.get("text") or ""),
                "title": str(row.get("title") or "") if row.get("title") is not None else None,
                "source_id": str(row.get("source_id") or ""),
            }
        )
    normalized.sort(key=lambda item: (item["ts"], item["role"], item["text"]))
    return normalized


def _build_trace_facts(
    *,
    source_route: str,
    rows: list[dict[str, Any]],
    tool_summary: Mapping[str, Any] | None = None,
    completion_candidates: list[dict[str, Any]] | None = None,
    external_commitments: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hour_bins = _empty_bins()
    roles = Counter()
    tool_names = Counter()
    thread_ids: list[str] = []
    titles: list[str] = []
    platforms: list[str] = []
    account_ids: list[str] = []
    source_ids: list[str] = []
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    unanswered_user_messages = 0
    last_role = None

    for row in rows:
        ts = _parse_ts(row.get("ts"))
        if ts is not None:
            hour_bins[ts.hour] += 1
            first_ts = ts if first_ts is None or ts < first_ts else first_ts
            last_ts = ts if last_ts is None or ts > last_ts else last_ts
        role = str(row.get("role") or "")
        roles[role] += 1
        if role == "tool":
            tool = _tool_name_from_text(row.get("text"))
            if tool:
                tool_names[tool] += 1
        thread_id = str(row.get("canonical_thread_id") or "")
        if thread_id and thread_id not in thread_ids:
            thread_ids.append(thread_id)
        title = str(row.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
        platform = str(row.get("platform") or "").strip()
        if platform and platform not in platforms:
            platforms.append(platform)
        account_id = str(row.get("account_id") or "").strip()
        if account_id and account_id not in account_ids:
            account_ids.append(account_id)
        source_id = str(row.get("source_id") or "").strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
        if last_role == "user" and role not in {"assistant", "tool"}:
            unanswered_user_messages += 1
        last_role = role or last_role
    if last_role == "user":
        unanswered_user_messages += 1

    completion_candidates = [
        dict(item) for item in (completion_candidates or []) if isinstance(item, Mapping)
    ]
    external_commitments = [dict(item) for item in (external_commitments or []) if isinstance(item, Mapping)]
    warnings = [str(item) for item in (warnings or []) if str(item).strip()]
    evidence_refs = [dict(item) for item in (evidence_refs or []) if isinstance(item, Mapping)]

    open_commitments = [
        item for item in external_commitments if str(item.get("status") or "").strip().lower() in {"needs_action", "open"}
    ]
    completed_commitments = [
        item for item in external_commitments if str(item.get("status") or "").strip().lower() in {"completed", "done"}
    ]

    tool_summary = dict(tool_summary or {})
    request_user_input_count = _safe_int(tool_summary.get("request_user_input_count"), tool_names.get("request_user_input", 0))
    exec_command_count = _safe_int(tool_summary.get("exec_command_count"), tool_names.get("exec_command", 0))
    top_commands = []
    for item in tool_summary.get("commands") if isinstance(tool_summary.get("commands"), list) else []:
        if not isinstance(item, Mapping):
            continue
        command = item.get("command")
        top_commands.append(
            {
                "command": _command_sample(command),
                "count": _safe_int(item.get("count")),
                "cwd": str(item.get("cwd") or "") if item.get("cwd") is not None else None,
            }
        )

    trace_scope = {
        "thread_ids": thread_ids,
        "primary_thread_id": thread_ids[0] if thread_ids else None,
        "message_count": len(rows),
        "source_ids": source_ids,
        "window_start": _iso_utc(first_ts),
        "window_end": _iso_utc(last_ts),
    }
    session = {
        "platforms": platforms,
        "account_ids": account_ids,
        "titles": titles,
        "active_hours": sum(1 for count in hour_bins if count > 0),
        "source_route": source_route,
    }
    message_flow = {
        "message_count": len(rows),
        "user_count": roles.get("user", 0),
        "assistant_count": roles.get("assistant", 0),
        "tool_count": roles.get("tool", 0),
        "first_ts": _iso_utc(first_ts),
        "last_ts": _iso_utc(last_ts),
        "hour_bins": hour_bins,
        "unanswered_user_messages": unanswered_user_messages,
    }
    tool_use = {
        "total_calls": sum(tool_names.values()),
        "request_user_input_count": request_user_input_count,
        "exec_command_count": exec_command_count,
        "tool_names": dict(sorted(tool_names.items())),
        "top_commands": top_commands,
    }
    outcomes = {
        "completion_candidates": completion_candidates,
        "candidate_followups": [],
        "evidence_gaps": [{"reason": warning} for warning in warnings],
        "open_commitments": open_commitments,
        "completed_commitments": completed_commitments,
        "unresolved_blockers": [{"warning": warning} for warning in warnings],
    }
    artifacts = {
        "source_ids": source_ids,
        "snippet_refs": [],
    }

    payload = {
        "contract_version": "codex_trace_facts_v1",
        "source_route": source_route,
        "trace_scope": trace_scope,
        "session": session,
        "message_flow": message_flow,
        "tool_use": tool_use,
        "artifacts": artifacts,
        "outcomes": outcomes,
        "evidence_refs": evidence_refs,
    }
    payload["graphs"] = {
        "trace_scope": trace_scope,
        "session": session,
        "message_flow": message_flow,
        "tool_use": tool_use,
        "outcomes": outcomes,
    }
    payload["fact_digest"] = _hash_payload(
        {
            "trace_scope": trace_scope,
            "session": session,
            "message_flow": message_flow,
            "tool_use": tool_use,
            "outcomes": {
                "completion_candidate_ids": [
                    str(item.get("candidate_id") or item.get("external_item_id") or "")
                    for item in completion_candidates
                ],
                "open_commitment_ids": [
                    str(item.get("external_item_id") or item.get("candidate_id") or "")
                    for item in open_commitments
                ],
                "completed_commitment_ids": [
                    str(item.get("external_item_id") or item.get("candidate_id") or "")
                    for item in completed_commitments
                ],
                "evidence_gap_count": len(outcomes["evidence_gaps"]),
            },
        }
    )
    return payload


def core_trace_digest(facts: Mapping[str, Any]) -> str:
    payload = {
        "trace_scope": {
            "thread_ids": list((_coerce_mapping(facts.get("trace_scope"))).get("thread_ids", []))
            if isinstance((_coerce_mapping(facts.get("trace_scope"))).get("thread_ids"), list)
            else [],
            "message_count": _coerce_mapping(facts.get("trace_scope")).get("message_count"),
            "window_start": _coerce_mapping(facts.get("trace_scope")).get("window_start"),
            "window_end": _coerce_mapping(facts.get("trace_scope")).get("window_end"),
        },
        "message_flow": _coerce_mapping(facts.get("message_flow")),
        "tool_use": _coerce_mapping(facts.get("tool_use")),
    }
    return _hash_payload(payload)


def _coerce_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def facts_from_dashboard_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    timeline = payload.get("timeline") if isinstance(payload.get("timeline"), list) else []
    rows: list[dict[str, Any]] = []
    evidence_refs: list[dict[str, Any]] = []
    primary_thread_id = None
    chat_threads = payload.get("chat_threads") if isinstance(payload.get("chat_threads"), list) else []
    if chat_threads and isinstance(chat_threads[0], Mapping):
        primary_thread_id = str(chat_threads[0].get("thread_id") or "")
    for idx, event in enumerate(timeline):
        if not isinstance(event, Mapping):
            continue
        role = str(((event.get("meta") or {}) if isinstance(event.get("meta"), Mapping) else {}).get("role") or "")
        rows.append(
            {
                "canonical_thread_id": primary_thread_id or "dashboard_trace",
                "platform": "codex",
                "account_id": "dashboard",
                "ts": str(event.get("ts") or ""),
                "role": role if role in {"user", "assistant", "tool"} else "tool" if str(event.get("kind") or "") == "shell" else "assistant",
                "text": str(event.get("detail") or ""),
                "title": None,
                "source_id": str(event.get("source_path") or ""),
            }
        )
        evidence_refs.append(
            {
                "ref_kind": "timeline_event",
                "event_index": idx,
                "source_path": str(event.get("source_path") or "") if event.get("source_path") is not None else None,
                "ts": str(event.get("ts") or ""),
            }
        )
    for link in payload.get("artifact_links") if isinstance(payload.get("artifact_links"), list) else []:
        if not isinstance(link, Mapping):
            continue
        evidence_refs.append(
            {
                "ref_kind": "artifact_link",
                "label": str(link.get("label") or ""),
                "path": str(link.get("path") or ""),
            }
        )

    return _build_trace_facts(
        source_route="sb_dashboard",
        rows=rows,
        tool_summary=payload.get("tool_use_summary") if isinstance(payload.get("tool_use_summary"), Mapping) else {},
        completion_candidates=payload.get("task_completion_candidates") if isinstance(payload.get("task_completion_candidates"), list) else [],
        external_commitments=payload.get("external_commitments") if isinstance(payload.get("external_commitments"), list) else [],
        warnings=payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
        evidence_refs=evidence_refs,
    )


def load_chat_archive_rows(
    db_path: str | Path,
    *,
    canonical_thread_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    query = [
        "SELECT canonical_thread_id, platform, account_id, ts, role, text, title, source_id",
        "FROM messages",
    ]
    params: list[object] = []
    if canonical_thread_id:
        query.append("WHERE canonical_thread_id = ?")
        params.append(canonical_thread_id)
    query.append("ORDER BY ts ASC, rowid ASC")
    if limit is not None:
        query.append("LIMIT ?")
        params.append(int(limit))
    with sqlite3.connect(str(Path(db_path).expanduser())) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(" ".join(query), params).fetchall()
    return [dict(row) for row in rows]


def facts_from_chat_archive_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = _normalize_rows(rows)
    evidence_refs = [
        {
            "ref_kind": "chat_archive_message",
            "canonical_thread_id": row["canonical_thread_id"],
            "ts": row["ts"],
            "role": row["role"],
            "source_id": row["source_id"],
        }
        for row in normalized
    ]
    return _build_trace_facts(source_route="chat_archive", rows=normalized, evidence_refs=evidence_refs)


def facts_from_chat_archive_db(
    db_path: str | Path,
    *,
    canonical_thread_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    return facts_from_chat_archive_rows(
        load_chat_archive_rows(db_path, canonical_thread_id=canonical_thread_id, limit=limit)
    )


def _parse_history_rows(history_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not history_path.exists():
        return rows
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(
            {
                "canonical_thread_id": str(obj.get("session_id") or "unknown_session"),
                "platform": "codex",
                "account_id": "local",
                "ts": str(obj.get("ts") or ""),
                "role": "user",
                "text": str(obj.get("text") or ""),
                "title": None,
                "source_id": "codex_history_jsonl",
            }
        )
    return rows


def _parse_tool_rows(log_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not log_path.exists():
        return rows
    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = ANSI_RE.sub("", raw_line).rstrip()
        match = TOOLCALL_RE.search(line)
        if not match:
            continue
        ts_match = TS_RE.match(line)
        thread_match = THREAD_RE.search(line)
        rows.append(
            {
                "canonical_thread_id": thread_match.group(1) if thread_match else "codex_tooling",
                "platform": "codex",
                "account_id": "local",
                "ts": ts_match.group(1) if ts_match else "",
                "role": "tool",
                "text": f"{match.group(1)} {match.group(2)}",
                "title": None,
                "source_id": "codex_tui_log",
            }
        )
    return rows


def facts_from_raw_codex_logs(
    *,
    history_path: str | Path,
    log_path: str | Path,
    canonical_thread_id: str | None = None,
) -> dict[str, Any]:
    rows = _parse_history_rows(Path(history_path).expanduser()) + _parse_tool_rows(Path(log_path).expanduser())
    if canonical_thread_id:
        rows = [row for row in rows if str(row.get("canonical_thread_id") or "") == canonical_thread_id]
    normalized = _normalize_rows(rows)
    evidence_refs = [
        {
            "ref_kind": "raw_codex_log",
            "canonical_thread_id": row["canonical_thread_id"],
            "ts": row["ts"],
            "role": row["role"],
            "source_id": row["source_id"],
        }
        for row in normalized
    ]
    return _build_trace_facts(source_route="raw_codex_logs", rows=normalized, evidence_refs=evidence_refs)
