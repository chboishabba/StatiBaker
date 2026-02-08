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


def _display_title(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "(no title)"


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
    finally:
        conn.close()

    for canonical_thread_id, title, role, ts, text, source_id in rows:
        dt = _parse_ts(ts)
        if dt is None:
            continue
        thread_id = str(canonical_thread_id or "").lower()
        thread_title = str(title or "").strip()
        in_scope = True
        if thread_scope:
            in_scope = thread_id in thread_ids
            if not in_scope and thread_title:
                lowered_title = thread_title.lower()
                in_scope = any(token in lowered_title for token in title_filters)
        if not in_scope:
            continue

        role_text = str(role or "unknown")
        char_count = len(str(text or ""))
        label = thread_title or thread_id or "chat-thread"
        detail = f"chat role={role_text} thread={label} chars={char_count}"
        source = f"{db_path}#{source_id}" if source_id else str(db_path)
        meta = {
            "thread_id": thread_id,
            "thread_title": thread_title or thread_scope.get(thread_id, ""),
            "role": role_text,
            "chars": char_count,
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
            thread_id or "unknown",
            {
                "thread_id": thread_id,
                "title": thread_title or thread_scope.get(thread_id, ""),
                "message_count": 0,
                "first_ts": _iso_utc(dt),
                "last_ts": _iso_utc(dt),
                "roles": {},
            },
        )
        stat["message_count"] += 1
        stat["first_ts"] = min(stat["first_ts"], _iso_utc(dt))
        stat["last_ts"] = max(stat["last_ts"], _iso_utc(dt))
        roles = stat["roles"]
        roles[role_text] = roles.get(role_text, 0) + 1

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
        chars = 0
        if isinstance(parts, list):
            chars = sum(len(str(p)) for p in parts if p is not None)
        elif isinstance(parts, str):
            chars = len(parts)
        items.append(
            {
                "role": str(role or "unknown"),
                "create_time": message.get("create_time"),
                "chars": chars,
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
        in_scope = True
        if thread_scope:
            in_scope = conv_id in thread_ids
            if not in_scope and title:
                lowered = title.lower()
                in_scope = any(token in lowered for token in title_filters)
        if not in_scope:
            continue

        label = title or conv_id or export_path.stem
        for item in items:
            dt = _parse_ts(item.get("create_time"))
            if dt is None or not (day_start <= dt < day_end):
                continue
            role_text = str(item.get("role") or "unknown")
            char_count = _safe_int(item.get("chars"))
            detail = f"chat role={role_text} thread={label} chars={char_count}"
            meta = {
                "thread_id": conv_id,
                "thread_title": title,
                "role": role_text,
                "chars": char_count,
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
                conv_id or export_path.stem,
                {
                    "thread_id": conv_id,
                    "title": title,
                    "message_count": 0,
                    "first_ts": _iso_utc(dt),
                    "last_ts": _iso_utc(dt),
                    "roles": {},
                },
            )
            stat["message_count"] += 1
            stat["first_ts"] = min(stat["first_ts"], _iso_utc(dt))
            stat["last_ts"] = max(stat["last_ts"], _iso_utc(dt))
            roles = stat["roles"]
            roles[role_text] = roles.get(role_text, 0) + 1

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
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            dt = _parse_ts(turn.get("ts_utc") or turn.get("ts"))
            if dt is None or not (day_start <= dt < day_end):
                continue
            role_text = str(turn.get("role") or "unknown")
            char_count = len(str(turn.get("text") or ""))
            detail = f"chat role={role_text} thread={title or thread_id} chars={char_count}"
            meta = {
                "thread_id": thread_id,
                "thread_title": title,
                "role": role_text,
                "chars": char_count,
            }
            events.append(TimelineEvent(dt=dt, kind="chat", detail=detail, source_path=str(path), meta=meta))
            stat = thread_stats.setdefault(
                thread_id,
                {
                    "thread_id": thread_id,
                    "title": title,
                    "message_count": 0,
                    "first_ts": _iso_utc(dt),
                    "last_ts": _iso_utc(dt),
                    "roles": {},
                },
            )
            stat["message_count"] += 1
            stat["first_ts"] = min(stat["first_ts"], _iso_utc(dt))
            stat["last_ts"] = max(stat["last_ts"], _iso_utc(dt))
            roles = stat["roles"]
            roles[role_text] = roles.get(role_text, 0) + 1
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

        families.append(
            {
                "family": family,
                "count": int(count),
                "unique_variants": len(variants),
                "variants": variant_rows,
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

    artifact_rows = []
    for item in artifacts:
        target = str(item.get("path", ""))
        label = escape(str(item.get("label", target)))
        href = escape(_rel_href(target, html_path))
        artifact_rows.append(f"<li><a href='{href}'>{label}</a><code>{escape(target)}</code></li>")

    thread_rows = []
    for thread in threads:
        roles = ", ".join(f"{k}:{v}" for k, v in sorted((thread.get("roles") or {}).items()))
        thread_rows.append(
            "<tr>"
            f"<td><code>{escape(str(thread.get('thread_id') or ''))}</code></td>"
            f"<td>{escape(_display_title(thread.get('title')))}</td>"
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
        variant_lines = []
        for item in variants:
            if not isinstance(item, dict):
                continue
            command_text = escape(str(item.get("command") or ""))
            command_count = _safe_int(item.get("count"))
            variant_lines.append(f"<li><code>{command_text}</code> ({command_count})</li>")
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

    timeline_rows = []
    for item in timeline:
        timeline_rows.append(
            "<tr>"
            f"<td><code>{escape(str(item.get('ts', '')))}</code></td>"
            f"<td>{escape(str(item.get('kind', '')))}</td>"
            f"<td>{escape(str(item.get('detail', '')))}</td>"
            f"<td><code>{escape(str(item.get('source_path', '')))}</code></td>"
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
    .bars {{ display: grid; gap: 0.8rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .bars ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 0.3rem; }}
    .bars li {{ display: grid; grid-template-columns: 2.2rem 1fr 2rem; align-items: center; gap: 0.4rem; }}
    .bar-wrap {{ border: 1px solid var(--line); border-radius: 7px; overflow: hidden; height: 0.7rem; }}
    .bar {{ height: 100%; }}
    .chat {{ background: var(--chat); }} .shell {{ background: var(--shell); }} .input {{ background: var(--input); }} .window {{ background: var(--window); }} .branch {{ background: var(--branch); }} .pr {{ background: var(--pr); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 0.35rem; vertical-align: top; }}
    code {{ background: #eff2ef; border-radius: 4px; padding: 0.05rem 0.2rem; }}
    .links li {{ display: grid; gap: 0.15rem; margin-bottom: 0.45rem; }}
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
      <div><h2>Chat/hour</h2><ul>{_render_hour_rows(freq.get("chat", _empty_bins()), "chat")}</ul></div>
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
        <thead><tr><th>Thread ID</th><th>Title</th><th>Messages</th><th>First</th><th>Last</th><th>Roles</th></tr></thead>
        <tbody>{"".join(thread_rows) if thread_rows else "<tr><td colspan='6'>No chat thread activity for this date.</td></tr>"}</tbody>
      </table>
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
      <table>
        <thead><tr><th>TS</th><th>Kind</th><th>Detail</th><th>Source</th></tr></thead>
        <tbody>{"".join(timeline_rows) if timeline_rows else "<tr><td colspan='4'>No timeline events.</td></tr>"}</tbody>
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


def _date_window(end_date_text: str, days: int) -> list[str]:
    if days <= 0:
        raise ValueError("days must be >= 1")
    end_date = date_cls.fromisoformat(end_date_text)
    start_date = end_date - timedelta(days=days - 1)
    return [
        (start_date + timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]


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

    return {
        "date": date_text,
        "generated_at": _iso_utc(datetime.now(UTC)),
        "chat_source": chat_source,
        "chat_scope_mode": "all" if include_all_chat else "scoped",
        "chat_scope_thread_count": len(scoped_thread_ids),
        "summary": {
            "chat_messages": len(chat_events),
            "chat_threads": len(thread_activity),
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
        },
        "frequency_by_hour": freq,
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
        shell=<code>{escape(str(averages.get("shell_commands", 0)))}</code>,
        commits=<code>{escape(str(averages.get("git_commits", 0)))}</code>,
        prs=<code>{escape(str(averages.get("pr_events", 0)))}</code>
      </p>
    </section>
    <section class="panel">
      <h2>Per-Day Summary</h2>
      <table>
        <thead><tr><th>Date</th><th>Chat Source</th><th>Scope</th><th>Chat Msg</th><th>Chat Threads</th><th>Shell</th><th>Commits</th><th>Branch</th><th>PR</th><th>Warnings</th><th>Daily</th></tr></thead>
        <tbody>{"".join(day_rows) if day_rows else "<tr><td colspan='11'>No days found.</td></tr>"}</tbody>
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
