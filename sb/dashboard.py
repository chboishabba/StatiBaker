from __future__ import annotations

import json
import os
import re
import shlex
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date as date_cls, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
RESOLVER_ID_RE = re.compile(r"resolver_([0-9a-fA-F-]{8,})\.json$")
WEEKLY_SUMMARY_KEYS = (
    "chat_messages",
    "chat_threads",
    "chat_switches",
    "shell_commands",
    "input_events",
    "input_keys_total",
    "input_mouse_total",
    "window_focus_events",
    "activity_events",
    "git_commits",
    "git_branch_events",
    "pr_events",
    "pr_received",
    "pr_commented",
    "pr_merged",
    "timeline_events",
)
CHAT_FLOW_COLORS = (
    "#0b6e4f",
    "#1d4ed8",
    "#a16207",
    "#9d174d",
    "#0f766e",
    "#7c3aed",
    "#b45309",
    "#be123c",
    "#047857",
    "#1e40af",
    "#7c2d12",
    "#4c1d95",
)


@dataclass
class TimelineEvent:
    dt: datetime
    kind: str
    detail: str
    source_path: str
    meta: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "ts": _iso_utc(self.dt),
            "kind": self.kind,
            "detail": self.detail,
            "source_path": self.source_path,
            "hour": self.dt.hour,
        }
        if self.meta:
            payload["meta"] = self.meta
        return payload


def _iso_utc(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), UTC)
        except (ValueError, OSError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromtimestamp(float(text), UTC)
        except (ValueError, OSError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: int, denominator: int, digits: int = 2) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), digits)


def _display_title(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "(no title)"


def _title_from_first_user_preview(value: object, max_chars: int = 96) -> str:
    preview = _collapse_ws(value)
    if not preview:
        return "(no title)"
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "..."
    return f"(untitled) {preview}"


def _resolve_thread_title(title: object, first_user_preview: object) -> str:
    title_text = str(title or "").strip()
    if title_text:
        return title_text
    return _title_from_first_user_preview(first_user_preview)


def _origin_from_source_ids(source_ids: dict[str, int], fallback_source: str = "unknown") -> str:
    if not source_ids:
        return fallback_source
    keys = [str(key).strip().lower() for key in source_ids if str(key).strip()]
    if not keys:
        return fallback_source
    if any(key.startswith("codex_") for key in keys):
        return "codex-ingest"
    if any("resolver" in key for key in keys):
        return "resolver-sync"
    if any("chat_export" in key for key in keys):
        return "chat-export-json"
    first = sorted(keys)[0]
    prefix = first.split("_", 1)[0]
    return f"source:{prefix}" if prefix else fallback_source


def _thread_in_scope(
    *,
    thread_id: str,
    thread_title: str,
    thread_scope: dict[str, str],
    thread_ids: set[str],
    title_filters: list[str],
) -> bool:
    if not thread_scope:
        return True
    if thread_id in thread_ids:
        return True
    lowered = thread_title.lower()
    if lowered and any(token in lowered for token in title_filters):
        return True
    return False


def _short_id(value: object, width: int = 8) -> str:
    text = str(value or "").strip()
    if len(text) <= width:
        return text
    return text[:width]


def _collapse_ws(value: object) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", text).strip()


def _preview_text(value: object, max_chars: int = 220) -> str:
    text = _collapse_ws(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _render_foldable_text(text: object, limit: int = 180) -> str:
    collapsed = _collapse_ws(text)
    if not collapsed:
        return ""
    if len(collapsed) <= limit:
        return escape(collapsed)
    short = escape(collapsed[:limit].rstrip() + "...")
    full = escape(collapsed)
    return f"<details><summary>{short}</summary><pre>{full}</pre></details>"


def _source_kind(source_path: str) -> str:
    lowered = source_path.lower()
    if "chat-export-structurer" in lowered and ".sqlite" in lowered:
        return "sqlite"
    if "/chat_exports/" in lowered:
        return "chat_exports"
    if "__context/last_sync" in lowered:
        return "resolver"
    if "/logs/" in lowered:
        return "logs"
    if "activity_ledger.json" in lowered:
        return "activity"
    if "/outputs/" in lowered:
        return "outputs"
    return "other"


def _source_label(source_path: str) -> str:
    labels = {
        "sqlite": "sqlite",
        "chat_exports": "chat exports",
        "resolver": "resolver",
        "logs": "run logs",
        "activity": "activity",
        "outputs": "outputs",
        "other": "other",
    }
    key = str(source_path or "").strip()
    kind = key if key in labels else _source_kind(key)
    return labels.get(kind, kind)


def _looks_like_python_executable(token: str) -> bool:
    base = os.path.basename(token).lower()
    return base == "python" or base.startswith("python")


def _command_family(command: str) -> str:
    text = str(command or "").strip()
    if not text:
        return "(empty)"
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    if not tokens:
        return "(empty)"

    first = os.path.basename(tokens[0])
    if _looks_like_python_executable(first):
        if len(tokens) >= 3 and tokens[1] == "-m":
            return f"python -m {tokens[2]}"
        if len(tokens) >= 2 and not tokens[1].startswith("-"):
            return f"python {os.path.basename(tokens[1])}"
        return "python"

    first_lower = first.lower()
    if first_lower in {"bash", "sh"}:
        if len(tokens) >= 2 and tokens[1] in {"-c", "-lc"}:
            return f"{first_lower} -c"
        if len(tokens) >= 2:
            return f"{first_lower} {os.path.basename(tokens[1])}"
        return first_lower

    if first_lower in {"git", "npm", "pnpm", "yarn", "cargo", "uv"}:
        if len(tokens) >= 2:
            return f"{first_lower} {tokens[1]}"
        return first_lower

    return first_lower


def _extract_cd_dirs(command: str) -> list[str]:
    text = str(command or "")
    paths: list[str] = []
    for match in re.finditer(r"(?:^|[;&|])\s*cd\s+([^\s;&|]+)", text):
        raw = match.group(1).strip().strip("\"'")
        if raw:
            paths.append(raw)
    return paths


def _rg_mode_and_diff(command: str) -> tuple[str, str]:
    text = str(command or "").strip()
    if not text:
        return "other", "(empty)"
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    if not tokens:
        return "other", "(empty)"
    if os.path.basename(tokens[0]).lower() != "rg":
        return "other", _preview_text(text, max_chars=120)

    if "--files" in tokens:
        globs: list[str] = []
        residual: list[str] = []
        i = 1
        while i < len(tokens):
            token = tokens[i]
            if token in {"-g", "--glob"}:
                if i + 1 < len(tokens):
                    globs.append(tokens[i + 1])
                    i += 2
                    continue
                i += 1
                continue
            if token.startswith("--glob="):
                globs.append(token.split("=", 1)[1])
                i += 1
                continue
            if token.startswith("-g") and token != "-g":
                globs.append(token[2:])
                i += 1
                continue
            if token == "--files":
                i += 1
                continue
            if token.startswith("-"):
                i += 1
                continue
            residual.append(token)
            i += 1
        parts: list[str] = []
        if globs:
            parts.append(", ".join(globs[:5]) + (" ..." if len(globs) > 5 else ""))
        if residual:
            parts.append(" ".join(residual[:8]) + (" ..." if len(residual) > 8 else ""))
        return "--files", " | ".join(parts) if parts else "(all files)"

    if "-n" in tokens or "--line-number" in tokens:
        non_option = [token for token in tokens[1:] if token and not token.startswith("-")]
        if non_option:
            detail = " ".join(non_option[:10]) + (" ..." if len(non_option) > 10 else "")
        else:
            detail = "(pattern omitted)"
        return "-n", detail

    detail = _preview_text(" ".join(tokens[1:]), max_chars=120) or "(no args)"
    return "other", detail


def _parse_tool_message(text: str) -> tuple[str, dict[str, Any]] | None:
    payload_text = str(text or "").strip()
    if not payload_text:
        return None
    match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+(\{.*\})$", payload_text, re.S)
    if not match:
        return None
    tool_name = match.group(1)
    raw_json = match.group(2)
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return tool_name, payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _parse_convo_scope(convo_ids_path: Path) -> dict[str, str]:
    scope: dict[str, str] = {}
    if not convo_ids_path.exists():
        return scope
    for line in convo_ids_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cols = [part.strip() for part in stripped.strip("|").split("|")]
        if len(cols) < 2:
            continue
        conv_id = cols[0]
        title = cols[1]
        if UUID_RE.match(conv_id):
            scope[conv_id.lower()] = title
    return scope


def _chat_rows_sqlite(
    db_path: Path,
    date_text: str,
    thread_scope: dict[str, str],
) -> tuple[list[TimelineEvent], dict[str, Any], str | None]:
    if not db_path.exists():
        return [], {}, None

    thread_ids = set(thread_scope.keys())
    title_filters = [title.lower() for title in thread_scope.values() if title]
    events: list[TimelineEvent] = []
    thread_stats: dict[str, dict[str, Any]] = {}
    uri = f"file:{db_path.resolve()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return [], {}, None

    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT canonical_thread_id, title, role, ts, text, source_id
                FROM messages
                WHERE substr(ts, 1, 10) = ?
                ORDER BY ts ASC
                """,
                (date_text,),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            return [], {}, None
    finally:
        conn.close()

    first_user_preview: dict[str, str] = {}
    for canonical_thread_id, title, role, ts, text, _source_id in rows:
        thread_id = str(canonical_thread_id or "").lower()
        thread_title = str(title or "").strip()
        if not _thread_in_scope(
            thread_id=thread_id,
            thread_title=thread_title,
            thread_scope=thread_scope,
            thread_ids=thread_ids,
            title_filters=title_filters,
        ):
            continue
        thread_key = thread_id or "unknown"
        role_text = str(role or "unknown").strip().lower()
        if role_text != "user" or thread_key in first_user_preview:
            continue
        preview = _preview_text(text, max_chars=120)
        if preview:
            first_user_preview[thread_key] = preview

    for canonical_thread_id, title, role, ts, text, source_id in rows:
        dt = _parse_ts(ts)
        if dt is None:
            continue
        thread_id = str(canonical_thread_id or "").lower()
        thread_key = thread_id or "unknown"
        thread_title = str(title or "").strip()
        if not _thread_in_scope(
            thread_id=thread_id,
            thread_title=thread_title,
            thread_scope=thread_scope,
            thread_ids=thread_ids,
            title_filters=title_filters,
        ):
            continue

        role_text = str(role or "unknown")
        char_count = len(str(text or ""))
        scope_title = str(thread_scope.get(thread_id, "")).strip()
        raw_title = thread_title or scope_title
        resolved_title = _resolve_thread_title(raw_title, first_user_preview.get(thread_key, ""))
        source_id_text = str(source_id or "").strip()
        detail = f"chat role={role_text} chars={char_count}"
        source = f"{db_path}#{source_id_text}" if source_id_text else str(db_path)
        meta = {
            "thread_id": thread_id,
            "thread_title": resolved_title,
            "thread_title_raw": raw_title,
            "thread_first_user_preview": first_user_preview.get(thread_key, ""),
            "role": role_text,
            "chars": char_count,
            "preview": _preview_text(text, max_chars=220),
            "source_id": source_id_text,
        }
        events.append(
            TimelineEvent(
                dt=dt,
                kind="chat",
                detail=detail,
                source_path=source,
                meta=meta,
            )
        )
        stat = thread_stats.setdefault(
            thread_key,
            {
                "thread_id": thread_id,
                "title": raw_title,
                "title_resolved": resolved_title,
                "first_user_preview": first_user_preview.get(thread_key, ""),
                "message_count": 0,
                "first_ts": _iso_utc(dt),
                "last_ts": _iso_utc(dt),
                "roles": {},
                "source_ids": {},
                "origin": "unknown",
            },
        )
        if not stat.get("title"):
            stat["title"] = raw_title
        if not stat.get("first_user_preview"):
            stat["first_user_preview"] = first_user_preview.get(thread_key, "")
        stat["message_count"] += 1
        stat["first_ts"] = min(stat["first_ts"], _iso_utc(dt))
        stat["last_ts"] = max(stat["last_ts"], _iso_utc(dt))
        roles = stat["roles"]
        roles[role_text] = roles.get(role_text, 0) + 1
        if source_id_text:
            source_counts = stat["source_ids"]
            source_counts[source_id_text] = source_counts.get(source_id_text, 0) + 1

    resolved_title_by_thread: dict[str, str] = {}
    origin_by_thread: dict[str, str] = {}
    for key, stat in thread_stats.items():
        resolved = _resolve_thread_title(stat.get("title"), stat.get("first_user_preview"))
        stat["title_resolved"] = resolved
        origin = _origin_from_source_ids(stat.get("source_ids") or {}, fallback_source="sqlite")
        stat["origin"] = origin
        resolved_title_by_thread[key] = resolved
        origin_by_thread[key] = origin

    for event in events:
        if not isinstance(event.meta, dict):
            continue
        thread_key = str(event.meta.get("thread_id") or "").lower() or "unknown"
        if not _collapse_ws(event.meta.get("thread_title")):
            event.meta["thread_title"] = resolved_title_by_thread.get(thread_key, "(no title)")
        event.meta["thread_origin"] = origin_by_thread.get(thread_key, "unknown")

    return events, thread_stats, "sqlite"


def _iter_export_messages(export_path: Path) -> tuple[str | None, str, list[dict[str, Any]]]:
    try:
        payload = json.loads(export_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "", []
    if not isinstance(payload, dict):
        return None, "", []
    conversation_id = payload.get("conversation_id")
    title = str(payload.get("title") or "")
    mapping = payload.get("mapping")
    if not isinstance(mapping, dict):
        return str(conversation_id) if conversation_id else None, title, []
    items: list[dict[str, Any]] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        role = (message.get("author") or {}).get("role")
        content = message.get("content") or {}
        parts = content.get("parts") if isinstance(content, dict) else None
        text_value = ""
        if isinstance(parts, list):
            text_value = "\n".join(str(p) for p in parts if p is not None)
        elif isinstance(parts, str):
            text_value = parts
        chars = len(text_value)
        items.append(
            {
                "role": str(role or "unknown"),
                "create_time": message.get("create_time"),
                "chars": chars,
                "preview": _preview_text(text_value, max_chars=220),
            }
        )
    return str(conversation_id) if conversation_id else None, title, items


def _chat_rows_exports(
    exports_dir: Path,
    date_text: str,
    thread_scope: dict[str, str],
) -> tuple[list[TimelineEvent], dict[str, Any], str | None]:
    if not exports_dir.exists():
        return [], {}, None

    day = date_cls.fromisoformat(date_text)
    day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    thread_ids = set(thread_scope.keys())
    title_filters = [title.lower() for title in thread_scope.values() if title]

    events: list[TimelineEvent] = []
    thread_stats: dict[str, dict[str, Any]] = {}
    for export_path in sorted(exports_dir.glob("*.json")):
        conversation_id, title, items = _iter_export_messages(export_path)
        if not items:
            continue
        conv_id = (conversation_id or "").lower()
        if not _thread_in_scope(
            thread_id=conv_id,
            thread_title=title,
            thread_scope=thread_scope,
            thread_ids=thread_ids,
            title_filters=title_filters,
        ):
            continue

        thread_key = conv_id or export_path.stem
        first_user_preview = ""
        for item in items:
            if str(item.get("role") or "").lower() == "user":
                first_user_preview = _collapse_ws(item.get("preview"))
                if first_user_preview:
                    break
        resolved_title = _resolve_thread_title(title, first_user_preview)
        for item in items:
            dt = _parse_ts(item.get("create_time"))
            if dt is None or not (day_start <= dt < day_end):
                continue
            role_text = str(item.get("role") or "unknown")
            char_count = _safe_int(item.get("chars"))
            detail = f"chat role={role_text} chars={char_count}"
            meta = {
                "thread_id": conv_id,
                "thread_title": resolved_title,
                "thread_title_raw": title,
                "thread_first_user_preview": first_user_preview,
                "role": role_text,
                "chars": char_count,
                "preview": _collapse_ws(item.get("preview")),
                "thread_origin": "chat-export-json",
            }
            events.append(
                TimelineEvent(
                    dt=dt,
                    kind="chat",
                    detail=detail,
                    source_path=str(export_path),
                    meta=meta,
                )
            )
            stat = thread_stats.setdefault(
                thread_key,
                {
                    "thread_id": conv_id,
                    "title": title,
                    "title_resolved": resolved_title,
                    "first_user_preview": first_user_preview,
                    "message_count": 0,
                    "first_ts": _iso_utc(dt),
                    "last_ts": _iso_utc(dt),
                    "roles": {},
                    "source_ids": {"chat_export_json": 0},
                    "origin": "chat-export-json",
                },
            )
            stat["message_count"] += 1
            stat["first_ts"] = min(stat["first_ts"], _iso_utc(dt))
            stat["last_ts"] = max(stat["last_ts"], _iso_utc(dt))
            roles = stat["roles"]
            roles[role_text] = roles.get(role_text, 0) + 1
            stat["source_ids"]["chat_export_json"] += 1

    for stat in thread_stats.values():
        stat["title_resolved"] = _resolve_thread_title(stat.get("title"), stat.get("first_user_preview"))
        stat["origin"] = _origin_from_source_ids(stat.get("source_ids") or {}, fallback_source="chat_exports")

    return events, thread_stats, "chat_exports"


def _chat_rows_resolver(
    last_sync_dir: Path,
    date_text: str,
    thread_scope: dict[str, str],
) -> tuple[list[TimelineEvent], dict[str, Any], str | None]:
    if not last_sync_dir.exists():
        return [], {}, None

    day = date_cls.fromisoformat(date_text)
    day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    thread_ids = set(thread_scope.keys())

    events: list[TimelineEvent] = []
    thread_stats: dict[str, dict[str, Any]] = {}
    for path in sorted(last_sync_dir.glob("*_resolver_*.json")):
        match = RESOLVER_ID_RE.search(path.name)
        if not match:
            continue
        thread_id = match.group(1).lower()
        if thread_scope and thread_id not in thread_ids:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        turns = payload.get("web_recent_turns")
        if not isinstance(turns, list):
            continue
        title = (payload.get("web_recent_turns_meta") or {}).get("title") or thread_scope.get(thread_id, "")
        thread_key = thread_id or "unknown"
        first_user_preview = ""
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            if str(turn.get("role") or "").strip().lower() != "user":
                continue
            first_user_preview = _preview_text(turn.get("text"), max_chars=120)
            if first_user_preview:
                break
        resolved_title = _resolve_thread_title(title, first_user_preview)
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            dt = _parse_ts(turn.get("ts_utc") or turn.get("ts"))
            if dt is None or not (day_start <= dt < day_end):
                continue
            role_text = str(turn.get("role") or "unknown")
            char_count = len(str(turn.get("text") or ""))
            detail = f"chat role={role_text} chars={char_count}"
            meta = {
                "thread_id": thread_id,
                "thread_title": resolved_title,
                "thread_title_raw": title,
                "thread_first_user_preview": first_user_preview,
                "role": role_text,
                "chars": char_count,
                "preview": _preview_text(turn.get("text"), max_chars=220),
                "thread_origin": "resolver-sync",
            }
            events.append(TimelineEvent(dt=dt, kind="chat", detail=detail, source_path=str(path), meta=meta))
            stat = thread_stats.setdefault(
                thread_key,
                {
                    "thread_id": thread_id,
                    "title": title,
                    "title_resolved": resolved_title,
                    "first_user_preview": first_user_preview,
                    "message_count": 0,
                    "first_ts": _iso_utc(dt),
                    "last_ts": _iso_utc(dt),
                    "roles": {},
                    "source_ids": {"resolver_snapshot": 0},
                    "origin": "resolver-sync",
                },
            )
            stat["message_count"] += 1
            stat["first_ts"] = min(stat["first_ts"], _iso_utc(dt))
            stat["last_ts"] = max(stat["last_ts"], _iso_utc(dt))
            roles = stat["roles"]
            roles[role_text] = roles.get(role_text, 0) + 1
            stat["source_ids"]["resolver_snapshot"] += 1

    for stat in thread_stats.values():
        stat["title_resolved"] = _resolve_thread_title(stat.get("title"), stat.get("first_user_preview"))
        stat["origin"] = _origin_from_source_ids(stat.get("source_ids") or {}, fallback_source="resolver")
    return events, thread_stats, "resolver"


def _load_chat_events(
    date_text: str,
    thread_scope: dict[str, str],
    chat_db_path: Path,
    exports_dir: Path,
    last_sync_dir: Path,
) -> tuple[list[TimelineEvent], list[dict[str, Any]], str, list[str]]:
    warnings: list[str] = []

    events, stats, source = _chat_rows_sqlite(chat_db_path, date_text, thread_scope)
    if not events:
        events, stats, source = _chat_rows_exports(exports_dir, date_text, thread_scope)
    if not events:
        events, stats, source = _chat_rows_resolver(last_sync_dir, date_text, thread_scope)
    if not events:
        warnings.append("No chat events found for this date in sqlite, chat exports, or resolver files.")
        source = "none"

    thread_activity = sorted(
        stats.values(),
        key=lambda row: row.get("message_count", 0),
        reverse=True,
    )
    return events, thread_activity, source, warnings


def _load_tool_use_summary_sqlite(
    *,
    db_path: Path,
    date_text: str,
    thread_scope: dict[str, str],
    top_families: int = 20,
    top_variants: int = 6,
    top_dirs: int = 20,
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "source": "none",
            "total_tool_messages": 0,
            "exec_command_count": 0,
            "unique_commands": 0,
            "families": [],
            "top_dirs": [],
            "warnings": ["Tool-use summary unavailable: sqlite archive not found."],
        }

    thread_ids = set(thread_scope.keys())
    title_filters = [title.lower() for title in thread_scope.values() if title]
    uri = f"file:{db_path.resolve()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return {
            "source": "none",
            "total_tool_messages": 0,
            "exec_command_count": 0,
            "unique_commands": 0,
            "families": [],
            "top_dirs": [],
            "warnings": ["Tool-use summary unavailable: failed to open sqlite archive."],
        }

    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT canonical_thread_id, title, text
                FROM messages
                WHERE substr(ts, 1, 10) = ?
                  AND role = 'tool'
                  AND text IS NOT NULL
                  AND TRIM(text) <> ''
                ORDER BY ts ASC
                """,
                (date_text,),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            return {
                "source": "none",
                "total_tool_messages": 0,
                "exec_command_count": 0,
                "unique_commands": 0,
                "families": [],
                "top_dirs": [],
                "warnings": [
                    "Tool-use summary unavailable: sqlite query failed for this date."
                ],
            }
    finally:
        conn.close()

    total_tool_messages = 0
    exec_command_count = 0
    parse_failures = 0
    all_command_counts: Counter[str] = Counter()
    dir_counts: Counter[str] = Counter()
    family_totals: Counter[str] = Counter()
    family_variants: dict[str, Counter[str]] = {}
    family_dirs: dict[str, Counter[str]] = {}

    for canonical_thread_id, title, text in rows:
        thread_id = str(canonical_thread_id or "").lower()
        thread_title = str(title or "").strip()
        in_scope = True
        if thread_scope:
            in_scope = thread_id in thread_ids
            if not in_scope and thread_title:
                lowered = thread_title.lower()
                in_scope = any(token in lowered for token in title_filters)
        if not in_scope:
            continue

        total_tool_messages += 1
        parsed = _parse_tool_message(str(text or ""))
        if not parsed:
            parse_failures += 1
            continue

        tool_name, payload = parsed
        if tool_name != "exec_command":
            continue

        command = str(payload.get("cmd") or "").strip()
        if not command:
            continue
        exec_command_count += 1
        all_command_counts[command] += 1

        family = _command_family(command)
        family_totals[family] += 1
        family_variants.setdefault(family, Counter())[command] += 1

        dirs = []
        workdir = str(payload.get("workdir") or "").strip()
        if workdir:
            dirs.append(workdir)
        dirs.extend(_extract_cd_dirs(command))
        for directory in dirs:
            dir_counts[directory] += 1
            family_dirs.setdefault(family, Counter())[directory] += 1

    families: list[dict[str, Any]] = []
    for family, count in family_totals.most_common(top_families):
        variants = family_variants.get(family, Counter())
        family_dir_counter = family_dirs.get(family, Counter())
        variant_rows = []
        for variant_command, variant_count in variants.most_common(top_variants):
            variant_dirs = []
            workdir = []
            # Capture directories directly referenced by this command for display.
            extracted = _extract_cd_dirs(variant_command)
            if extracted:
                workdir.extend(extracted)
            variant_rows.append(
                {
                    "command": variant_command,
                    "count": int(variant_count),
                    "dirs_hint": workdir[:5],
                }
            )

        variant_groups: list[dict[str, Any]] = []
        if family == "rg":
            group_totals: Counter[str] = Counter()
            group_details: dict[str, Counter[str]] = {}
            for variant_command, variant_count in variants.items():
                mode, diff = _rg_mode_and_diff(variant_command)
                group_totals[mode] += int(variant_count)
                group_details.setdefault(mode, Counter())[diff] += int(variant_count)
            for mode, mode_count in group_totals.most_common():
                detail_rows = [
                    {"detail": detail, "count": int(detail_count)}
                    for detail, detail_count in group_details.get(mode, Counter()).most_common(top_variants)
                ]
                variant_groups.append(
                    {
                        "group": mode,
                        "count": int(mode_count),
                        "variants": detail_rows,
                    }
                )

        families.append(
            {
                "family": family,
                "count": int(count),
                "unique_variants": len(variants),
                "variants": variant_rows,
                "variant_groups": variant_groups,
                "top_dirs": [
                    {"path": path, "count": int(path_count)}
                    for path, path_count in family_dir_counter.most_common(5)
                ],
            }
        )

    warnings: list[str] = []
    if total_tool_messages == 0:
        warnings.append("No tool messages found for this date/scope in sqlite.")
    if parse_failures:
        warnings.append(f"{parse_failures} tool messages were not parseable as structured tool payloads.")

    return {
        "source": "sqlite",
        "total_tool_messages": int(total_tool_messages),
        "exec_command_count": int(exec_command_count),
        "unique_commands": int(len(all_command_counts)),
        "families": families,
        "top_dirs": [
            {"path": path, "count": int(count)}
            for path, count in dir_counts.most_common(top_dirs)
        ],
        "warnings": warnings,
    }


def _load_cli_events(path: Path) -> tuple[list[TimelineEvent], int]:
    events: list[TimelineEvent] = []
    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        cmd_hash = row.get("cmd_hash") or "missing_cmd_hash"
        detail = f"shell exit={row.get('exit')} duration_ms={row.get('duration_ms')} cmd_hash={cmd_hash}"
        events.append(TimelineEvent(dt=dt, kind="shell", detail=detail, source_path=str(path)))
    return events, len(events)


def _load_input_events(path: Path) -> tuple[list[TimelineEvent], int, int, int]:
    events: list[TimelineEvent] = []
    key_total = 0
    mouse_total = 0
    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        keys = row.get("keys") if isinstance(row.get("keys"), dict) else {}
        mouse = row.get("mouse") if isinstance(row.get("mouse"), dict) else {}
        keys_count = sum(_safe_int(value) for value in keys.values())
        mouse_count = sum(_safe_int(value) for value in mouse.values())
        key_total += keys_count
        mouse_total += mouse_count
        detail = f"input focus={row.get('focus_app')} keys={keys_count} mouse={mouse_count}"
        events.append(TimelineEvent(dt=dt, kind="input", detail=detail, source_path=str(path)))
    return events, len(events), key_total, mouse_total


def _load_window_events(path: Path) -> tuple[list[TimelineEvent], int]:
    events: list[TimelineEvent] = []
    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        detail = (
            f"window app={row.get('app_id')} duration_ms={row.get('duration_ms')} "
            f"title_hash={row.get('window_title_hash')}"
        )
        events.append(TimelineEvent(dt=dt, kind="window", detail=detail, source_path=str(path)))
    return events, len(events)


def _load_git_events(path: Path) -> tuple[list[TimelineEvent], int]:
    events: list[TimelineEvent] = []
    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        short_hash = str(row.get("hash") or "")[:7]
        detail = f"git commit={short_hash} repo={row.get('repo')}"
        events.append(TimelineEvent(dt=dt, kind="git", detail=detail, source_path=str(path)))
    return events, len(events)


def _load_git_branch_events(path: Path) -> tuple[list[TimelineEvent], int]:
    events: list[TimelineEvent] = []
    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        detail = (
            f"git_branch event_type={row.get('event_type')} ref={row.get('ref')} "
            f"repo={row.get('repo')}"
        )
        events.append(TimelineEvent(dt=dt, kind="git_branch", detail=detail, source_path=str(path)))
    return events, len(events)


def _load_pr_events(path: Path) -> tuple[list[TimelineEvent], int, dict[str, int]]:
    events: list[TimelineEvent] = []
    counts: dict[str, int] = {
        "pr_received": 0,
        "pr_commented": 0,
        "pr_merged": 0,
    }
    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        event_type = str(row.get("event_type") or "unknown")
        detail = (
            f"pr event_type={event_type} repo={row.get('repo')} "
            f"pr=#{row.get('pr_number')}"
        )
        events.append(TimelineEvent(dt=dt, kind="pr", detail=detail, source_path=str(path)))
        if event_type in counts:
            counts[event_type] += 1
    return events, len(events), counts


def _load_activity_events(path: Path) -> tuple[list[TimelineEvent], int]:
    if not path.exists():
        return [], 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], 0
    if not isinstance(payload, dict):
        return [], 0
    raw_events = payload.get("activity_events")
    if not isinstance(raw_events, list):
        return [], 0
    events: list[TimelineEvent] = []
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        dt = _parse_ts(item.get("t_start") or item.get("t_end"))
        if dt is None:
            continue
        t_end = _parse_ts(item.get("t_end"))
        duration_s = 0
        if t_end is not None:
            duration_s = max(0, int((t_end - dt).total_seconds()))
        detail = f"activity app={item.get('primary_app')} duration_s={duration_s}"
        events.append(TimelineEvent(dt=dt, kind="activity", detail=detail, source_path=str(path)))
    return events, len(events)


def _collect_artifact_links(
    repo_root: Path,
    runs_output_dir: Path,
    context_root: Path,
    thread_scope: dict[str, str],
    include_all_chat: bool = False,
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []

    for name in ("daily_brief.md", "retrospective.md", "state.json", "drift.json", "activity_ledger.json"):
        path = runs_output_dir / name
        if path.exists():
            links.append({"label": name, "path": str(path)})

    for path in (
        repo_root / "StatiBaker/COMPACTIFIED_CONTEXT.md",
        context_root / "CONTEXT.md",
        context_root / "COMPACTIFIED_CONTEXT.md",
    ):
        if path.exists():
            links.append({"label": path.name, "path": str(path)})

    last_sync = context_root / "last_sync"
    if last_sync.exists():
        prefixes = [thread_id.split("-")[0].lower() for thread_id in thread_scope]
        for file_path in sorted(last_sync.iterdir()):
            if not file_path.is_file():
                continue
            lowered = file_path.name.lower()
            if "context_refresh" in lowered:
                links.append({"label": file_path.name, "path": str(file_path)})
                continue
            if include_all_chat and (
                "_resolver_" in lowered
                or "_latest_" in lowered
                or lowered.endswith(".tsv")
            ):
                links.append({"label": file_path.name, "path": str(file_path)})
                continue
            if any(prefix in lowered for prefix in prefixes):
                links.append({"label": file_path.name, "path": str(file_path)})

    deduped: list[dict[str, str]] = []
    seen = set()
    for item in links:
        key = item["path"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _empty_bins() -> list[int]:
    return [0 for _ in range(24)]


def _increment_bin(bins: list[int], dt: datetime) -> None:
    bins[dt.hour] += 1


def _build_chat_flow(
    chat_events: list[TimelineEvent],
    *,
    render_limit: int = 480,
) -> dict[str, Any]:
    ordered = sorted((event for event in chat_events if event.kind == "chat"), key=lambda item: item.dt)
    total_messages = len(ordered)
    if total_messages == 0:
        return {
            "message_count": 0,
            "thread_count": 0,
            "active_hours": 0,
            "switch_count": 0,
            "switch_rate": 0.0,
            "switch_opportunities": 0,
            "messages_per_hour_active": 0.0,
            "messages_per_hour_day": 0.0,
            "messages_per_chat": 0.0,
            "dominant_thread_share": 0.0,
            "first_ts": "",
            "last_ts": "",
            "hour_bins": _empty_bins(),
            "threads": [],
            "waterfall": [],
            "waterfall_render_limit": max(1, render_limit),
            "waterfall_truncated": False,
        }

    thread_counts: Counter[str] = Counter()
    thread_titles: dict[str, str] = {}
    thread_order: dict[str, int] = {}
    hour_bins = _empty_bins()
    switch_count = 0
    prev_thread_key = ""
    waterfall_all: list[dict[str, Any]] = []

    for event in ordered:
        meta = event.meta if isinstance(event.meta, dict) else {}
        raw_thread_id = str(meta.get("thread_id") or "").strip().lower()
        thread_title = _resolve_thread_title(
            meta.get("thread_title"),
            meta.get("thread_first_user_preview"),
        )
        thread_key = raw_thread_id or f"untitled:{thread_title.lower()}"
        if thread_key not in thread_order:
            thread_order[thread_key] = len(thread_order)
            thread_titles[thread_key] = thread_title

        thread_counts[thread_key] += 1
        _increment_bin(hour_bins, event.dt)

        switched = bool(prev_thread_key) and prev_thread_key != thread_key
        if switched:
            switch_count += 1
        prev_thread_key = thread_key

        color_index = thread_order[thread_key] % len(CHAT_FLOW_COLORS)
        role_text = str(meta.get("role") or "unknown").strip().lower() or "unknown"
        waterfall_all.append(
            {
                "ts": _iso_utc(event.dt),
                "hour": event.dt.hour,
                "thread_id": raw_thread_id,
                "thread_key": thread_key,
                "thread_title": thread_titles[thread_key],
                "role": role_text,
                "switch": switched,
                "color_index": color_index,
                "color_hex": CHAT_FLOW_COLORS[color_index],
            }
        )

    render_limit_safe = max(1, int(render_limit))
    waterfall = waterfall_all[-render_limit_safe:]
    active_hours = sum(1 for count in hour_bins if count > 0)
    thread_count = len(thread_counts)
    dominant_count = max(thread_counts.values()) if thread_counts else 0

    threads: list[dict[str, Any]] = []
    for thread_key, count in sorted(
        thread_counts.items(),
        key=lambda item: (-item[1], thread_order.get(item[0], 0)),
    ):
        color_index = thread_order.get(thread_key, 0) % len(CHAT_FLOW_COLORS)
        threads.append(
            {
                "thread_key": thread_key,
                "thread_id": "" if thread_key.startswith("untitled:") else thread_key,
                "thread_title": thread_titles.get(thread_key, "(no title)"),
                "message_count": count,
                "share": _ratio(count, total_messages, digits=3),
                "color_index": color_index,
                "color_hex": CHAT_FLOW_COLORS[color_index],
            }
        )

    return {
        "message_count": total_messages,
        "thread_count": thread_count,
        "active_hours": active_hours,
        "switch_count": switch_count,
        "switch_rate": _ratio(switch_count, max(0, total_messages - 1), digits=3),
        "switches_per_active_hour": _ratio(switch_count, active_hours, digits=2),
        "switch_opportunities": max(0, total_messages - 1),
        "messages_per_hour_active": _ratio(total_messages, active_hours, digits=2),
        "messages_per_hour_day": round(total_messages / 24.0, 2),
        "messages_per_chat": _ratio(total_messages, thread_count, digits=2),
        "dominant_thread_share": _ratio(dominant_count, total_messages, digits=3),
        "first_ts": _iso_utc(ordered[0].dt),
        "last_ts": _iso_utc(ordered[-1].dt),
        "hour_bins": hour_bins,
        "threads": threads,
        "waterfall": waterfall,
        "waterfall_render_limit": render_limit_safe,
        "waterfall_truncated": total_messages > len(waterfall),
    }


def _rel_href(target: str, html_path: Path) -> str:
    try:
        return os.path.relpath(target, html_path.parent)
    except ValueError:
        return target


def _render_hour_rows(bins: list[int], css_class: str) -> str:
    max_count = max(bins) if bins else 0
    safe_max = max_count if max_count > 0 else 1
    rows: list[str] = []
    for hour, count in enumerate(bins):
        width = int((count / safe_max) * 100) if count else 0
        rows.append(
            "<li>"
            f"<code>{hour:02d}</code>"
            f"<div class='bar-wrap'><div class='bar {css_class}' style='width:{width}%;'></div></div>"
            f"<span>{count}</span>"
            "</li>"
        )
    return "\n".join(rows)


def render_dashboard_html(payload: dict[str, Any], html_path: Path) -> str:
    summary = payload.get("summary", {})
    freq = payload.get("frequency_by_hour", {})
    artifacts = payload.get("artifact_links", [])
    timeline = payload.get("timeline", [])
    threads = payload.get("chat_threads", [])
    tool_use_summary = payload.get("tool_use_summary") or {}
    warnings = payload.get("warnings", [])
    chat_flow = payload.get("chat_flow") or {}

    artifact_rows = []
    for item in artifacts:
        target = str(item.get("path", ""))
        label = escape(str(item.get("label", target)))
        href = escape(_rel_href(target, html_path))
        artifact_rows.append(f"<li><a href='{href}'>{label}</a><code>{escape(target)}</code></li>")

    thread_rows = []
    for thread in threads:
        roles = ", ".join(f"{k}:{v}" for k, v in sorted((thread.get("roles") or {}).items()))
        thread_id_full = str(thread.get("thread_id") or "")
        thread_id_short = _short_id(thread_id_full, width=12)
        title_resolved = str(
            thread.get("title_resolved")
            or _resolve_thread_title(thread.get("title"), thread.get("first_user_preview"))
        )
        origin = str(thread.get("origin") or "unknown")
        thread_rows.append(
            "<tr>"
            f"<td><code title='{escape(thread_id_full)}'>{escape(thread_id_short)}</code></td>"
            f"<td>{escape(title_resolved)}</td>"
            f"<td><code>{escape(origin)}</code></td>"
            f"<td>{thread.get('message_count', 0)}</td>"
            f"<td><code>{escape(str(thread.get('first_ts') or ''))}</code></td>"
            f"<td><code>{escape(str(thread.get('last_ts') or ''))}</code></td>"
            f"<td>{escape(roles)}</td>"
            "</tr>"
        )

    tool_family_rows: list[str] = []
    for family in tool_use_summary.get("families") or []:
        family_name = escape(str(family.get("family") or "unknown"))
        family_count = _safe_int(family.get("count"))
        family_variants = _safe_int(family.get("unique_variants"))
        top_dirs = family.get("top_dirs") or []
        top_dir_text = ", ".join(
            f"{item.get('path')} ({item.get('count')})"
            for item in top_dirs
            if isinstance(item, dict) and item.get("path")
        ) or "none"
        variants = family.get("variants") or []
        variant_groups = family.get("variant_groups") or []
        if family.get("family") == "rg" and isinstance(variant_groups, list) and variant_groups:
            grouped_lines: list[str] = []
            for group in variant_groups:
                if not isinstance(group, dict):
                    continue
                mode = str(group.get("group") or "other")
                mode_count = _safe_int(group.get("count"))
                mode_items = group.get("variants") if isinstance(group.get("variants"), list) else []
                mode_lines: list[str] = []
                for mode_item in mode_items:
                    if not isinstance(mode_item, dict):
                        continue
                    detail = str(mode_item.get("detail") or "")
                    detail_count = _safe_int(mode_item.get("count"))
                    mode_lines.append(
                        f"<li><code>{detail_count}</code> {_render_foldable_text(detail, limit=120)}</li>"
                    )
                mode_html = "<ul>" + "".join(mode_lines) + "</ul>" if mode_lines else ""
                grouped_lines.append(
                    f"<li><code>rg {escape(mode)}</code> <code>{mode_count}</code>{mode_html}</li>"
                )
            variant_html = "<ul>" + "".join(grouped_lines) + "</ul>" if grouped_lines else "none"
        else:
            variant_lines = []
            for item in variants:
                if not isinstance(item, dict):
                    continue
                command_text = str(item.get("command") or "")
                command_count = _safe_int(item.get("count"))
                variant_lines.append(
                    f"<li><code>{command_count}</code> {_render_foldable_text(command_text, limit=140)}</li>"
                )
            variant_html = "<ul>" + "".join(variant_lines) + "</ul>" if variant_lines else "none"
        tool_family_rows.append(
            "<tr>"
            f"<td><code>{family_name}</code></td>"
            f"<td>{family_count}</td>"
            f"<td>{family_variants}</td>"
            f"<td>{escape(top_dir_text)}</td>"
            f"<td>{variant_html}</td>"
            "</tr>"
        )

    tool_dir_rows = []
    for item in tool_use_summary.get("top_dirs") or []:
        if not isinstance(item, dict):
            continue
        path_text = item.get("path")
        if not path_text:
            continue
        tool_dir_rows.append(
            f"<li><code>{escape(str(path_text))}</code> ({_safe_int(item.get('count'))})</li>"
        )

    tool_warning_rows = "\n".join(
        f"<li>{escape(str(warn))}</li>" for warn in (tool_use_summary.get("warnings") or [])
    )

    flow_thread_rows: list[str] = []
    for thread in chat_flow.get("threads") or []:
        if not isinstance(thread, dict):
            continue
        color_hex = str(thread.get("color_hex") or "#6b7280")
        message_count = _safe_int(thread.get("message_count"))
        share_pct = _safe_float(thread.get("share")) * 100.0
        thread_title = str(thread.get("thread_title") or "(no title)")
        thread_id = str(thread.get("thread_id") or "")
        thread_label = thread_title
        if thread_id:
            thread_label = f"{thread_label} [{_short_id(thread_id, width=12)}]"
        flow_thread_rows.append(
            "<li>"
            f"<span class='wf-swatch' style='background:{escape(color_hex)};'></span>"
            f"<code>{message_count}</code> {escape(thread_label)} <code>{share_pct:.1f}%</code>"
            "</li>"
        )

    flow_segments: list[str] = []
    for segment in chat_flow.get("waterfall") or []:
        if not isinstance(segment, dict):
            continue
        color_hex = str(segment.get("color_hex") or "#6b7280")
        thread_title = str(segment.get("thread_title") or "(no title)")
        thread_id = str(segment.get("thread_id") or "")
        role_text = str(segment.get("role") or "unknown")
        ts_text = str(segment.get("ts") or "")
        switch_text = "switch" if bool(segment.get("switch")) else "stay"
        title_parts = [ts_text, role_text, thread_title, switch_text]
        if thread_id:
            title_parts.append(_short_id(thread_id, width=12))
        title_text = " | ".join(item for item in title_parts if item)
        class_text = "wf-seg switch" if bool(segment.get("switch")) else "wf-seg"
        flow_segments.append(
            f"<span class='{class_text}' style='background:{escape(color_hex)};' title='{escape(title_text)}' aria-label='{escape(title_text)}'></span>"
        )

    messages_per_hour_active = _safe_float(summary.get("messages_per_hour_active"))
    messages_per_chat = _safe_float(summary.get("messages_per_chat"))
    chat_switch_rate_pct = _safe_float(summary.get("chat_switch_rate")) * 100.0

    kind_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    chat_role_counts: Counter[str] = Counter()
    for item in timeline:
        kind_value = str(item.get("kind") or "unknown")
        source_value = _source_kind(str(item.get("source_path") or ""))
        kind_counts[kind_value] += 1
        source_counts[source_value] += 1
        if kind_value == "chat":
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            role_value = str(meta.get("role") or "unknown").strip().lower() if isinstance(meta, dict) else "unknown"
            chat_role_counts[role_value] += 1

    kind_filters = "".join(
        (
            "<label>"
            f"<input type='checkbox' class='flt-kind' value='{escape(kind)}' checked> "
            f"{escape(kind)} <code>{count}</code>"
            "</label>"
        )
        for kind, count in sorted(kind_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    source_filters = "".join(
        (
            "<label>"
            f"<input type='checkbox' class='flt-source' value='{escape(source)}' checked> "
            f"{escape(_source_label(source))} <code>{count}</code>"
            "</label>"
        )
        for source, count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    role_filters = "".join(
        (
            "<label>"
            f"<input type='checkbox' class='flt-role' value='{escape(role)}' checked> "
            f"{escape(role)} <code>{count}</code>"
            "</label>"
        )
        for role, count in sorted(chat_role_counts.items(), key=lambda item: (-item[1], item[0]))
    )

    timeline_rows = []
    for item in timeline:
        kind_value = str(item.get("kind", "") or "unknown")
        source_path = str(item.get("source_path", ""))
        source_kind = _source_kind(source_path)
        source_label = _source_label(source_path)
        detail_text = str(item.get("detail", ""))
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        role_value = "n/a"
        thread_id_value = ""
        chars = ""
        detail_display = detail_text
        if isinstance(meta, dict):
            chars_value = meta.get("chars")
            if chars_value is not None:
                chars = str(_safe_int(chars_value))
            thread_id_value = str(meta.get("thread_id") or "")
            if kind_value == "chat":
                role = str(meta.get("role") or "unknown")
                role_value = role.strip().lower() or "unknown"
                thread_title = _resolve_thread_title(
                    meta.get("thread_title"),
                    meta.get("thread_first_user_preview"),
                )
                thread_origin = str(meta.get("thread_origin") or "")
                preview = _collapse_ws(meta.get("preview"))
                detail_display = f"{role} · {thread_title}"
                if thread_origin and thread_origin != "unknown":
                    detail_display += f" · {thread_origin}"
                if preview:
                    detail_display += f" · {preview}"

        search_blob = _collapse_ws(
            " ".join(
                [
                    str(item.get("ts", "")),
                    kind_value,
                    detail_display,
                    source_label,
                    source_path,
                    thread_id_value,
                    role_value,
                ]
            )
        ).lower()
        timeline_rows.append(
            "<tr "
            f"data-kind='{escape(kind_value)}' "
            f"data-source='{escape(source_kind)}' "
            f"data-chat-role='{escape(role_value)}' "
            f"data-thread='{escape(thread_id_value)}' "
            f"data-search='{escape(search_blob)}'>"
            f"<td><code>{escape(str(item.get('ts', '')))}</code></td>"
            f"<td>{escape(kind_value)}</td>"
            f"<td>{_render_foldable_text(detail_display, limit=190)}</td>"
            f"<td><code>{escape(chars)}</code></td>"
            f"<td><span class='src-badge src-{escape(source_kind)}' title='{escape(source_path)}'>{escape(source_label)}</span></td>"
            "</tr>"
        )

    warning_rows = "\n".join(f"<li>{escape(str(warn))}</li>" for warn in warnings)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SB Activity Dashboard {escape(str(payload.get("date", "")))}</title>
  <style>
    :root {{
      --bg: #f3f6f0;
      --ink: #1c2321;
      --panel: #ffffff;
      --chat: #0b6e4f;
      --shell: #1d4ed8;
      --input: #a16207;
      --window: #9d174d;
      --branch: #0f766e;
      --pr: #7c3aed;
      --line: #d9e1d9;
    }}
    body {{ margin: 0; background: radial-gradient(circle at top left, #e7f2ea, var(--bg)); color: var(--ink); font-family: "IBM Plex Sans", "Segoe UI", sans-serif; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 1.2rem; display: grid; gap: 1rem; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 0.9rem; }}
    h1,h2 {{ margin: 0 0 0.6rem 0; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .meta {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.92rem; }}
    .grid {{ display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }}
    .metric {{ border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem; }}
    .metric b {{ display:block; font-size: 1.3rem; margin-top: 0.2rem; }}
    .metric small {{ display:block; margin-top: 0.2rem; color: #4b5563; font-size: 0.78rem; }}
    .bars {{ display: grid; gap: 0.8rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .bars ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 0.3rem; }}
    .bars li {{ display: grid; grid-template-columns: 2.2rem 1fr 2rem; align-items: center; gap: 0.4rem; }}
    .bar-wrap {{ border: 1px solid var(--line); border-radius: 7px; overflow: hidden; height: 0.7rem; }}
    .bar {{ height: 100%; }}
    .chat {{ background: var(--chat); }} .shell {{ background: var(--shell); }} .input {{ background: var(--input); }} .window {{ background: var(--window); }} .branch {{ background: var(--branch); }} .pr {{ background: var(--pr); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 0.35rem; vertical-align: top; }}
    .filter-grid {{ display: grid; gap: 0.65rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-bottom: 0.7rem; }}
    .filter-block {{ border: 1px solid var(--line); border-radius: 8px; padding: 0.45rem; background: #fbfcfb; }}
    .filter-search {{ display: flex; gap: 0.4rem; margin-top: 0.35rem; }}
    .filter-search input[type="search"] {{ flex: 1; border: 1px solid var(--line); border-radius: 6px; padding: 0.25rem 0.4rem; font: inherit; }}
    .filter-search button {{ border: 1px solid var(--line); border-radius: 6px; background: #f5f7f4; padding: 0.25rem 0.5rem; cursor: pointer; }}
    .filter-options {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.35rem; }}
    .filter-options label {{ display: inline-flex; align-items: center; gap: 0.2rem; border: 1px solid var(--line); border-radius: 999px; padding: 0.1rem 0.35rem; background: #f7faf7; font-size: 0.82rem; }}
    .timeline-count {{ margin-top: 0.4rem; font-size: 0.82rem; color: #4b5563; }}
    code {{ background: #eff2ef; border-radius: 4px; padding: 0.05rem 0.2rem; }}
    pre {{ white-space: pre-wrap; word-break: break-word; margin: 0.45rem 0 0 0; font-family: "IBM Plex Mono", "Consolas", monospace; font-size: 0.82rem; }}
    details summary {{ cursor: pointer; }}
    .src-badge {{ display: inline-block; border-radius: 999px; padding: 0.1rem 0.45rem; font-size: 0.76rem; border: 1px solid var(--line); }}
    .src-sqlite {{ background: #e5f3ec; color: #0b6e4f; border-color: #8ecfb4; }}
    .src-chat_exports {{ background: #e8eefc; color: #1d4ed8; border-color: #adc3f4; }}
    .src-resolver {{ background: #f4ebfd; color: #7c3aed; border-color: #ccb7f6; }}
    .src-logs {{ background: #fff7e6; color: #a16207; border-color: #f1d193; }}
    .src-activity {{ background: #ffe9f1; color: #9d174d; border-color: #f2b7cf; }}
    .src-outputs {{ background: #ebf8ff; color: #0f766e; border-color: #9fdcd6; }}
    .src-other {{ background: #f3f4f6; color: #374151; border-color: #d1d5db; }}
    .links li {{ display: grid; gap: 0.15rem; margin-bottom: 0.45rem; }}
    .wf-strip {{ display: flex; gap: 0.16rem; overflow-x: auto; padding: 0.25rem 0 0.35rem 0; }}
    .wf-seg {{ width: 0.62rem; height: 0.95rem; border-radius: 2px; border: 1px solid rgba(0, 0, 0, 0.15); flex: 0 0 auto; }}
    .wf-seg.switch {{ outline: 2px solid rgba(17, 24, 39, 0.65); outline-offset: 1px; }}
    .wf-legend {{ list-style: none; margin: 0.5rem 0 0 0; padding: 0; display: grid; gap: 0.3rem; }}
    .wf-legend li {{ display: flex; align-items: center; gap: 0.35rem; }}
    .wf-swatch {{ width: 0.75rem; height: 0.75rem; border-radius: 3px; border: 1px solid rgba(0, 0, 0, 0.25); display: inline-block; }}
    .wf-note {{ margin-top: 0.45rem; color: #4b5563; font-size: 0.84rem; }}
    @media (max-width: 760px) {{ table {{ font-size: 0.82rem; }} }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>SB Activity Dashboard</h1>
      <div class="meta">
        <div><b>Date:</b> <code>{escape(str(payload.get("date", "")))}</code></div>
        <div><b>Generated:</b> <code>{escape(str(payload.get("generated_at", "")))}</code></div>
        <div><b>Chat source:</b> <code>{escape(str(payload.get("chat_source", "")))}</code></div>
        <div><b>Chat scope:</b> <code>{escape(str(payload.get("chat_scope_mode", "scoped")))}</code></div>
      </div>
    </section>
    <section class="panel">
      <h2>Summary</h2>
      <div class="grid">
        <div class="metric">Chat messages<b>{summary.get("chat_messages", 0)}</b></div>
        <div class="metric">Chat threads<b>{summary.get("chat_threads", 0)}</b></div>
        <div class="metric">Messages/hour (active)<b>{messages_per_hour_active:.2f}</b><small>{_safe_int(summary.get("chat_active_hours"))} active hour(s)</small></div>
        <div class="metric">Messages/chat<b>{messages_per_chat:.2f}</b></div>
        <div class="metric">Chat switches<b>{_safe_int(summary.get("chat_switches"))}</b><small>{chat_switch_rate_pct:.1f}% of transitions</small></div>
        <div class="metric">Shell commands<b>{summary.get("shell_commands", 0)}</b></div>
        <div class="metric">Input events<b>{summary.get("input_events", 0)}</b></div>
        <div class="metric">Window focus events<b>{summary.get("window_focus_events", 0)}</b></div>
        <div class="metric">Activity events<b>{summary.get("activity_events", 0)}</b></div>
        <div class="metric">Git branch events<b>{summary.get("git_branch_events", 0)}</b></div>
        <div class="metric">PR events<b>{summary.get("pr_events", 0)}</b></div>
        <div class="metric">PR merged/commented/received<b>{summary.get("pr_merged", 0)}/{summary.get("pr_commented", 0)}/{summary.get("pr_received", 0)}</b></div>
      </div>
    </section>
    <section class="panel bars">
      <div><h2>Messages/hour</h2><ul>{_render_hour_rows(freq.get("chat", _empty_bins()), "chat")}</ul></div>
      <div><h2>Shell/hour</h2><ul>{_render_hour_rows(freq.get("shell", _empty_bins()), "shell")}</ul></div>
      <div><h2>Input/hour</h2><ul>{_render_hour_rows(freq.get("input", _empty_bins()), "input")}</ul></div>
      <div><h2>Window/hour</h2><ul>{_render_hour_rows(freq.get("window", _empty_bins()), "window")}</ul></div>
      <div><h2>Branch/hour</h2><ul>{_render_hour_rows(freq.get("git_branch", _empty_bins()), "branch")}</ul></div>
      <div><h2>PR/hour</h2><ul>{_render_hour_rows(freq.get("pr", _empty_bins()), "pr")}</ul></div>
    </section>
    <section class="panel">
      <h2>Process Artifacts</h2>
      <ul class="links">{"".join(artifact_rows) if artifact_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel">
      <h2>Chat Threads</h2>
      <table>
        <thead><tr><th>Thread ID</th><th>Title</th><th>Origin</th><th>Messages</th><th>First</th><th>Last</th><th>Roles</th></tr></thead>
        <tbody>{"".join(thread_rows) if thread_rows else "<tr><td colspan='7'>No chat thread activity for this date.</td></tr>"}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Chat Flow Waterfall</h2>
      <p>
        messages=<code>{_safe_int(chat_flow.get("message_count"))}</code>,
        threads=<code>{_safe_int(chat_flow.get("thread_count"))}</code>,
        switches=<code>{_safe_int(chat_flow.get("switch_count"))}</code>,
        switch_rate=<code>{_safe_float(chat_flow.get("switch_rate")) * 100.0:.1f}%</code>,
        window=<code>{escape(str(chat_flow.get("first_ts") or ""))}</code> to
        <code>{escape(str(chat_flow.get("last_ts") or ""))}</code>
      </p>
      <div class="wf-strip">{"".join(flow_segments) if flow_segments else "<span>No chat messages for this date.</span>"}</div>
      <p class="wf-note">
        {(
          f"Showing newest {_safe_int(chat_flow.get('waterfall_render_limit'))} of {_safe_int(chat_flow.get('message_count'))} messages."
          if bool(chat_flow.get("waterfall_truncated"))
          else "Each block is one chat message; outlined blocks mark a jump to a different thread."
        )}
      </p>
      <ul class="wf-legend">{"".join(flow_thread_rows) if flow_thread_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel">
      <h2>Tool Use Summary</h2>
      <p>
        source=<code>{escape(str(tool_use_summary.get("source", "none")))}</code>,
        tool_messages=<code>{_safe_int(tool_use_summary.get("total_tool_messages"))}</code>,
        exec_command=<code>{_safe_int(tool_use_summary.get("exec_command_count"))}</code>,
        unique_commands=<code>{_safe_int(tool_use_summary.get("unique_commands"))}</code>
      </p>
      <p><b>Top directories touched:</b></p>
      <ul>{"".join(tool_dir_rows) if tool_dir_rows else "<li>None</li>"}</ul>
      <table>
        <thead><tr><th>Command Family</th><th>Count</th><th>Unique Variants</th><th>Top Dirs</th><th>Variants</th></tr></thead>
        <tbody>{"".join(tool_family_rows) if tool_family_rows else "<tr><td colspan='5'>No tool command activity parsed.</td></tr>"}</tbody>
      </table>
      <p><b>Tool summary warnings:</b></p>
      <ul>{tool_warning_rows if tool_warning_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel">
      <h2>Timeline</h2>
      <div class="filter-grid">
        <div class="filter-block">
          <b>Search</b>
          <div class="filter-search">
            <input id="timeline-search" type="search" placeholder="filter timeline rows">
            <button id="timeline-reset" type="button">Reset</button>
          </div>
          <div id="timeline-count" class="timeline-count"></div>
        </div>
        <div class="filter-block">
          <b>Kinds</b>
          <div class="filter-options">{kind_filters if kind_filters else "<span>None</span>"}</div>
        </div>
        <div class="filter-block">
          <b>Sources</b>
          <div class="filter-options">{source_filters if source_filters else "<span>None</span>"}</div>
        </div>
        <div class="filter-block">
          <b>Chat Roles</b>
          <div class="filter-options">{role_filters if role_filters else "<span>None</span>"}</div>
        </div>
      </div>
      <table id="timeline-table">
        <thead><tr><th>TS</th><th>Kind</th><th>Detail</th><th>Chars</th><th>Source</th></tr></thead>
        <tbody>{"".join(timeline_rows) if timeline_rows else "<tr><td colspan='5'>No timeline events.</td></tr>"}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Warnings</h2>
      <ul>{warning_rows if warning_rows else "<li>None</li>"}</ul>
    </section>
  </main>
  <script>
    (() => {{
      const table = document.getElementById("timeline-table");
      if (!table) return;
      const bodyRows = Array.from(table.querySelectorAll("tbody tr[data-kind]"));
      if (!bodyRows.length) return;

      const kindBoxes = Array.from(document.querySelectorAll(".flt-kind"));
      const sourceBoxes = Array.from(document.querySelectorAll(".flt-source"));
      const roleBoxes = Array.from(document.querySelectorAll(".flt-role"));
      const searchInput = document.getElementById("timeline-search");
      const resetButton = document.getElementById("timeline-reset");
      const countLabel = document.getElementById("timeline-count");

      const selected = (boxes) =>
        new Set(boxes.filter((box) => box.checked).map((box) => box.value));

      const applyFilters = () => {{
        const allowedKinds = selected(kindBoxes);
        const allowedSources = selected(sourceBoxes);
        const allowedRoles = selected(roleBoxes);
        const query = (searchInput?.value || "").trim().toLowerCase();
        let visible = 0;

        bodyRows.forEach((row) => {{
          const kind = row.dataset.kind || "";
          const source = row.dataset.source || "";
          const chatRole = row.dataset.chatRole || "n/a";
          const haystack = row.dataset.search || "";
          let show = true;

          if (allowedKinds.size && !allowedKinds.has(kind)) show = false;
          if (show && allowedSources.size && !allowedSources.has(source)) show = false;
          if (show && kind === "chat" && allowedRoles.size && !allowedRoles.has(chatRole)) show = false;
          if (show && query && !haystack.includes(query)) show = false;

          row.style.display = show ? "" : "none";
          if (show) visible += 1;
        }});

        if (countLabel) {{
          countLabel.textContent = `${{visible}}/${{bodyRows.length}} rows`;
        }}
      }};

      const resetFilters = () => {{
        kindBoxes.forEach((box) => {{
          box.checked = true;
        }});
        sourceBoxes.forEach((box) => {{
          box.checked = true;
        }});
        roleBoxes.forEach((box) => {{
          box.checked = true;
        }});
        if (searchInput) {{
          searchInput.value = "";
        }}
        applyFilters();
      }};

      [...kindBoxes, ...sourceBoxes, ...roleBoxes].forEach((box) => {{
        box.addEventListener("change", applyFilters);
      }});
      if (searchInput) {{
        searchInput.addEventListener("input", applyFilters);
      }}
      if (resetButton) {{
        resetButton.addEventListener("click", resetFilters);
      }}

      applyFilters();
    }})();
  </script>
</body>
</html>
"""


def _date_window(end_date_text: str, days: int) -> list[str]:
    if days <= 0:
        raise ValueError("days must be >= 1")
    end_date = date_cls.fromisoformat(end_date_text)
    start_date = end_date - timedelta(days=days - 1)
    return [
        (start_date + timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]


def _build_trailing_chat_context(
    *,
    date_text: str,
    runs_root: Path,
    current_summary: dict[str, Any],
    days: int = 7,
) -> dict[str, Any]:
    if days <= 0:
        return {"window_days": 0, "available_days": 0, "has_baseline": False}

    end_date = date_cls.fromisoformat(date_text)
    baseline_summaries: list[dict[str, Any]] = []
    for idx in range(1, days + 1):
        day_text = (end_date - timedelta(days=idx)).isoformat()
        summary_path = runs_root / day_text / "outputs" / "dashboard.json"
        if not summary_path.exists():
            continue
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        summary = payload.get("summary")
        if isinstance(summary, dict):
            baseline_summaries.append(summary)

    def mean(metric_key: str, digits: int) -> float:
        if not baseline_summaries:
            return 0.0
        total = sum(_safe_float(item.get(metric_key)) for item in baseline_summaries)
        return round(total / len(baseline_summaries), digits)

    current_rate = _safe_float(current_summary.get("context_switch_rate"))
    current_switches_per_hour = _safe_float(current_summary.get("switches_per_active_hour"))
    current_messages_per_chat = _safe_float(current_summary.get("messages_per_chat"))
    current_top_thread_share = _safe_float(current_summary.get("top_thread_share"))

    baseline_rate = mean("context_switch_rate", 3)
    baseline_switches_per_hour = mean("switches_per_active_hour", 2)
    baseline_messages_per_chat = mean("messages_per_chat", 2)
    baseline_top_thread_share = mean("top_thread_share", 3)

    available_days = len(baseline_summaries)
    return {
        "window_days": days,
        "available_days": available_days,
        "has_baseline": available_days > 0,
        "current": {
            "context_switch_rate": round(current_rate, 3),
            "switches_per_active_hour": round(current_switches_per_hour, 2),
            "messages_per_chat": round(current_messages_per_chat, 2),
            "top_thread_share": round(current_top_thread_share, 3),
        },
        "baseline_avg": {
            "context_switch_rate": baseline_rate,
            "switches_per_active_hour": baseline_switches_per_hour,
            "messages_per_chat": baseline_messages_per_chat,
            "top_thread_share": baseline_top_thread_share,
        },
        "delta": {
            "context_switch_rate": round(current_rate - baseline_rate, 3),
            "switches_per_active_hour": round(current_switches_per_hour - baseline_switches_per_hour, 2),
            "messages_per_chat": round(current_messages_per_chat - baseline_messages_per_chat, 2),
            "top_thread_share": round(current_top_thread_share - baseline_top_thread_share, 3),
        },
    }


def build_dashboard(
    *,
    date_text: str,
    repo_root: Path,
    runs_root: Path,
    context_root: Path,
    convo_ids_path: Path,
    chat_db_path: Path,
    chat_exports_dir: Path,
    max_timeline_events: int = 600,
    include_all_chat: bool = False,
) -> dict[str, Any]:
    run_dir = runs_root / date_text
    logs_dir = run_dir / "logs"
    outputs_dir = run_dir / "outputs"

    scoped_thread_ids = _parse_convo_scope(convo_ids_path)
    thread_scope = {} if include_all_chat else scoped_thread_ids

    chat_events, thread_activity, chat_source, warnings = _load_chat_events(
        date_text=date_text,
        thread_scope=thread_scope,
        chat_db_path=chat_db_path,
        exports_dir=chat_exports_dir,
        last_sync_dir=context_root / "last_sync",
    )
    tool_use_summary = _load_tool_use_summary_sqlite(
        db_path=chat_db_path,
        date_text=date_text,
        thread_scope=thread_scope,
    )

    cli_events, shell_commands = _load_cli_events(logs_dir / "cli" / f"{date_text}.jsonl")
    input_events, input_count, input_keys_total, input_mouse_total = _load_input_events(
        logs_dir / "input" / f"{date_text}.jsonl"
    )
    window_events, window_count = _load_window_events(logs_dir / "windows" / f"{date_text}.jsonl")
    git_events, git_commits = _load_git_events(logs_dir / "git" / f"{date_text}.jsonl")
    git_branch_events, git_branch_count = _load_git_branch_events(
        logs_dir / "git_branch" / f"{date_text}.jsonl"
    )
    pr_events, pr_count, pr_detail_counts = _load_pr_events(logs_dir / "pr" / f"{date_text}.jsonl")
    activity_events, activity_count = _load_activity_events(outputs_dir / "activity_ledger.json")

    all_events = (
        chat_events
        + cli_events
        + input_events
        + window_events
        + git_events
        + git_branch_events
        + pr_events
        + activity_events
    )
    all_events.sort(key=lambda item: item.dt)
    timeline_truncated = False
    if len(all_events) > max_timeline_events:
        all_events = all_events[-max_timeline_events:]
        timeline_truncated = True

    freq = {
        "chat": _empty_bins(),
        "shell": _empty_bins(),
        "input": _empty_bins(),
        "window": _empty_bins(),
        "git_branch": _empty_bins(),
        "pr": _empty_bins(),
    }
    for event in all_events:
        if event.kind == "chat":
            _increment_bin(freq["chat"], event.dt)
        elif event.kind == "shell":
            _increment_bin(freq["shell"], event.dt)
        elif event.kind == "input":
            _increment_bin(freq["input"], event.dt)
        elif event.kind == "window":
            _increment_bin(freq["window"], event.dt)
        elif event.kind == "git_branch":
            _increment_bin(freq["git_branch"], event.dt)
        elif event.kind == "pr":
            _increment_bin(freq["pr"], event.dt)

    chat_flow = _build_chat_flow(chat_events)

    artifacts = _collect_artifact_links(
        repo_root,
        outputs_dir,
        context_root,
        scoped_thread_ids,
        include_all_chat=include_all_chat,
    )
    if timeline_truncated:
        warnings.append(
            f"Timeline truncated to {max_timeline_events} events (newest retained)."
        )
    if include_all_chat:
        warnings.append(
            "Debug mode enabled: chat scope filter disabled (all chat threads scanned for this date)."
        )

    summary = {
        "chat_messages": len(chat_events),
        "chat_threads": len(thread_activity),
        "chat_active_hours": _safe_int(chat_flow.get("active_hours")),
        "messages_per_hour_active": _safe_float(chat_flow.get("messages_per_hour_active")),
        "messages_per_hour_day": _safe_float(chat_flow.get("messages_per_hour_day")),
        "messages_per_chat": _safe_float(chat_flow.get("messages_per_chat")),
        "chat_switches": _safe_int(chat_flow.get("switch_count")),
        "chat_switch_rate": _safe_float(chat_flow.get("switch_rate")),
        "context_switch_rate": _safe_float(chat_flow.get("switch_rate")),
        "switches_per_active_hour": _safe_float(chat_flow.get("switches_per_active_hour")),
        "top_thread_share": _safe_float(chat_flow.get("dominant_thread_share")),
        "shell_commands": shell_commands,
        "input_events": input_count,
        "input_keys_total": input_keys_total,
        "input_mouse_total": input_mouse_total,
        "window_focus_events": window_count,
        "activity_events": activity_count,
        "git_commits": git_commits,
        "git_branch_events": git_branch_count,
        "pr_events": pr_count,
        "pr_received": pr_detail_counts.get("pr_received", 0),
        "pr_commented": pr_detail_counts.get("pr_commented", 0),
        "pr_merged": pr_detail_counts.get("pr_merged", 0),
        "timeline_events": len(all_events),
    }
    trailing_chat_context = _build_trailing_chat_context(
        date_text=date_text,
        runs_root=runs_root,
        current_summary=summary,
        days=7,
    )

    return {
        "date": date_text,
        "generated_at": _iso_utc(datetime.now(UTC)),
        "chat_source": chat_source,
        "chat_scope_mode": "all" if include_all_chat else "scoped",
        "chat_scope_thread_count": len(scoped_thread_ids),
        "summary": summary,
        "frequency_by_hour": freq,
        "chat_flow": chat_flow,
        "chat_context_trailing": trailing_chat_context,
        "chat_threads": thread_activity,
        "tool_use_summary": tool_use_summary,
        "artifact_links": artifacts,
        "timeline": [event.to_payload() for event in all_events],
        "warnings": warnings,
    }


def build_weekly_dashboard(
    *,
    end_date_text: str,
    days: int,
    repo_root: Path,
    runs_root: Path,
    context_root: Path,
    convo_ids_path: Path,
    chat_db_path: Path,
    chat_exports_dir: Path,
    max_timeline_events: int = 600,
    include_all_chat: bool = False,
) -> dict[str, Any]:
    dates = _date_window(end_date_text, days)
    totals = {key: 0 for key in WEEKLY_SUMMARY_KEYS}
    daily: list[dict[str, Any]] = []
    chat_source_counts: dict[str, int] = {}
    warning_days: list[dict[str, Any]] = []

    for date_text in dates:
        payload = build_dashboard(
            date_text=date_text,
            repo_root=repo_root,
            runs_root=runs_root,
            context_root=context_root,
            convo_ids_path=convo_ids_path,
            chat_db_path=chat_db_path,
            chat_exports_dir=chat_exports_dir,
            max_timeline_events=max_timeline_events,
            include_all_chat=include_all_chat,
        )
        summary = payload.get("summary") or {}
        source = str(payload.get("chat_source") or "none")
        chat_source_counts[source] = chat_source_counts.get(source, 0) + 1
        day_warnings = payload.get("warnings") or []
        if day_warnings:
            warning_days.append(
                {
                    "date": date_text,
                    "warnings": [str(item) for item in day_warnings],
                }
            )

        day_summary = {}
        for key in WEEKLY_SUMMARY_KEYS:
            value = _safe_int(summary.get(key))
            totals[key] += value
            day_summary[key] = value
        day_summary["context_switch_rate"] = _safe_float(summary.get("context_switch_rate"))
        day_summary["switches_per_active_hour"] = _safe_float(summary.get("switches_per_active_hour"))
        day_summary["messages_per_chat"] = _safe_float(summary.get("messages_per_chat"))
        day_summary["top_thread_share"] = _safe_float(summary.get("top_thread_share"))

        daily_outputs = runs_root / date_text / "outputs"
        daily.append(
            {
                "date": date_text,
                "chat_source": source,
                "chat_scope_mode": str(payload.get("chat_scope_mode") or "scoped"),
                "summary": day_summary,
                "warning_count": len(day_warnings),
                "warning_preview": str(day_warnings[0]) if day_warnings else "",
                "daily_json_path": str(daily_outputs / "dashboard.json"),
                "daily_html_path": str(daily_outputs / "dashboard.html"),
            }
        )

    averages = {
        key: round(totals[key] / max(1, len(dates)), 2)
        for key in WEEKLY_SUMMARY_KEYS
    }
    context_averages = {
        "context_switch_rate": round(
            sum(_safe_float((row.get("summary") or {}).get("context_switch_rate")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
        "switches_per_active_hour": round(
            sum(_safe_float((row.get("summary") or {}).get("switches_per_active_hour")) for row in daily)
            / max(1, len(daily)),
            2,
        ),
        "messages_per_chat": round(
            sum(_safe_float((row.get("summary") or {}).get("messages_per_chat")) for row in daily)
            / max(1, len(daily)),
            2,
        ),
        "top_thread_share": round(
            sum(_safe_float((row.get("summary") or {}).get("top_thread_share")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
    }
    warnings: list[str] = []
    if warning_days:
        warnings.append(f"{len(warning_days)} day(s) reported one or more warnings.")
    if include_all_chat:
        warnings.append(
            "Debug mode enabled: chat scope filter disabled (all chat threads scanned for each day)."
        )

    return {
        "period_start": dates[0],
        "period_end": dates[-1],
        "days": len(dates),
        "generated_at": _iso_utc(datetime.now(UTC)),
        "chat_scope_mode": "all" if include_all_chat else "scoped",
        "totals": totals,
        "averages_per_day": averages,
        "chat_context_averages": context_averages,
        "chat_source_counts": chat_source_counts,
        "daily": daily,
        "warning_days": warning_days,
        "warnings": warnings,
    }


def render_weekly_dashboard_html(payload: dict[str, Any], html_path: Path) -> str:
    totals = payload.get("totals") or {}
    averages = payload.get("averages_per_day") or {}
    rows = payload.get("daily") or []
    warnings = payload.get("warnings") or []

    day_rows: list[str] = []
    for row in rows:
        summary = row.get("summary") or {}
        html_target = str(row.get("daily_html_path") or "")
        day_rows.append(
            "<tr>"
            f"<td><code>{escape(str(row.get('date') or ''))}</code></td>"
            f"<td>{escape(str(row.get('chat_source') or 'none'))}</td>"
            f"<td>{escape(str(row.get('chat_scope_mode') or 'scoped'))}</td>"
            f"<td>{_safe_int(summary.get('chat_messages'))}</td>"
            f"<td>{_safe_int(summary.get('chat_threads'))}</td>"
            f"<td>{_safe_int(summary.get('chat_switches'))}</td>"
            f"<td>{_safe_int(summary.get('shell_commands'))}</td>"
            f"<td>{_safe_int(summary.get('git_commits'))}</td>"
            f"<td>{_safe_int(summary.get('git_branch_events'))}</td>"
            f"<td>{_safe_int(summary.get('pr_events'))}</td>"
            f"<td>{_safe_int(row.get('warning_count'))}</td>"
            f"<td><a href='{escape(_rel_href(html_target, html_path))}'>daily</a></td>"
            "</tr>"
        )

    warning_rows = "\n".join(f"<li>{escape(str(item))}</li>" for item in warnings)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SB Weekly Dashboard {escape(str(payload.get("period_start", "")))} to {escape(str(payload.get("period_end", "")))}</title>
  <style>
    :root {{
      --bg: #f4f8f7;
      --ink: #17222a;
      --panel: #ffffff;
      --line: #d7e1e7;
    }}
    body {{ margin: 0; background: linear-gradient(170deg, #eaf2f6, var(--bg)); color: var(--ink); font-family: "IBM Plex Sans", "Segoe UI", sans-serif; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 1.2rem; display: grid; gap: 1rem; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 0.9rem; }}
    .grid {{ display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }}
    .metric {{ border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem; }}
    .metric b {{ display:block; font-size: 1.25rem; margin-top: 0.2rem; }}
    h1,h2 {{ margin: 0 0 0.6rem 0; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 0.35rem; vertical-align: top; }}
    code {{ background: #edf2f4; border-radius: 4px; padding: 0.05rem 0.2rem; }}
    @media (max-width: 760px) {{ table {{ font-size: 0.82rem; }} }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>SB Weekly Dashboard</h1>
      <p>
        <b>Window:</b> <code>{escape(str(payload.get("period_start", "")))}</code> to
        <code>{escape(str(payload.get("period_end", "")))}</code> |
        <b>Days:</b> <code>{escape(str(payload.get("days", 0)))}</code> |
        <b>Chat scope:</b> <code>{escape(str(payload.get("chat_scope_mode", "scoped")))}</code>
      </p>
    </section>
    <section class="panel">
      <h2>Totals</h2>
      <div class="grid">
        <div class="metric">Chat messages<b>{_safe_int(totals.get("chat_messages"))}</b></div>
        <div class="metric">Chat threads<b>{_safe_int(totals.get("chat_threads"))}</b></div>
        <div class="metric">Chat switches<b>{_safe_int(totals.get("chat_switches"))}</b></div>
        <div class="metric">Shell commands<b>{_safe_int(totals.get("shell_commands"))}</b></div>
        <div class="metric">Input events<b>{_safe_int(totals.get("input_events"))}</b></div>
        <div class="metric">Window focus events<b>{_safe_int(totals.get("window_focus_events"))}</b></div>
        <div class="metric">Activity events<b>{_safe_int(totals.get("activity_events"))}</b></div>
        <div class="metric">Git commits<b>{_safe_int(totals.get("git_commits"))}</b></div>
        <div class="metric">Git branch events<b>{_safe_int(totals.get("git_branch_events"))}</b></div>
        <div class="metric">PR events<b>{_safe_int(totals.get("pr_events"))}</b></div>
      </div>
      <p>
        <b>Daily averages:</b>
        chat=<code>{escape(str(averages.get("chat_messages", 0)))}</code>,
        switches=<code>{escape(str(averages.get("chat_switches", 0)))}</code>,
        shell=<code>{escape(str(averages.get("shell_commands", 0)))}</code>,
        commits=<code>{escape(str(averages.get("git_commits", 0)))}</code>,
        prs=<code>{escape(str(averages.get("pr_events", 0)))}</code>
      </p>
    </section>
    <section class="panel">
      <h2>Per-Day Summary</h2>
      <table>
        <thead><tr><th>Date</th><th>Chat Source</th><th>Scope</th><th>Chat Msg</th><th>Chat Threads</th><th>Switches</th><th>Shell</th><th>Commits</th><th>Branch</th><th>PR</th><th>Warnings</th><th>Daily</th></tr></thead>
        <tbody>{"".join(day_rows) if day_rows else "<tr><td colspan='12'>No days found.</td></tr>"}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Warnings</h2>
      <ul>{warning_rows if warning_rows else "<li>None</li>"}</ul>
    </section>
  </main>
</body>
</html>
"""


def write_dashboard_outputs(
    payload: dict[str, Any],
    *,
    json_path: Path,
    html_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    html_path.write_text(render_dashboard_html(payload, html_path), encoding="utf-8")


def write_weekly_outputs(
    payload: dict[str, Any],
    *,
    json_path: Path,
    html_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    html_path.write_text(render_weekly_dashboard_html(payload, html_path), encoding="utf-8")
