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
from typing import Any, Iterable

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
RUN_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RESOLVER_ID_RE = re.compile(r"resolver_([0-9a-fA-F-]{8,})\.json$")
ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
AGENT_EDIT_HEADER_RE = re.compile(
    r"^\s*[•*-]\s*Edited\s+(?P<path>.+?)\s+\(\+(?P<added>\d+)\s*-(?P<removed>\d+)\)\s*$"
)
AGENT_EDIT_LINE_RE = re.compile(r"^\s*(?P<line>\d{1,6})\b")
WEEKLY_SUMMARY_KEYS = (
    "chat_messages",
    "chat_threads",
    "chat_switches",
    "chat_chars_est",
    "chat_tokens_est",
    "chat_input_tokens_est",
    "chat_output_tokens_est",
    "chat_other_tokens_est",
    "chat_context_overflow_threads",
    "chat_context_overflow_tokens",
    "shell_commands",
    "agent_edit_blocks",
    "agent_edit_files",
    "agent_edit_lines_added",
    "agent_edit_lines_removed",
    "media_events",
    "media_items_observed",
    "media_consumed_seconds",
    "media_content_seconds",
    "media_churn_events",
    "inaturalist_events",
    "inaturalist_insect_observations",
    "mood_reports",
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
    "itir_overlays_total",
    "itir_overlays_fuzzymodo_selector_v1",
    "itir_overlays_casey_workspace_v1",
    "itir_overlays_itir_mission_graph_v1",
    "itir_overlays_other",
)
INAT_PHASE_CODES = ("upward_knee", "rising", "peak", "declining", "stable", "insufficient_data", "no_activity")
INAT_EXPECTATION_CODES = ("expect_more", "at_or_near_peak", "expect_less", "stable_or_unclear", "insufficient_data")
LIFETIME_STATE_SUMMARY_KEYS = (
    "raw_events",
    "compressed_events",
    "junk_events_raw",
    "junk_events_compressed",
    "state_json_bytes",
)
NOTES_LIFECYCLE_ENTITIES = ("notebook", "file", "context", "unknown")
NOTES_LIFECYCLE_OPS = ("created", "modified", "moved", "deleted", "seen", "other")
WATERFALL_PALETTES: dict[str, tuple[str, ...]] = {
    # Matplotlib-style perceptual gradients.
    "viridis": (
        "#440154",
        "#414487",
        "#2a788e",
        "#22a884",
        "#7ad151",
        "#fde725",
    ),
    # Rainbow-like but smoother and more uniform than jet.
    "turbo": (
        "#30123b",
        "#4145ab",
        "#4675ed",
        "#39a2fc",
        "#1bcfd4",
        "#24eca6",
        "#61fc6c",
        "#a4fc3c",
        "#d9e335",
        "#f8ba2f",
        "#f88727",
        "#e6531a",
        "#c52f0f",
        "#900c00",
    ),
    # Blue -> pink -> yellow style.
    "plasma": (
        "#0d0887",
        "#5b02a3",
        "#9a179b",
        "#cb4679",
        "#ed7953",
        "#fdb42f",
        "#f0f921",
    ),
    # Red/Yellow/Green diverging.
    "rdylgn": (
        "#a50026",
        "#d73027",
        "#f46d43",
        "#fdae61",
        "#fee08b",
        "#d9ef8b",
        "#a6d96a",
        "#66bd63",
        "#1a9850",
        "#006837",
    ),
}
CHAT_FLOW_COLORS = WATERFALL_PALETTES["viridis"]
TOKEN_EST_CHARS_PER_TOKEN = 4.0
DEFAULT_CONTEXT_WINDOW_TOKENS = 128000
REFERENCE_CONTEXT_WINDOWS = (32000, 128000, 200000)
INDICATIVE_COST_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "budget",
        "label": "Budget (Indicative)",
        "input_usd_per_mtok": 1.0,
        "output_usd_per_mtok": 4.0,
    },
    {
        "id": "standard",
        "label": "Standard (Indicative)",
        "input_usd_per_mtok": 5.0,
        "output_usd_per_mtok": 15.0,
    },
    {
        "id": "premium",
        "label": "Premium (Indicative)",
        "input_usd_per_mtok": 15.0,
        "output_usd_per_mtok": 75.0,
    },
)
VOICE_ACTIVITY_APP_HINTS = (
    "whisper",
    "transcrib",
    "dictat",
    "voice",
    "speech",
    "microphone",
    "mic",
    "zoom",
    "meet",
    "teams",
    "otter",
    "obs",
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


def _empty_notes_lifecycle_counts() -> dict[str, dict[str, int]]:
    return {
        entity: {op: 0 for op in NOTES_LIFECYCLE_OPS}
        for entity in NOTES_LIFECYCLE_ENTITIES
    }


def _empty_notes_meta_summary() -> dict[str, Any]:
    return {
        "total_events": 0,
        "notebooklm_events": 0,
        "app_counts": {},
        "lifecycle": _empty_notes_lifecycle_counts(),
        "warnings": [],
    }


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


def _safe_int(value: object, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: int, denominator: int, digits: int = 2) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), digits)


def _estimate_tokens_from_chars(chars: int, *, chars_per_token: float = TOKEN_EST_CHARS_PER_TOKEN) -> int:
    safe_chars = max(0, int(chars))
    safe_cpt = chars_per_token if chars_per_token > 0 else TOKEN_EST_CHARS_PER_TOKEN
    return max(1, int(round(float(safe_chars) / float(safe_cpt)))) if safe_chars > 0 else 0


def _estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    input_usd_per_mtok: float,
    output_usd_per_mtok: float,
) -> float:
    input_cost = (max(0, int(input_tokens)) / 1_000_000.0) * max(0.0, float(input_usd_per_mtok))
    output_cost = (max(0, int(output_tokens)) / 1_000_000.0) * max(0.0, float(output_usd_per_mtok))
    return round(input_cost + output_cost, 4)


def _build_chat_context_usage(
    chat_events: list[TimelineEvent],
    *,
    default_window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS,
    reference_windows: tuple[int, ...] = REFERENCE_CONTEXT_WINDOWS,
) -> dict[str, Any]:
    if not chat_events:
        return {
            "messages": 0,
            "threads": 0,
            "chars_est": 0,
            "tokens_est": 0,
            "input_tokens_est": 0,
            "output_tokens_est": 0,
            "other_tokens_est": 0,
            "default_context_window_tokens": max(1, int(default_window_tokens)),
            "reference_context_windows": [max(1, int(value)) for value in reference_windows],
            "overflow_threads": 0,
            "overflow_tokens": 0,
            "max_thread_usage_pct": 0.0,
            "threads_usage": [],
            "window_summary": [],
            "token_estimation": {
                "chars_per_token": TOKEN_EST_CHARS_PER_TOKEN,
                "method": "max(1, round(chars/4.0)) when chars > 0",
            },
        }

    ordered = sorted((event for event in chat_events if event.kind == "chat"), key=lambda item: item.dt)
    thread_usage: dict[str, dict[str, Any]] = {}
    total_chars = 0
    total_tokens = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_other_tokens = 0

    for event in ordered:
        meta = event.meta if isinstance(event.meta, dict) else {}
        thread_id = str(meta.get("thread_id") or "").strip().lower()
        thread_title = _resolve_thread_title(meta.get("thread_title"), meta.get("thread_first_user_preview"))
        thread_key = thread_id or f"untitled:{thread_title.lower()}"
        role_text = str(meta.get("role") or "unknown").strip().lower() or "unknown"

        chars = _safe_int(meta.get("chars"), fallback=0)
        if chars <= 0:
            chars = len(str(meta.get("preview") or ""))
        tokens = _estimate_tokens_from_chars(chars)
        total_chars += chars
        total_tokens += tokens
        if role_text == "user":
            total_input_tokens += tokens
        elif role_text in {"assistant", "tool"}:
            total_output_tokens += tokens
        else:
            total_other_tokens += tokens

        entry = thread_usage.setdefault(
            thread_key,
            {
                "thread_key": thread_key,
                "thread_id": thread_id,
                "thread_title": thread_title,
                "message_count": 0,
                "chars_est": 0,
                "tokens_est": 0,
                "input_tokens_est": 0,
                "output_tokens_est": 0,
                "other_tokens_est": 0,
                "first_ts": _iso_utc(event.dt),
                "last_ts": _iso_utc(event.dt),
            },
        )
        entry["message_count"] += 1
        entry["chars_est"] += chars
        entry["tokens_est"] += tokens
        if role_text == "user":
            entry["input_tokens_est"] += tokens
        elif role_text in {"assistant", "tool"}:
            entry["output_tokens_est"] += tokens
        else:
            entry["other_tokens_est"] += tokens
        entry["first_ts"] = min(str(entry.get("first_ts") or ""), _iso_utc(event.dt))
        entry["last_ts"] = max(str(entry.get("last_ts") or ""), _iso_utc(event.dt))

    windows = sorted({max(1, int(default_window_tokens)), *[max(1, int(value)) for value in reference_windows]})
    window_summary: list[dict[str, Any]] = []
    max_thread_usage = 0.0
    default_overflow_threads = 0
    default_overflow_tokens = 0

    for window_tokens in windows:
        overflow_threads = 0
        overflow_tokens = 0
        max_usage = 0.0
        for entry in thread_usage.values():
            thread_tokens = _safe_int(entry.get("tokens_est"))
            usage = _ratio(thread_tokens, window_tokens, digits=3)
            max_usage = max(max_usage, usage)
            if thread_tokens > window_tokens:
                overflow_threads += 1
                overflow_tokens += (thread_tokens - window_tokens)
            if window_tokens == max(1, int(default_window_tokens)):
                entry["window_usage_pct"] = usage
                entry["overflow_tokens"] = max(0, thread_tokens - window_tokens)
                entry["overflow_pct"] = _ratio(max(0, thread_tokens - window_tokens), window_tokens, digits=3)
        window_summary.append(
            {
                "context_window_tokens": window_tokens,
                "overflow_threads": overflow_threads,
                "overflow_tokens": overflow_tokens,
                "max_thread_usage_pct": max_usage,
            }
        )
        if window_tokens == max(1, int(default_window_tokens)):
            default_overflow_threads = overflow_threads
            default_overflow_tokens = overflow_tokens
            max_thread_usage = max_usage

    threads_usage = sorted(
        thread_usage.values(),
        key=lambda item: (-_safe_int(item.get("tokens_est")), -_safe_int(item.get("message_count")), str(item.get("thread_title") or "")),
    )
    for entry in threads_usage:
        entry["share_tokens_pct"] = _ratio(_safe_int(entry.get("tokens_est")), max(1, total_tokens), digits=3)

    return {
        "messages": len(ordered),
        "threads": len(threads_usage),
        "chars_est": total_chars,
        "tokens_est": total_tokens,
        "input_tokens_est": total_input_tokens,
        "output_tokens_est": total_output_tokens,
        "other_tokens_est": total_other_tokens,
        "default_context_window_tokens": max(1, int(default_window_tokens)),
        "reference_context_windows": windows,
        "overflow_threads": default_overflow_threads,
        "overflow_tokens": default_overflow_tokens,
        "max_thread_usage_pct": max_thread_usage,
        "threads_usage": threads_usage,
        "window_summary": window_summary,
        "token_estimation": {
            "chars_per_token": TOKEN_EST_CHARS_PER_TOKEN,
            "method": "max(1, round(chars/4.0)) when chars > 0",
        },
    }


def _hour_key(ts: datetime) -> tuple[int, int, int, int]:
    return (ts.year, ts.month, ts.day, ts.hour)


def _count_nearby_points(
    *,
    base_dts: list[datetime],
    ref_dts: list[datetime],
    window_seconds: int,
) -> int:
    if not base_dts or not ref_dts:
        return 0
    safe_window = max(0, int(window_seconds))
    refs = sorted(int(dt.timestamp()) for dt in ref_dts)
    bases = sorted(int(dt.timestamp()) for dt in base_dts)
    ref_idx = 0
    matched = 0
    for base_ts in bases:
        lower = base_ts - safe_window
        upper = base_ts + safe_window
        while ref_idx < len(refs) and refs[ref_idx] < lower:
            ref_idx += 1
        probe = ref_idx
        found = False
        while probe < len(refs) and refs[probe] <= upper:
            found = True
            break
        if found:
            matched += 1
    return matched


def _looks_voice_activity(app_name: object) -> bool:
    lowered = str(app_name or "").strip().lower()
    if not lowered:
        return False
    return any(token in lowered for token in VOICE_ACTIVITY_APP_HINTS)


def _build_concurrency_summary(
    *,
    chat_events: list[TimelineEvent],
    media_events: list[TimelineEvent],
    input_events: list[TimelineEvent],
    activity_events: list[TimelineEvent],
    window_seconds: int = 300,
) -> dict[str, Any]:
    chat_dts = sorted(event.dt for event in chat_events)
    media_dts = sorted(event.dt for event in media_events)
    input_dts = sorted(event.dt for event in input_events)
    activity_dts = sorted(event.dt for event in activity_events)

    chat_hours = {_hour_key(dt) for dt in chat_dts}
    media_hours = {_hour_key(dt) for dt in media_dts}
    input_hours = {_hour_key(dt) for dt in input_dts}
    activity_hours = {_hour_key(dt) for dt in activity_dts}

    voice_activity_dts = []
    for event in activity_events:
        app_name = event.meta.get("primary_app") if isinstance(event.meta, dict) else ""
        if _looks_voice_activity(app_name):
            voice_activity_dts.append(event.dt)
    voice_activity_hours = {_hour_key(dt) for dt in voice_activity_dts}

    chat_media_overlap_hours = len(chat_hours & media_hours)
    chat_input_overlap_hours = len(chat_hours & input_hours)
    chat_activity_overlap_hours = len(chat_hours & activity_hours)
    voice_activity_overlap_hours = len(chat_hours & voice_activity_hours)

    chat_messages_with_media_nearby = _count_nearby_points(
        base_dts=chat_dts,
        ref_dts=media_dts,
        window_seconds=window_seconds,
    )
    chat_messages_with_input_nearby = _count_nearby_points(
        base_dts=chat_dts,
        ref_dts=input_dts,
        window_seconds=window_seconds,
    )
    chat_messages_with_voice_activity_nearby = _count_nearby_points(
        base_dts=chat_dts,
        ref_dts=voice_activity_dts,
        window_seconds=window_seconds,
    )

    return {
        "window_seconds": max(0, int(window_seconds)),
        "chat_active_hours": len(chat_hours),
        "chat_media_overlap_hours": chat_media_overlap_hours,
        "chat_media_overlap_rate": _ratio(chat_media_overlap_hours, len(chat_hours), digits=3),
        "chat_input_overlap_hours": chat_input_overlap_hours,
        "chat_input_overlap_rate": _ratio(chat_input_overlap_hours, len(chat_hours), digits=3),
        "chat_activity_overlap_hours": chat_activity_overlap_hours,
        "chat_activity_overlap_rate": _ratio(chat_activity_overlap_hours, len(chat_hours), digits=3),
        "voice_activity_events": len(voice_activity_dts),
        "voice_activity_overlap_hours": voice_activity_overlap_hours,
        "voice_activity_overlap_rate": _ratio(voice_activity_overlap_hours, len(chat_hours), digits=3),
        "chat_messages_with_media_nearby": chat_messages_with_media_nearby,
        "chat_messages_with_media_nearby_rate": _ratio(chat_messages_with_media_nearby, len(chat_dts), digits=3),
        "chat_messages_with_input_nearby": chat_messages_with_input_nearby,
        "chat_messages_with_input_nearby_rate": _ratio(chat_messages_with_input_nearby, len(chat_dts), digits=3),
        "chat_messages_with_voice_activity_nearby": chat_messages_with_voice_activity_nearby,
        "chat_messages_with_voice_activity_nearby_rate": _ratio(chat_messages_with_voice_activity_nearby, len(chat_dts), digits=3),
    }


def _format_seconds_compact(seconds: int) -> str:
    total = max(0, _safe_int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


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
    if ".chat_archive.sqlite" in lowered or ("chat-export-structurer" in lowered and ".sqlite" in lowered):
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


def _split_shell_tokens(command: str) -> list[str]:
    text = str(command or "").strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _command_start_index(tokens: list[str]) -> int:
    if not tokens:
        return 0
    idx = 0
    if tokens[0].lower() == "env":
        idx = 1
        while idx < len(tokens) and tokens[idx].startswith("-"):
            idx += 1
    while idx < len(tokens) and ENV_ASSIGN_RE.match(tokens[idx]):
        idx += 1
    return idx


def _command_prefix(command: str) -> str:
    tokens = _split_shell_tokens(command)
    if not tokens:
        return ""
    start_idx = _command_start_index(tokens)
    if start_idx <= 0:
        return ""
    return " ".join(tokens[:start_idx])


def _command_without_prefix(command: str) -> str:
    tokens = _split_shell_tokens(command)
    if not tokens:
        return ""
    start_idx = _command_start_index(tokens)
    if start_idx >= len(tokens):
        return ""
    return " ".join(tokens[start_idx:])


def _command_family(command: str) -> str:
    text = str(command or "").strip()
    if not text:
        return "(empty)"
    tokens = _split_shell_tokens(text)
    if not tokens:
        return "(empty)"
    start_idx = _command_start_index(tokens)
    if start_idx >= len(tokens):
        return os.path.basename(tokens[0]).lower()
    tokens = tokens[start_idx:]

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
    tokens = _split_shell_tokens(text)
    if not tokens:
        return "other", "(empty)"
    start_idx = _command_start_index(tokens)
    if start_idx >= len(tokens):
        return "other", _preview_text(text, max_chars=120)
    tokens = tokens[start_idx:]
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


def _empty_agent_edit_summary() -> dict[str, Any]:
    return {
        "source": "none",
        "messages_scanned": 0,
        "messages_with_edits": 0,
        "edit_blocks": 0,
        "files_touched": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "top_file_share": 0.0,
        "avg_edits_per_file": 0.0,
        "focus_mode": "none",
        "files": [],
        "warnings": [],
    }


def _extract_agent_edit_blocks(text: str) -> list[dict[str, Any]]:
    lines = str(text or "").splitlines()
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in lines:
        header = AGENT_EDIT_HEADER_RE.match(line)
        if header:
            if current:
                blocks.append(current)
            current = {
                "path": _collapse_ws(header.group("path")),
                "added": _safe_int(header.group("added")),
                "removed": _safe_int(header.group("removed")),
                "line_numbers": [],
            }
            continue
        if current is None:
            continue
        line_match = AGENT_EDIT_LINE_RE.match(line)
        if line_match:
            line_no = _safe_int(line_match.group("line"))
            if line_no > 0:
                current["line_numbers"].append(line_no)

    if current:
        blocks.append(current)

    normalized: list[dict[str, Any]] = []
    for item in blocks:
        path = _collapse_ws(item.get("path"))
        if not path:
            continue
        deduped_line_numbers = sorted(set(_safe_int(v) for v in item.get("line_numbers") or []))
        normalized.append(
            {
                "path": path,
                "added": _safe_int(item.get("added")),
                "removed": _safe_int(item.get("removed")),
                "line_numbers": [v for v in deduped_line_numbers if v > 0][:40],
            }
        )
    return normalized


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


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _available_run_dates(
    *,
    runs_root: Path,
    end_date_text: str | None = None,
    start_date_text: str | None = None,
) -> list[str]:
    end_date = date_cls.fromisoformat(end_date_text) if end_date_text else None
    start_date = date_cls.fromisoformat(start_date_text) if start_date_text else None

    dates: list[str] = []
    if not runs_root.exists():
        return dates
    for child in runs_root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if not RUN_DATE_RE.match(name):
            continue
        try:
            run_date = date_cls.fromisoformat(name)
        except ValueError:
            continue
        if end_date and run_date > end_date:
            continue
        if start_date and run_date < start_date:
            continue
        dates.append(name)
    dates.sort()
    return dates


def _daily_output_paths(*, runs_root: Path, date_text: str, include_all_chat: bool) -> tuple[Path, Path]:
    suffix = "_all" if include_all_chat else ""
    out_dir = runs_root / date_text / "outputs"
    return (out_dir / f"dashboard{suffix}.json", out_dir / f"dashboard{suffix}.html")


def _estimate_state_volume(*, state_payload: dict[str, Any], state_path: Path) -> dict[str, Any]:
    events = state_payload.get("events")
    if not isinstance(events, list):
        events = []

    raw_events = 0
    compressed_events = 0
    junk_events_raw = 0
    junk_events_compressed = 0

    for item in events:
        if not isinstance(item, dict):
            continue
        compressed_events += 1

        collapsed_count = _safe_int(item.get("collapsed_count"), fallback=1)
        collapsed_ids = item.get("collapsed_ids")
        if isinstance(collapsed_ids, list):
            collapsed_count = max(
                collapsed_count,
                len([entry for entry in collapsed_ids if str(entry or "").strip()]),
            )
        expanded_count = max(1, collapsed_count)
        raw_events += expanded_count

        is_junk = bool(item.get("low_signal"))
        if is_junk:
            junk_events_compressed += 1
            junk_events_raw += expanded_count

    state_bytes = state_path.stat().st_size if state_path.exists() else 0
    compression_ratio = _ratio(compressed_events, raw_events, digits=3)
    expansion_ratio = _ratio(raw_events, compressed_events, digits=3)
    junk_share_raw = _ratio(junk_events_raw, raw_events, digits=3)
    junk_share_compressed = _ratio(junk_events_compressed, compressed_events, digits=3)

    return {
        "raw_events": raw_events,
        "compressed_events": compressed_events,
        "junk_events_raw": junk_events_raw,
        "junk_events_compressed": junk_events_compressed,
        "state_json_bytes": state_bytes,
        "compression_ratio": compression_ratio,
        "expansion_ratio": expansion_ratio,
        "junk_share_raw": junk_share_raw,
        "junk_share_compressed": junk_share_compressed,
    }


def _load_or_build_daily_payload(
    *,
    date_text: str,
    repo_root: Path,
    runs_root: Path,
    context_root: Path,
    convo_ids_path: Path,
    chat_db_path: Path,
    chat_exports_dir: Path,
    max_timeline_events: int,
    include_all_chat: bool,
) -> dict[str, Any]:
    # DB-first cache: the canonical store for dashboards is SQLite under runs_root.
    # JSON files are legacy/regression exports and should not be written implicitly
    # during higher-level aggregation (weekly/lifetime) builds.
    from sb.dashboard_store_sqlite import DashboardKey, load_dashboard_payload, upsert_dashboard_payload

    scope = "all" if include_all_chat else "scoped"
    db_path = runs_root / "dashboard.sqlite"
    cached_db = load_dashboard_payload(
        db_path=db_path,
        key=DashboardKey(date=date_text, view="daily", scope=scope, window_days=0),
    )
    if cached_db is not None:
        summary = cached_db.get("summary") if isinstance(cached_db.get("summary"), dict) else {}
        if "shell_commands_agent_exec" in summary and "shell_commands_host" in summary:
            return cached_db

    # Back-compat migration path: if legacy JSON exists, import it into the DB once.
    daily_json_path, _daily_html_path = _daily_output_paths(
        runs_root=runs_root,
        date_text=date_text,
        include_all_chat=include_all_chat,
    )
    cached_json = _load_json_dict(daily_json_path)
    if cached_json is not None:
        upsert_dashboard_payload(
            db_path=db_path,
            key=DashboardKey(date=date_text, view="daily", scope=scope, window_days=0),
            payload=cached_json,
        )
        return cached_json

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
    upsert_dashboard_payload(
        db_path=db_path,
        key=DashboardKey(date=date_text, view="daily", scope=scope, window_days=0),
        payload=payload,
    )
    return payload


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


def _sqlite_chat_day_diagnostics(
    *,
    db_path: Path,
    date_text: str,
) -> dict[str, Any]:
    diag = {
        "db_exists": db_path.exists(),
        "day_count": 0,
        "max_ts": "",
    }
    if not db_path.exists():
        return diag

    uri = f"file:{db_path.resolve()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return diag
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM messages WHERE substr(ts, 1, 10) = ?", (date_text,))
            row = cur.fetchone()
            if row:
                diag["day_count"] = _safe_int(row[0])
        except sqlite3.Error:
            pass
        try:
            cur.execute("SELECT MAX(ts) FROM messages")
            row = cur.fetchone()
            if row and row[0]:
                diag["max_ts"] = str(row[0])
        except sqlite3.Error:
            pass
    finally:
        conn.close()
    return diag


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
        sqlite_diag = _sqlite_chat_day_diagnostics(db_path=chat_db_path, date_text=date_text)
        if not sqlite_diag.get("db_exists"):
            warnings.append("Chat sqlite archive not found; run chat export ingestion or set --chat-db.")
        else:
            day_count = _safe_int(sqlite_diag.get("day_count"))
            max_ts = str(sqlite_diag.get("max_ts") or "")
            if day_count > 0 and thread_scope:
                warnings.append(
                    f"Chat archive has {day_count} message(s) on {date_text} but none matched current convo scope; refresh convo_ids or run --debug-include-all-chat."
                )
            elif day_count == 0 and max_ts:
                warnings.append(
                    f"Chat archive has 0 messages on {date_text}; latest archived message is {max_ts}. Sync/import newer chats."
                )
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
    empty_summary = {
        "source": "none",
        "total_tool_messages": 0,
        "exec_command_count": 0,
        "exec_with_workdir_count": 0,
        "exec_without_workdir_count": 0,
        "unique_commands": 0,
        "families": [],
        "top_dirs": [],
        "warnings": [],
    }
    if not db_path.exists():
        result = dict(empty_summary)
        result["warnings"] = ["Tool-use summary unavailable: sqlite archive not found."]
        return result

    thread_ids = set(thread_scope.keys())
    title_filters = [title.lower() for title in thread_scope.values() if title]
    uri = f"file:{db_path.resolve()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        result = dict(empty_summary)
        result["warnings"] = ["Tool-use summary unavailable: failed to open sqlite archive."]
        return result

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
            result = dict(empty_summary)
            result["warnings"] = [
                "Tool-use summary unavailable: sqlite query failed for this date."
            ]
            return result
    finally:
        conn.close()

    total_tool_messages = 0
    exec_command_count = 0
    exec_with_workdir_count = 0
    exec_without_workdir_count = 0
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
            exec_with_workdir_count += 1
            dirs.append(workdir)
        else:
            exec_without_workdir_count += 1
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
        else:
            prefix_totals: Counter[str] = Counter()
            prefix_details: dict[str, Counter[str]] = {}
            for variant_command, variant_count in variants.items():
                prefix = _command_prefix(variant_command)
                if not prefix:
                    continue
                detail = _command_without_prefix(variant_command) or "(empty)"
                prefix_totals[prefix] += int(variant_count)
                prefix_details.setdefault(prefix, Counter())[detail] += int(variant_count)

            for prefix, prefix_count in prefix_totals.most_common(top_variants):
                detail_rows = [
                    {"detail": detail, "count": int(detail_count)}
                    for detail, detail_count in prefix_details.get(prefix, Counter()).most_common(top_variants)
                ]
                variant_groups.append(
                    {
                        "group": prefix,
                        "count": int(prefix_count),
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
        "exec_with_workdir_count": int(exec_with_workdir_count),
        "exec_without_workdir_count": int(exec_without_workdir_count),
        "unique_commands": int(len(all_command_counts)),
        "families": families,
        "top_dirs": [
            {"path": path, "count": int(count)}
            for path, count in dir_counts.most_common(top_dirs)
        ],
        "warnings": warnings,
    }


def _summarize_agent_edit_blocks(blocks: list[dict[str, Any]], *, source: str, messages_scanned: int, messages_with_edits: int) -> dict[str, Any]:
    if not blocks:
        summary = _empty_agent_edit_summary()
        summary["source"] = source
        summary["messages_scanned"] = int(messages_scanned)
        summary["messages_with_edits"] = int(messages_with_edits)
        return summary

    per_file: dict[str, dict[str, Any]] = {}
    lines_added = 0
    lines_removed = 0
    for block in blocks:
        path = _collapse_ws(block.get("path"))
        if not path:
            continue
        added = _safe_int(block.get("added"))
        removed = _safe_int(block.get("removed"))
        total = added + removed
        lines_added += added
        lines_removed += removed
        line_numbers = [v for v in (block.get("line_numbers") or []) if _safe_int(v) > 0]

        row = per_file.setdefault(
            path,
            {"path": path, "blocks": 0, "lines_added": 0, "lines_removed": 0, "line_numbers": set()},
        )
        row["blocks"] = _safe_int(row.get("blocks")) + 1
        row["lines_added"] = _safe_int(row.get("lines_added")) + added
        row["lines_removed"] = _safe_int(row.get("lines_removed")) + removed
        row["line_numbers"].update(line_numbers)
        row["total_edits"] = _safe_int(row.get("lines_added")) + _safe_int(row.get("lines_removed"))

    file_rows = sorted(
        (
            {
                "path": data["path"],
                "blocks": _safe_int(data.get("blocks")),
                "lines_added": _safe_int(data.get("lines_added")),
                "lines_removed": _safe_int(data.get("lines_removed")),
                "total_edits": _safe_int(data.get("total_edits")),
                "line_numbers": sorted(int(v) for v in data.get("line_numbers", set()) if _safe_int(v) > 0)[:40],
            }
            for data in per_file.values()
        ),
        key=lambda item: (-_safe_int(item.get("total_edits")), -_safe_int(item.get("blocks")), str(item.get("path"))),
    )
    total_edits = max(1, sum(_safe_int(item.get("total_edits")) for item in file_rows))
    for row in file_rows:
        row["share"] = _ratio(_safe_int(row.get("total_edits")), total_edits, digits=3)

    top_share = _safe_float(file_rows[0].get("share")) if file_rows else 0.0
    if top_share >= 0.7:
        focus_mode = "single-file-heavy"
    elif top_share >= 0.45:
        focus_mode = "mixed"
    else:
        focus_mode = "spread"

    return {
        "source": source,
        "messages_scanned": int(messages_scanned),
        "messages_with_edits": int(messages_with_edits),
        "edit_blocks": len(blocks),
        "files_touched": len(file_rows),
        "lines_added": int(lines_added),
        "lines_removed": int(lines_removed),
        "top_file_share": round(top_share, 3),
        "avg_edits_per_file": _ratio(total_edits, max(1, len(file_rows)), digits=2),
        "focus_mode": focus_mode,
        "files": file_rows[:80],
        "warnings": [],
    }


def _load_agent_edit_summary_sqlite(
    *,
    db_path: Path,
    date_text: str,
    thread_scope: dict[str, str],
) -> dict[str, Any]:
    empty = _empty_agent_edit_summary()
    if not db_path.exists():
        empty["warnings"] = ["Agent edit summary unavailable: sqlite archive not found."]
        return empty

    thread_ids = set(thread_scope.keys())
    title_filters = [title.lower() for title in thread_scope.values() if title]
    uri = f"file:{db_path.resolve()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        empty["warnings"] = ["Agent edit summary unavailable: failed to open sqlite archive."]
        return empty

    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT canonical_thread_id, title, role, text
                FROM messages
                WHERE substr(ts, 1, 10) = ?
                  AND text IS NOT NULL
                  AND TRIM(text) <> ''
                  AND role IN ('assistant', 'tool')
                ORDER BY ts ASC
                """,
                (date_text,),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            empty["warnings"] = ["Agent edit summary unavailable: sqlite query failed for this date."]
            return empty
    finally:
        conn.close()

    blocks: list[dict[str, Any]] = []
    messages_scanned = 0
    messages_with_edits = 0
    for canonical_thread_id, title, _role, text in rows:
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
        messages_scanned += 1
        parsed = _extract_agent_edit_blocks(str(text or ""))
        if not parsed:
            continue
        messages_with_edits += 1
        blocks.extend(parsed)

    summary = _summarize_agent_edit_blocks(
        blocks,
        source="sqlite",
        messages_scanned=messages_scanned,
        messages_with_edits=messages_with_edits,
    )
    if messages_scanned == 0:
        summary["warnings"] = ["No in-scope assistant/tool messages found for agent edit parsing."]
    elif messages_with_edits == 0:
        summary["warnings"] = ["No `Edited <file> (+a -b)` patterns found in in-scope assistant/tool messages."]
    return summary


def _load_agent_edit_summary_from_chat_events(chat_events: list[TimelineEvent]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    messages_scanned = 0
    messages_with_edits = 0
    for event in chat_events:
        if not isinstance(event.meta, dict):
            continue
        if str(event.meta.get("role") or "").strip().lower() != "assistant":
            continue
        messages_scanned += 1
        preview_text = str(event.meta.get("preview") or "")
        parsed = _extract_agent_edit_blocks(preview_text)
        if not parsed:
            continue
        messages_with_edits += 1
        blocks.extend(parsed)
    summary = _summarize_agent_edit_blocks(
        blocks,
        source="chat_preview",
        messages_scanned=messages_scanned,
        messages_with_edits=messages_with_edits,
    )
    if summary.get("edit_blocks", 0):
        summary["warnings"] = [
            "Agent edit summary derived from truncated chat previews; line-number/detail completeness may be limited."
        ]
    return summary


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


def _load_calendar_events(path: Path) -> tuple[list[TimelineEvent], int]:
    events: list[TimelineEvent] = []
    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        event_type = str(row.get("type") or "unknown")
        duration_min = _safe_int(row.get("duration_min"))
        # Calendar "text" may include sensitive content; keep meta-only in dashboards.
        detail = f"calendar type={event_type} duration_min={duration_min}"
        events.append(TimelineEvent(dt=dt, kind="calendar", detail=detail, source_path=str(path)))
    return events, len(events)


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
        primary_app = str(item.get("primary_app") or "")
        t_end = _parse_ts(item.get("t_end"))
        duration_s = 0
        if t_end is not None:
            duration_s = max(0, int((t_end - dt).total_seconds()))
        detail = f"activity app={primary_app} duration_s={duration_s}"
        events.append(
            TimelineEvent(
                dt=dt,
                kind="activity",
                detail=detail,
                source_path=str(path),
                meta={
                    "primary_app": primary_app,
                    "duration_s": duration_s,
                    "t_end": _iso_utc(t_end) if t_end is not None else "",
                },
            )
        )
    return events, len(events)


def _load_media_events_and_summary(path: Path) -> tuple[list[TimelineEvent], dict[str, Any]]:
    events: list[TimelineEvent] = []
    observations: list[dict[str, Any]] = []
    by_platform: dict[str, dict[str, int]] = {}
    warnings: list[str] = []

    for row in _load_jsonl(path):
        dt = _parse_ts(row.get("ts"))
        if dt is None:
            continue
        platform = str(row.get("platform") or "unknown").strip().lower() or "unknown"
        event_type = str(row.get("event_type") or "playback_observed").strip().lower() or "playback_observed"
        item_id_hash = str(row.get("item_id_hash") or "").strip()
        consumed_seconds = max(0, _safe_int(row.get("consumed_seconds")))
        content_seconds = max(0, _safe_int(row.get("content_duration_seconds")))
        completion_ratio = _safe_float(row.get("completion_ratio"))
        if completion_ratio <= 0.0 and content_seconds > 0:
            completion_ratio = float(consumed_seconds) / float(content_seconds)
        completion_ratio = round(max(0.0, completion_ratio), 3)

        detail = (
            f"media platform={platform} event={event_type} consumed_s={consumed_seconds} "
            f"duration_s={content_seconds} completion={completion_ratio:.3f}"
        )
        events.append(
            TimelineEvent(
                dt=dt,
                kind="media",
                detail=detail,
                source_path=str(path),
                meta={
                    "platform": platform,
                    "event_type": event_type,
                    "item_id_hash": item_id_hash,
                    "consumed_seconds": consumed_seconds,
                    "content_duration_seconds": content_seconds,
                    "completion_ratio": completion_ratio,
                },
            )
        )
        observations.append(
            {
                "dt": dt,
                "platform": platform,
                "event_type": event_type,
                "item_id_hash": item_id_hash,
                "consumed_seconds": consumed_seconds,
                "content_duration_seconds": content_seconds,
                "completion_ratio": completion_ratio,
            }
        )
        if platform not in by_platform:
            by_platform[platform] = {
                "events": 0,
                "items_observed": 0,
                "consumed_seconds": 0,
                "content_duration_seconds": 0,
            }
        by_platform[platform]["events"] += 1
        by_platform[platform]["consumed_seconds"] += consumed_seconds
        by_platform[platform]["content_duration_seconds"] += content_seconds

    observations.sort(key=lambda item: item["dt"])
    item_set: set[str] = set()
    for item in observations:
        key = str(item.get("item_id_hash") or "").strip()
        if key:
            item_set.add(key)

    platform_item_sets: dict[str, set[str]] = {platform: set() for platform in by_platform}
    for item in observations:
        platform = item["platform"]
        key = str(item.get("item_id_hash") or "").strip()
        if key:
            platform_item_sets.setdefault(platform, set()).add(key)
    for platform, counters in by_platform.items():
        counters["items_observed"] = len(platform_item_sets.get(platform, set()))

    churn_events = 0
    for idx, item in enumerate(observations[:-1]):
        next_item = observations[idx + 1]
        ratio = _safe_float(item.get("completion_ratio"))
        current_id = str(item.get("item_id_hash") or "").strip()
        next_id = str(next_item.get("item_id_hash") or "").strip()
        if not current_id or not next_id or current_id == next_id:
            continue
        gap_seconds = int((next_item["dt"] - item["dt"]).total_seconds())
        if ratio < 0.35 and gap_seconds <= 900:
            churn_events += 1

    consumed_total = sum(_safe_int(item.get("consumed_seconds")) for item in observations)
    content_total = sum(_safe_int(item.get("content_duration_seconds")) for item in observations)
    if observations and not any(str(item.get("item_id_hash") or "").strip() for item in observations):
        warnings.append("media rows missing item_id_hash; churn and unique-item metrics may be understated")

    summary = {
        "events": len(observations),
        "items_observed": len(item_set),
        "consumed_seconds": consumed_total,
        "content_duration_seconds": content_total,
        "completion_ratio": _ratio(consumed_total, content_total, digits=3),
        "churn_events": churn_events,
        "churn_rate": _ratio(churn_events, max(1, len(item_set)), digits=3),
        "by_platform": by_platform,
        "warnings": warnings,
    }
    return events, summary


def _notes_event_entity_and_operation(
    event_name: object,
    *,
    note_id_hash: object,
    notebook_id_hash: object,
) -> tuple[str, str]:
    lowered = str(event_name or "").strip().lower()

    if "context" in lowered:
        entity = "context"
    elif "notebook" in lowered:
        entity = "notebook"
    elif any(token in lowered for token in ("source", "file", "note")):
        entity = "file"
    elif str(note_id_hash or "").strip():
        entity = "file"
    elif str(notebook_id_hash or "").strip():
        entity = "notebook"
    else:
        entity = "unknown"

    if any(token in lowered for token in ("move", "moved", "rename", "renamed", "relocat")):
        operation = "moved"
    elif any(token in lowered for token in ("delete", "deleted", "remove", "removed", "trash", "archiv")):
        operation = "deleted"
    elif any(token in lowered for token in ("create", "created", "add", "added", "import", "upload", "new")):
        operation = "created"
    elif any(token in lowered for token in ("modify", "modified", "update", "updated", "edit", "edited", "change", "changed", "status")):
        operation = "modified"
    elif any(token in lowered for token in ("observed", "seen", "snapshot", "listed", "list", "discover")):
        operation = "seen"
    else:
        operation = "other"

    return entity, operation


def _load_notes_meta_summary(path: Path) -> dict[str, Any]:
    summary = _empty_notes_meta_summary()
    if not path.exists():
        return summary

    app_counts: dict[str, int] = {}
    lifecycle = summary.get("lifecycle")
    lifecycle_counts = lifecycle if isinstance(lifecycle, dict) else _empty_notes_lifecycle_counts()
    warnings: list[str] = []

    for row in _load_jsonl(path):
        if not isinstance(row, dict):
            continue
        app = str(row.get("app") or "unknown").strip().lower() or "unknown"
        event_name = str(row.get("event") or row.get("event_type") or "unknown").strip().lower()
        app_counts[app] = app_counts.get(app, 0) + 1
        summary["total_events"] = _safe_int(summary.get("total_events")) + 1

        if app != "notebooklm":
            continue

        summary["notebooklm_events"] = _safe_int(summary.get("notebooklm_events")) + 1
        entity, operation = _notes_event_entity_and_operation(
            event_name,
            note_id_hash=row.get("note_id_hash"),
            notebook_id_hash=row.get("notebook_id_hash"),
        )
        if entity not in lifecycle_counts:
            lifecycle_counts[entity] = {op: 0 for op in NOTES_LIFECYCLE_OPS}
        if operation not in lifecycle_counts[entity]:
            lifecycle_counts[entity][operation] = 0
        lifecycle_counts[entity][operation] += 1
        if entity == "unknown":
            warnings.append(f"unclassified notebooklm event='{event_name or 'unknown'}'")

    summary["app_counts"] = app_counts
    summary["lifecycle"] = lifecycle_counts
    summary["warnings"] = warnings
    return summary


def _load_context_field_rows(path: Path) -> list[dict[str, Any]]:
    rows = _load_jsonl(path)
    return [row for row in rows if isinstance(row, dict) and row.get("signal") == "context_field"]


def _summarize_inaturalist_day(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_events = 0
    insect_obs = 0
    for row in rows:
        if str(row.get("context_type") or "").strip().lower() != "inaturalist":
            continue
        total_events += 1
        count = _safe_int(row.get("obs_count"), fallback=1)
        if _safe_int(row.get("insect_flag")) == 1:
            insect_obs += max(1, count)
    return {"events": total_events, "insect_observations": insect_obs}


def _summarize_mood_day(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reports = 0
    latest: dict[str, Any] | None = None
    latest_dt: datetime | None = None
    for row in rows:
        if str(row.get("context_type") or "").strip().lower() != "mood":
            continue
        reports += 1
        dt = _parse_ts(row.get("ts"))
        if dt and (latest_dt is None or dt > latest_dt):
            latest_dt = dt
            latest = row
    latest_out = {}
    if latest:
        latest_out = {
            "ts": str(latest.get("ts") or ""),
            "mood_code": str(latest.get("mood_code") or "unknown"),
            "valence_score": _safe_float(latest.get("valence_score")),
            "arousal_score": _safe_float(latest.get("arousal_score")),
            "energy_score": _safe_float(latest.get("energy_score")),
            "stress_score": _safe_float(latest.get("stress_score")),
            "anxiety_score": _safe_float(latest.get("anxiety_score")),
        }
    return {"reports": reports, "latest": latest_out}


def _classify_inat_phase(counts: list[int]) -> tuple[str, str, dict[str, Any]]:
    # Deterministic, coarse heuristic. Operates on daily insect counts.
    if not counts:
        return ("insufficient_data", "insufficient_data", {})
    if all(value <= 0 for value in counts):
        return ("no_activity", "stable_or_unclear", {"max": 0})
    if len(counts) < 14:
        return ("insufficient_data", "insufficient_data", {"days": len(counts)})

    def avg(window: list[int]) -> float:
        return float(sum(window)) / float(max(1, len(window)))

    recent = avg(counts[-7:])
    prev = avg(counts[-14:-7])
    earlier = avg(counts[-21:-14]) if len(counts) >= 21 else prev
    max_val = max(counts)
    if max_val <= 0:
        return ("no_activity", "stable_or_unclear", {"max": 0})

    # Slope proxy: recent vs prev week.
    ratio = recent / max(1e-9, prev)
    near_peak = recent >= (0.9 * float(max_val))

    phase = "stable"
    if near_peak and ratio <= 1.15 and prev > 0:
        phase = "peak"
    elif ratio >= 1.8 and prev <= max(1.0, 0.4 * float(max_val)) and earlier <= prev:
        phase = "upward_knee"
    elif ratio >= 1.15:
        phase = "rising"
    elif ratio <= 0.85 and prev >= 1.0:
        phase = "declining"
    else:
        phase = "stable"

    expectation = "stable_or_unclear"
    if phase in {"upward_knee", "rising"}:
        expectation = "expect_more"
    elif phase == "peak":
        expectation = "at_or_near_peak"
    elif phase == "declining":
        expectation = "expect_less"
    elif phase in {"no_activity", "stable"}:
        expectation = "stable_or_unclear"
    else:
        expectation = "insufficient_data"

    return (
        phase,
        expectation,
        {
            "recent_avg_7d": round(recent, 3),
            "prev_avg_7d": round(prev, 3),
            "earlier_avg_7d": round(earlier, 3),
            "max_daily": int(max_val),
            "recent_prev_ratio": round(ratio, 3) if prev > 0 else None,
        },
    )


def _build_inaturalist_trend(
    *,
    end_date_text: str,
    runs_root: Path,
    days: int = 42,
) -> dict[str, Any]:
    window = _date_window(end_date_text, max(1, days))
    daily = []
    counts: list[int] = []
    available = 0
    for day_text in window:
        path = runs_root / day_text / "logs" / "context" / f"{day_text}.jsonl"
        if not path.exists():
            daily.append({"date": day_text, "insect_observations": 0, "events": 0})
            counts.append(0)
            continue
        available += 1
        rows = _load_context_field_rows(path)
        summary = _summarize_inaturalist_day(rows)
        day_count = _safe_int(summary.get("insect_observations"))
        daily.append({"date": day_text, "insect_observations": day_count, "events": _safe_int(summary.get("events"))})
        counts.append(day_count)

    phase, expectation, diag = _classify_inat_phase(counts)
    return {
        "window_days": int(days),
        "available_days": int(available),
        "phase_code": phase,
        "expectation_code": expectation,
        "daily": daily,
        "diagnostics": diag,
    }


def _notebooklm_lifecycle_focus(notes_summary: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    lifecycle = notes_summary.get("lifecycle") if isinstance(notes_summary, dict) else {}
    lifecycle = lifecycle if isinstance(lifecycle, dict) else {}
    focus: dict[str, dict[str, int]] = {}
    for entity in ("notebook", "file"):
        entity_counts = lifecycle.get(entity) if isinstance(lifecycle.get(entity), dict) else {}
        focus[entity] = {op: _safe_int(entity_counts.get(op)) for op in NOTES_LIFECYCLE_OPS}
    return focus


def _merge_notes_meta_summaries(total: dict[str, Any], day: dict[str, Any] | None) -> dict[str, Any]:
    merged = _empty_notes_meta_summary()
    merged["total_events"] = _safe_int(total.get("total_events")) + _safe_int((day or {}).get("total_events"))
    merged["notebooklm_events"] = _safe_int(total.get("notebooklm_events")) + _safe_int(
        (day or {}).get("notebooklm_events")
    )

    app_counts: dict[str, int] = {}
    for source in (total.get("app_counts"), (day or {}).get("app_counts")):
        if not isinstance(source, dict):
            continue
        for app, count in source.items():
            app_key = str(app or "unknown").strip().lower() or "unknown"
            app_counts[app_key] = app_counts.get(app_key, 0) + _safe_int(count)
    merged["app_counts"] = app_counts

    lifecycle = _empty_notes_lifecycle_counts()
    for source in (total.get("lifecycle"), (day or {}).get("lifecycle")):
        if not isinstance(source, dict):
            continue
        for entity, counts in source.items():
            entity_key = str(entity or "unknown").strip().lower() or "unknown"
            if entity_key not in lifecycle:
                lifecycle[entity_key] = {op: 0 for op in NOTES_LIFECYCLE_OPS}
            if not isinstance(counts, dict):
                continue
            for op in NOTES_LIFECYCLE_OPS:
                lifecycle[entity_key][op] += _safe_int(counts.get(op))
    merged["lifecycle"] = lifecycle

    warnings: list[str] = []
    for source in (total.get("warnings"), (day or {}).get("warnings")):
        if not isinstance(source, list):
            continue
        warnings.extend(str(item) for item in source if str(item).strip())
    merged["warnings"] = warnings
    return merged


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
            "switches_per_active_hour": 0.0,
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
    thread_first_dt: dict[str, datetime] = {}
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
            thread_first_dt[thread_key] = event.dt

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
                "thread_start_ts": _iso_utc(thread_first_dt[thread_key]),
                "thread_start_hour": thread_first_dt[thread_key].hour,
                "thread_id": raw_thread_id,
                "thread_key": thread_key,
                "thread_title": thread_titles[thread_key],
                "role": role_text,
                "switch": switched,
                "color_index": color_index,
                "color_hex": CHAT_FLOW_COLORS[color_index],
            }
        )

    # Encode the elapsed time from each message to the next message so the
    # waterfall can scale segment widths by time, not only by message count.
    if waterfall_all:
        next_gaps: list[int] = []
        for idx in range(len(ordered) - 1):
            delta_seconds = int((ordered[idx + 1].dt - ordered[idx].dt).total_seconds())
            next_gaps.append(max(1, delta_seconds))
        tail_gap = next_gaps[-1] if next_gaps else 60
        next_gaps.append(max(1, tail_gap))
        for idx, item in enumerate(waterfall_all):
            item["gap_to_next_seconds"] = next_gaps[idx]

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
                "thread_start_ts": _iso_utc(thread_first_dt[thread_key]),
                "thread_start_hour": thread_first_dt[thread_key].hour,
                "thread_order": thread_order.get(thread_key, 0),
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


def _waterfall_layout(segment_count: int) -> dict[str, float]:
    if segment_count <= 120:
        return {"min_width_rem": 0.42, "max_width_rem": 5.6, "extra_width_rem": 38.0, "seg_height_rem": 0.95, "strip_gap_rem": 0.10}
    if segment_count <= 240:
        return {"min_width_rem": 0.28, "max_width_rem": 4.8, "extra_width_rem": 44.0, "seg_height_rem": 0.86, "strip_gap_rem": 0.08}
    if segment_count <= 480:
        return {"min_width_rem": 0.18, "max_width_rem": 3.8, "extra_width_rem": 52.0, "seg_height_rem": 0.78, "strip_gap_rem": 0.05}
    if segment_count <= 960:
        return {"min_width_rem": 0.12, "max_width_rem": 2.9, "extra_width_rem": 60.0, "seg_height_rem": 0.72, "strip_gap_rem": 0.03}
    return {"min_width_rem": 0.08, "max_width_rem": 2.2, "extra_width_rem": 68.0, "seg_height_rem": 0.68, "strip_gap_rem": 0.02}


def _waterfall_segment_widths(segments: list[dict[str, Any]]) -> tuple[list[float], dict[str, float]]:
    layout = _waterfall_layout(len(segments))
    if not segments:
        return ([], layout)
    min_width = layout["min_width_rem"]
    max_width = layout["max_width_rem"]
    extra_width = layout["extra_width_rem"]
    gaps = [max(1, _safe_int(item.get("gap_to_next_seconds"), fallback=60)) for item in segments]
    total_gap = max(1, sum(gaps))
    widths = [
        min(max_width, max(min_width, min_width + (extra_width * (gap / total_gap))))
        for gap in gaps
    ]
    return (widths, layout)


def _weekday_index(date_text: str) -> int:
    # Monday=0..Sunday=6 (matches datetime.weekday()).
    return datetime.strptime(date_text, "%Y-%m-%d").weekday()


def _empty_weekday_hour_matrix() -> list[list[int]]:
    return [[0 for _ in range(24)] for _ in range(7)]


def _sum_bins(freq: dict[str, list[int]], keys: Iterable[str]) -> list[int]:
    out = [0 for _ in range(24)]
    for key in keys:
        bins = freq.get(key)
        if not isinstance(bins, list) or len(bins) != 24:
            continue
        for hour in range(24):
            out[hour] += _safe_int(bins[hour])
    return out


def _build_weekday_hour_heatmaps_from_daily_payloads(
    daily_payloads: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """
    Aggregate hourly bins into a weekday (rows) x hour (cols) heatmap.

    We keep sums plus a weekday day-count so the renderer can show avg/day.
    """
    weekday_day_counts = [0 for _ in range(7)]
    lanes: tuple[str, ...] = (
        "chat",
        "shell",
        "git",
        "pr",
        "git_branch",
        "input",
        "window",
        "activity",
        "media",
        "calendar",
    )
    lane_labels = {
        "chat": "Chat",
        "shell": "Shell",
        "git": "Git commits",
        "pr": "PR events",
        "git_branch": "Git branch events",
        "input": "Input",
        "window": "Window focus",
        "activity": "Activity sessions",
        "media": "Media",
        "calendar": "Calendar",
    }
    matrices = {name: _empty_weekday_hour_matrix() for name in lanes}

    for date_text, payload in daily_payloads:
        freq = payload.get("frequency_by_hour")
        if not isinstance(freq, dict):
            continue
        weekday = _weekday_index(date_text)
        weekday_day_counts[weekday] += 1
        for lane in lanes:
            bins = freq.get(lane)
            if not isinstance(bins, list) or len(bins) != 24:
                continue
            row = matrices[lane][weekday]
            for hour in range(24):
                row[hour] += _safe_int(bins[hour])

    lane_totals = {
        lane: sum(sum(_safe_int(v) for v in row) for row in matrices.get(lane, []))
        for lane in lanes
    }
    # Default selection: "score across all" lanes that have data in the window.
    # Users can quickly narrow to an intent-oriented subset via the "Intent set" button.
    default_selected = [lane for lane in lanes if _safe_int(lane_totals.get(lane)) > 0]

    return {
        "weekday_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "weekday_day_counts": weekday_day_counts,
        "lanes": list(lanes),
        "lane_labels": lane_labels,
        "lane_totals": lane_totals,
        "default_selected": default_selected,
        "series": matrices,
    }


def _heat_level(value: float, max_value: float) -> int:
    if value <= 0 or max_value <= 0:
        return 0
    ratio = max(0.0, min(1.0, value / max_value))
    if ratio <= 0.20:
        return 1
    if ratio <= 0.40:
        return 2
    if ratio <= 0.65:
        return 3
    return 4


def _render_weekday_hour_heatmap(
    *,
    title: str,
    series_name: str,
    heatmaps: dict[str, Any],
) -> str:
    series = heatmaps.get("series") if isinstance(heatmaps.get("series"), dict) else {}
    matrix = series.get(series_name) if isinstance(series.get(series_name), list) else _empty_weekday_hour_matrix()
    weekday_names = heatmaps.get("weekday_names") if isinstance(heatmaps.get("weekday_names"), list) else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_day_counts = heatmaps.get("weekday_day_counts") if isinstance(heatmaps.get("weekday_day_counts"), list) else [0 for _ in range(7)]

    # Use avg/day per weekday for intensity, so longer windows don't just look "darker."
    max_avg = 0.0
    avg_matrix: list[list[float]] = []
    for weekday in range(7):
        denom = max(1, _safe_int(weekday_day_counts[weekday] if weekday < len(weekday_day_counts) else 0))
        row_avg = []
        for hour in range(24):
            avg = _safe_int(matrix[weekday][hour]) / float(denom)
            row_avg.append(avg)
            max_avg = max(max_avg, avg)
        avg_matrix.append(row_avg)

    hour_labels = "".join(
        f"<div class='hm-hour'>{hour:02d}</div>" if hour % 3 == 0 else "<div class='hm-hour hm-hour-muted'></div>"
        for hour in range(24)
    )
    cells: list[str] = []
    for weekday in range(7):
        name = str(weekday_names[weekday] if weekday < len(weekday_names) else weekday)
        day_count = _safe_int(weekday_day_counts[weekday] if weekday < len(weekday_day_counts) else 0)
        cells.append(f"<div class='hm-dow'>{escape(name)}</div>")
        for hour in range(24):
            total = _safe_int(matrix[weekday][hour])
            avg = avg_matrix[weekday][hour]
            level = _heat_level(avg, max_avg)
            tooltip = f"{name} {hour:02d}:00 | total={total} | avg/day={avg:.2f} (days={day_count})"
            cells.append(f"<div class='hm-cell l{level}' title='{escape(tooltip)}'></div>")

    return (
        "<section class='panel'>"
        f"<h2>{escape(title)}</h2>"
        "<div class='hm-wrap'>"
        "<div class='hm-grid'>"
        "<div class='hm-corner'></div>"
        f"{hour_labels}"
        f"{''.join(cells)}"
        "</div>"
        "<div class='hm-legend'>"
        "<span>Less</span>"
        "<span class='hm-sq l0'></span><span class='hm-sq l1'></span><span class='hm-sq l2'></span><span class='hm-sq l3'></span><span class='hm-sq l4'></span>"
        "<span>More</span>"
        "</div>"
        "</div>"
        "<p class='hm-note'><small>Intensity uses avg/day per weekday-hour (prevents longer windows from just looking darker). Hover for totals + averages.</small></p>"
        "</section>"
    )


def _work_rollup_from_heatmap(
    *,
    heatmaps: dict[str, Any],
    series_name: str,
) -> dict[str, Any]:
    series = heatmaps.get("series") if isinstance(heatmaps.get("series"), dict) else {}
    matrix = series.get(series_name) if isinstance(series.get(series_name), list) else _empty_weekday_hour_matrix()
    weekday_names = heatmaps.get("weekday_names") if isinstance(heatmaps.get("weekday_names"), list) else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_day_counts = heatmaps.get("weekday_day_counts") if isinstance(heatmaps.get("weekday_day_counts"), list) else [0 for _ in range(7)]

    total_days = max(1, sum(_safe_int(x) for x in weekday_day_counts[:7]))
    weekday_totals = [sum(_safe_int(v) for v in (matrix[dow] if dow < len(matrix) else [])) for dow in range(7)]
    weekday_avg = [
        (weekday_totals[dow] / float(max(1, _safe_int(weekday_day_counts[dow] if dow < len(weekday_day_counts) else 0))))
        for dow in range(7)
    ]
    hour_totals = [
        sum(_safe_int(matrix[dow][hour]) for dow in range(7) if dow < len(matrix) and hour < len(matrix[dow]))
        for hour in range(24)
    ]
    hour_avg = [hour_totals[hour] / float(total_days) for hour in range(24)]

    overall_avg_per_day = sum(weekday_totals) / float(total_days)
    overall_avg_per_hour = overall_avg_per_day / 24.0 if overall_avg_per_day > 0 else 0.0
    weekday_delta_pct = [
        ((weekday_avg[dow] / overall_avg_per_day) - 1.0) * 100.0 if overall_avg_per_day > 0 else 0.0
        for dow in range(7)
    ]
    hour_delta_pct = [
        ((hour_avg[hour] / overall_avg_per_hour) - 1.0) * 100.0 if overall_avg_per_hour > 0 else 0.0
        for hour in range(24)
    ]

    top_cells: list[dict[str, Any]] = []
    for dow in range(7):
        denom = float(max(1, _safe_int(weekday_day_counts[dow] if dow < len(weekday_day_counts) else 0)))
        for hour in range(24):
            total = _safe_int(matrix[dow][hour])
            avg = total / denom
            top_cells.append(
                {
                    "dow": str(weekday_names[dow] if dow < len(weekday_names) else dow),
                    "hour": hour,
                    "total": total,
                    "avg_per_day": avg,
                    "days": int(denom),
                }
            )
    top_cells.sort(key=lambda item: (-_safe_float(item.get("avg_per_day")), -_safe_int(item.get("total"))))

    return {
        "series": series_name,
        "total_days": total_days,
        "weekday_names": weekday_names[:7],
        "weekday_day_counts": [int(_safe_int(x)) for x in weekday_day_counts[:7]],
        "weekday_totals": weekday_totals,
        "weekday_avg_per_day": weekday_avg,
        "weekday_delta_pct": weekday_delta_pct,
        "hour_totals": hour_totals,
        "hour_avg_per_day": hour_avg,
        "hour_delta_pct": hour_delta_pct,
        "overall_avg_per_day": overall_avg_per_day,
        "overall_avg_per_hour": overall_avg_per_hour,
        "top_cells": top_cells[:12],
    }


def _render_rollup_bar_rows(
    *,
    labels: list[str],
    values: list[float],
    deltas: list[float] | None,
    css_class: str,
    precision: int = 2,
) -> str:
    safe_values = [max(0.0, float(v)) for v in values]
    max_value = max(safe_values) if safe_values else 0.0
    safe_max = max_value if max_value > 0 else 1.0
    out: list[str] = []
    for idx, label in enumerate(labels):
        value = safe_values[idx] if idx < len(safe_values) else 0.0
        width = int((value / safe_max) * 100.0) if value else 0
        delta = 0.0
        if deltas is not None and idx < len(deltas):
            delta = float(deltas[idx])
        delta_text = f"{delta:+.0f}%" if abs(delta) >= 1.0 else ""
        tooltip = f"{label}: {value:.{precision}f} avg/day {delta_text}"
        out.append(
            "<li>"
            f"<code>{escape(label)}</code>"
            f"<div class='bar-wrap' title='{escape(tooltip)}'><div class='bar {escape(css_class)}' style='width:{width}%;'></div></div>"
            f"<span>{value:.{precision}f}{(' ' + escape(delta_text)) if delta_text else ''}</span>"
            "</li>"
        )
    return "\n".join(out)


def _render_signal_heatmap_interactive(
    *,
    heatmaps: dict[str, Any],
    dom_id_prefix: str,
) -> str:
    """
    Interactive (static HTML + tiny JS) weekday x hour heatmap with lane toggles.

    This is intentionally not "Grafana in SB": it renders a deterministic view
    over the baked SB payload, and all drilldown remains via SB daily links.
    """
    heatmaps_json = json.dumps(heatmaps, sort_keys=True).replace("<", "\\u003c")
    data_id = f"{dom_id_prefix}-heatmap-data"
    controls_id = f"{dom_id_prefix}-heatmap-controls"
    grid_id = f"{dom_id_prefix}-heatmap-grid"
    weekday_list_id = f"{dom_id_prefix}-rollup-weekday"
    hour_list_id = f"{dom_id_prefix}-rollup-hour"
    top_table_id = f"{dom_id_prefix}-rollup-top"
    normalize_id = f"{dom_id_prefix}-normalize"
    select_all_id = f"{dom_id_prefix}-select-all"
    select_none_id = f"{dom_id_prefix}-select-none"
    select_intent_id = f"{dom_id_prefix}-select-intent"

    # NOTE: the JS below is plain/portable; keep it small and deterministic.
    return f"""
<section class="panel">
  <h2>When You Work (Weekday x Hour)</h2>
  <p><small>Design cue: GitHub’s contribution calendar. This view answers "when" across the window. Default is a normalized score across selected signals; toggle signals to filter.</small></p>
  <div class="filter-grid">
    <div class="filter-block">
      <div><b>Signals</b></div>
      <div class="filter-options" id="{escape(controls_id)}"></div>
      <div class="wf-controls" style="margin-top:0.45rem;">
        <label><input type="checkbox" id="{escape(normalize_id)}" checked> Normalize (score)</label>
        <button type="button" id="{escape(select_all_id)}">All</button>
        <button type="button" id="{escape(select_none_id)}">None</button>
        <button type="button" id="{escape(select_intent_id)}">Intent set</button>
      </div>
    </div>
  </div>
  <div class="hm-wrap">
    <div class="hm-grid" id="{escape(grid_id)}"></div>
    <div class="hm-legend">
      <span>Less</span>
      <span class="hm-sq l0"></span><span class="hm-sq l1"></span><span class="hm-sq l2"></span><span class="hm-sq l3"></span><span class="hm-sq l4"></span>
      <span>More</span>
    </div>
  </div>
  <p class="hm-note"><small>Hover cells for per-signal breakdown. Intensity is normalized per lane when "Normalize" is on, so input volume doesn't swamp other signals.</small></p>
</section>

<section class="panel">
  <h2>Above / Below (Rollups)</h2>
  <p><small>Which days/hours are above baseline, using the selected signals.</small></p>
  <div class="rollup-grid">
    <div class="metric rollup">
      <div><b>By weekday (avg/day)</b></div>
      <ul id="{escape(weekday_list_id)}"></ul>
    </div>
    <div class="metric rollup">
      <div><b>By hour (avg/day)</b></div>
      <ul id="{escape(hour_list_id)}"></ul>
    </div>
    <div class="metric rollup">
      <div><b>Top weekday-hours</b></div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Rank</th><th>When</th><th>Value</th><th>Notes</th></tr></thead>
          <tbody id="{escape(top_table_id)}"></tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<script id="{escape(data_id)}" type="application/json">{heatmaps_json}</script>
<script>
(() => {{
  const dataEl = document.getElementById({json.dumps(data_id)});
  if (!dataEl) return;
  const data = JSON.parse(dataEl.textContent || "{{}}");
  const lanes = Array.isArray(data.lanes) ? data.lanes.slice() : [];
  const laneLabels = (data.lane_labels && typeof data.lane_labels === "object") ? data.lane_labels : {{}};
  const laneTotals = (data.lane_totals && typeof data.lane_totals === "object") ? data.lane_totals : {{}};
  const series = (data.series && typeof data.series === "object") ? data.series : {{}};
  const weekdayNames = Array.isArray(data.weekday_names) ? data.weekday_names : ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  const weekdayDayCounts = Array.isArray(data.weekday_day_counts) ? data.weekday_day_counts.map(x => Math.max(0, Number(x)||0)) : [0,0,0,0,0,0,0];
  const totalDays = Math.max(1, weekdayDayCounts.reduce((a,b) => a + b, 0));
  const defaultSelected = Array.isArray(data.default_selected) ? data.default_selected : [];

  const controls = document.getElementById({json.dumps(controls_id)});
  const grid = document.getElementById({json.dumps(grid_id)});
  const weekdayList = document.getElementById({json.dumps(weekday_list_id)});
  const hourList = document.getElementById({json.dumps(hour_list_id)});
  const topBody = document.getElementById({json.dumps(top_table_id)});
  const normalizeToggle = document.getElementById({json.dumps(normalize_id)});
  const btnAll = document.getElementById({json.dumps(select_all_id)});
  const btnNone = document.getElementById({json.dumps(select_none_id)});
  const btnIntent = document.getElementById({json.dumps(select_intent_id)});
  if (!controls || !grid || !weekdayList || !hourList || !topBody || !normalizeToggle) return;

  const INTENT_SET = ["git","shell","chat","pr","git_branch","input","calendar","activity"];

  function laneAvailable(lane) {{
    return (Number(laneTotals[lane]) || 0) > 0;
  }}

  function buildControls() {{
    const items = [];
    for (const lane of lanes) {{
      const label = laneLabels[lane] || lane;
      const available = laneAvailable(lane);
      const checked = defaultSelected.includes(lane) && available;
      items.push(
        `<label title="${{available ? "" : "no data in this window"}}">` +
          `<input type="checkbox" data-lane="${{lane}}" ${{checked ? "checked" : ""}} ${{available ? "" : "disabled"}}>` +
          `${{label}}` +
        `</label>`
      );
    }}
    controls.innerHTML = items.join("");
  }}

  function selectedLanes() {{
    const out = [];
    for (const box of controls.querySelectorAll("input[type=checkbox][data-lane]")) {{
      if (box.checked && !box.disabled) out.push(box.getAttribute("data-lane"));
    }}
    return out;
  }}

  function cellAvg(lane, dow, hour) {{
    const denom = Math.max(1, Number(weekdayDayCounts[dow]) || 0);
    const m = series[lane];
    if (!Array.isArray(m) || !Array.isArray(m[dow])) return 0;
    return (Number(m[dow][hour]) || 0) / denom;
  }}

  function computeLaneMaxAvg(lane) {{
    let max = 0;
    for (let dow = 0; dow < 7; dow++) {{
      for (let hour = 0; hour < 24; hour++) {{
        max = Math.max(max, cellAvg(lane, dow, hour));
      }}
    }}
    return max;
  }}

  function heatLevel(value, maxValue) {{
    if (!(value > 0) || !(maxValue > 0)) return 0;
    const ratio = Math.max(0, Math.min(1, value / maxValue));
    if (ratio <= 0.20) return 1;
    if (ratio <= 0.40) return 2;
    if (ratio <= 0.65) return 3;
    return 4;
  }}

  function formatDeltaPct(delta) {{
    if (!isFinite(delta) || Math.abs(delta) < 1) return "";
    const sign = delta >= 0 ? "+" : "";
    return `${{sign}}${{delta.toFixed(0)}}%`;
  }}

  function render() {{
    const selected = selectedLanes();
    const normalize = !!normalizeToggle.checked;
    const laneMax = {{}};
    if (normalize) {{
      for (const lane of selected) laneMax[lane] = computeLaneMaxAvg(lane);
    }}

    const values = Array.from({{length: 7}}, () => Array.from({{length: 24}}, () => 0));
    let maxVal = 0;
    for (let dow = 0; dow < 7; dow++) {{
      for (let hour = 0; hour < 24; hour++) {{
        if (!selected.length) {{
          values[dow][hour] = 0;
          continue;
        }}
        if (normalize) {{
          let sum = 0;
          let n = 0;
          for (const lane of selected) {{
            const m = laneMax[lane] || 0;
            if (!(m > 0)) continue;
            sum += (cellAvg(lane, dow, hour) / m);
            n += 1;
          }}
          values[dow][hour] = n ? (sum / n) : 0;
        }} else {{
          let sum = 0;
          for (const lane of selected) sum += cellAvg(lane, dow, hour);
          values[dow][hour] = sum;
        }}
        maxVal = Math.max(maxVal, values[dow][hour]);
      }}
    }}

    // Build heatmap grid.
    const hourLabels = [];
    for (let hour = 0; hour < 24; hour++) {{
      if (hour % 3 === 0) hourLabels.push(`<div class="hm-hour">${{String(hour).padStart(2,"0")}}</div>`);
      else hourLabels.push(`<div class="hm-hour hm-hour-muted"></div>`);
    }}
    const cells = [];
    for (let dow = 0; dow < 7; dow++) {{
      const dowName = String(weekdayNames[dow] || dow);
      const days = Number(weekdayDayCounts[dow]) || 0;
      cells.push(`<div class="hm-dow">${{dowName}}</div>`);
      for (let hour = 0; hour < 24; hour++) {{
        const val = values[dow][hour];
        const level = heatLevel(val, maxVal);
        const laneLines = selected.slice(0, 8).map(l => {{
          const avg = cellAvg(l, dow, hour);
          return `${{laneLabels[l] || l}}: ${{avg.toFixed(2)}} avg/day`;
        }});
        const mode = normalize ? "score" : "avg/day";
        const header = `${{dowName}} ${{String(hour).padStart(2,"0")}}:00 | ${{mode}}=${{val.toFixed(2)}} | days=${{days}}`;
        const more = selected.length > 8 ? ` (+${{selected.length - 8}} more)` : "";
        const tooltip = [header].concat(laneLines).concat([more]).filter(Boolean).join("\\n");
        cells.push(`<div class="hm-cell l${{level}}" title="${{tooltip.replace(/\"/g, "&quot;")}}"></div>`);
      }}
    }}
    grid.innerHTML = `<div class="hm-corner"></div>${{hourLabels.join("")}}${{cells.join("")}}`;

    // Rollups.
    const weekdayScore = Array.from({{length: 7}}, () => 0);
    for (let dow = 0; dow < 7; dow++) {{
      let sum = 0;
      for (let hour = 0; hour < 24; hour++) sum += values[dow][hour];
      weekdayScore[dow] = sum;
    }}
    const baselinePerDay = weekdayScore.reduce((acc, v, i) => acc + (v * (Number(weekdayDayCounts[i]) || 0)), 0) / totalDays;
    const weekdayDelta = weekdayScore.map((v, i) => (baselinePerDay > 0 ? ((v / baselinePerDay) - 1) * 100 : 0));

    const hourScore = Array.from({{length: 24}}, () => 0);
    for (let hour = 0; hour < 24; hour++) {{
      let sum = 0;
      for (let dow = 0; dow < 7; dow++) sum += values[dow][hour] * (Number(weekdayDayCounts[dow]) || 0);
      hourScore[hour] = sum / totalDays;
    }}
    const baselinePerHour = (baselinePerDay > 0) ? (baselinePerDay / 24.0) : 0;
    const hourDelta = hourScore.map(v => (baselinePerHour > 0 ? ((v / baselinePerHour) - 1) * 100 : 0));

    function renderBars(labels, vals, deltas, cssClass, precision) {{
      const max = Math.max(0.000001, ...vals);
      return labels.map((label, idx) => {{
        const v = vals[idx] || 0;
        const w = v ? Math.round((v / max) * 100) : 0;
        const d = deltas[idx] || 0;
        const dText = formatDeltaPct(d);
        const tip = `${{label}}: ${{v.toFixed(precision)}} avg/day ${{dText}}`;
        return (
          `<li>` +
            `<code>${{label}}</code>` +
            `<div class="bar-wrap" title="${{tip.replace(/\"/g, "&quot;")}}"><div class="bar ${{cssClass}}" style="width:${{w}}%;"></div></div>` +
            `<span>${{v.toFixed(precision)}}${{dText ? " " + dText : ""}}</span>` +
          `</li>`
        );
      }}).join("");
    }}

    weekdayList.innerHTML = renderBars(weekdayNames.slice(0,7), weekdayScore, weekdayDelta, "work", 2);
    hourList.innerHTML = renderBars(Array.from({{length:24}}, (_,h) => String(h).padStart(2,"0")), hourScore, hourDelta, "work", 2);

    // Top weekday-hours.
    const flat = [];
    for (let dow = 0; dow < 7; dow++) {{
      for (let hour = 0; hour < 24; hour++) {{
        flat.push({{
          dow: String(weekdayNames[dow] || dow),
          hour,
          value: values[dow][hour],
          days: Number(weekdayDayCounts[dow]) || 0
        }});
      }}
    }}
    flat.sort((a,b) => (b.value - a.value));
    const top = flat.slice(0, 12);
    topBody.innerHTML = top.map((row, idx) => {{
      const when = `${{row.dow}} ${{String(row.hour).padStart(2,"0")}}:00`;
      const note = normalize ? "score (normalized)" : "avg/day (raw)";
      return (
        `<tr>` +
          `<td>${{idx+1}}</td>` +
          `<td><code>${{when}}</code></td>` +
          `<td>${{row.value.toFixed(2)}}</td>` +
          `<td>${{note}}</td>` +
        `</tr>`
      );
    }}).join("") || `<tr><td colspan="4">No data.</td></tr>`;
  }}

  buildControls();
  controls.addEventListener("change", render);
  normalizeToggle.addEventListener("change", render);
  if (btnAll) btnAll.addEventListener("click", () => {{
    for (const box of controls.querySelectorAll("input[type=checkbox][data-lane]")) {{
      if (!box.disabled) box.checked = true;
    }}
    render();
  }});
  if (btnNone) btnNone.addEventListener("click", () => {{
    for (const box of controls.querySelectorAll("input[type=checkbox][data-lane]")) {{
      box.checked = false;
    }}
    render();
  }});
  if (btnIntent) btnIntent.addEventListener("click", () => {{
    for (const box of controls.querySelectorAll("input[type=checkbox][data-lane]")) {{
      const lane = box.getAttribute("data-lane");
      box.checked = !box.disabled && INTENT_SET.includes(lane);
    }}
    render();
  }});
  render();
}})();
</script>
"""


def render_dashboard_html(payload: dict[str, Any], html_path: Path) -> str:
    summary = payload.get("summary", {})
    freq = payload.get("frequency_by_hour", {})
    artifacts = payload.get("artifact_links", [])
    timeline = payload.get("timeline", [])
    threads = payload.get("chat_threads", [])
    tool_use_summary = payload.get("tool_use_summary") or {}
    itir_overlay_records = payload.get("itir_overlay_records") or []
    itir_overlay_joins = payload.get("itir_overlay_joins") or []
    warnings = payload.get("warnings", [])
    chat_flow = payload.get("chat_flow") or {}
    trailing = payload.get("chat_context_trailing") or {}
    notes_meta_summary = payload.get("notes_meta_summary")
    if not isinstance(notes_meta_summary, dict):
        notes_meta_summary = _empty_notes_meta_summary()
    notes_focus = _notebooklm_lifecycle_focus(notes_meta_summary)
    notebook_lifecycle = notes_focus.get("notebook") or {}
    file_lifecycle = notes_focus.get("file") or {}
    notes_total_events = _safe_int(notes_meta_summary.get("total_events"))
    notebooklm_events = _safe_int(notes_meta_summary.get("notebooklm_events"))
    notes_app_counts = notes_meta_summary.get("app_counts") if isinstance(notes_meta_summary.get("app_counts"), dict) else {}
    notes_app_counts_text = ", ".join(
        f"{app}:{_safe_int(count)}"
        for app, count in sorted(notes_app_counts.items(), key=lambda item: (-_safe_int(item[1]), item[0]))
    ) or "none"
    media_summary = payload.get("media_summary")
    if not isinstance(media_summary, dict):
        media_summary = {}
    inat_trend = payload.get("inaturalist_trend") if isinstance(payload.get("inaturalist_trend"), dict) else {}
    inat_phase = str(inat_trend.get("phase_code") or "insufficient_data")
    inat_expectation = str(inat_trend.get("expectation_code") or "insufficient_data")
    inat_available_days = _safe_int(inat_trend.get("available_days"))
    inat_window_days = _safe_int(inat_trend.get("window_days"))
    mood_latest = payload.get("mood_latest") if isinstance(payload.get("mood_latest"), dict) else {}
    mood_latest_code = str(mood_latest.get("mood_code") or "unknown")
    mood_latest_ts = str(mood_latest.get("ts") or "")
    media_events_total = _safe_int(summary.get("media_events", media_summary.get("events")))
    media_items_total = _safe_int(summary.get("media_items_observed", media_summary.get("items_observed")))
    media_consumed_seconds = _safe_int(summary.get("media_consumed_seconds", media_summary.get("consumed_seconds")))
    media_content_seconds = _safe_int(
        summary.get("media_content_seconds", media_summary.get("content_duration_seconds"))
    )
    media_completion_ratio = _safe_float(summary.get("media_completion_ratio", media_summary.get("completion_ratio")))
    media_churn_events = _safe_int(summary.get("media_churn_events", media_summary.get("churn_events")))
    media_churn_rate = _safe_float(summary.get("media_churn_rate", media_summary.get("churn_rate")))
    chat_tokens_est = _safe_int(summary.get("chat_tokens_est"))
    chat_input_tokens_est = _safe_int(summary.get("chat_input_tokens_est"))
    chat_output_tokens_est = _safe_int(summary.get("chat_output_tokens_est"))
    chat_context_default_window_tokens = _safe_int(
        summary.get("chat_context_default_window_tokens"),
        fallback=DEFAULT_CONTEXT_WINDOW_TOKENS,
    )
    chat_context_overflow_threads = _safe_int(summary.get("chat_context_overflow_threads"))
    chat_context_overflow_tokens = _safe_int(summary.get("chat_context_overflow_tokens"))
    chat_context_max_thread_usage_pct = _safe_float(summary.get("chat_context_max_thread_usage_pct")) * 100.0
    concurrency_window_seconds = _safe_int(summary.get("concurrency_window_seconds"), fallback=300)
    concurrency_window_minutes = max(1, concurrency_window_seconds // 60)
    chat_media_overlap_hours = _safe_int(summary.get("chat_media_overlap_hours"))
    chat_media_overlap_rate_pct = _safe_float(summary.get("chat_media_overlap_rate")) * 100.0
    chat_input_overlap_hours = _safe_int(summary.get("chat_input_overlap_hours"))
    chat_input_overlap_rate_pct = _safe_float(summary.get("chat_input_overlap_rate")) * 100.0
    chat_activity_overlap_hours = _safe_int(summary.get("chat_activity_overlap_hours"))
    chat_activity_overlap_rate_pct = _safe_float(summary.get("chat_activity_overlap_rate")) * 100.0
    chat_messages_with_media_nearby = _safe_int(summary.get("chat_messages_with_media_nearby"))
    chat_messages_with_media_nearby_rate_pct = _safe_float(summary.get("chat_messages_with_media_nearby_rate")) * 100.0
    chat_messages_with_input_nearby = _safe_int(summary.get("chat_messages_with_input_nearby"))
    chat_messages_with_input_nearby_rate_pct = _safe_float(
        summary.get("chat_messages_with_input_nearby_rate")
    ) * 100.0
    voice_activity_events = _safe_int(summary.get("voice_activity_events"))
    chat_messages_with_voice_activity_nearby = _safe_int(summary.get("chat_messages_with_voice_activity_nearby"))
    chat_messages_with_voice_activity_nearby_rate_pct = _safe_float(
        summary.get("chat_messages_with_voice_activity_nearby_rate")
    ) * 100.0
    agent_edit_summary = payload.get("agent_edit_summary")
    if not isinstance(agent_edit_summary, dict):
        agent_edit_summary = _empty_agent_edit_summary()
    agent_edit_blocks = _safe_int(summary.get("agent_edit_blocks", agent_edit_summary.get("edit_blocks")))
    agent_edit_files = _safe_int(summary.get("agent_edit_files", agent_edit_summary.get("files_touched")))
    agent_edit_lines_added = _safe_int(summary.get("agent_edit_lines_added", agent_edit_summary.get("lines_added")))
    agent_edit_lines_removed = _safe_int(summary.get("agent_edit_lines_removed", agent_edit_summary.get("lines_removed")))
    agent_edit_top_file_share = _safe_float(
        summary.get("agent_edit_top_file_share", agent_edit_summary.get("top_file_share"))
    )
    agent_edit_focus_mode = str(agent_edit_summary.get("focus_mode") or "none")
    inat_insects_today = _safe_int(summary.get("inaturalist_insect_observations"))
    mood_reports_today = _safe_int(summary.get("mood_reports"))
    chat_context_usage = payload.get("chat_context_usage")
    if not isinstance(chat_context_usage, dict):
        chat_context_usage = _build_chat_context_usage([])
    context_threads_usage = chat_context_usage.get("threads_usage") if isinstance(chat_context_usage.get("threads_usage"), list) else []
    context_windows = chat_context_usage.get("window_summary") if isinstance(chat_context_usage.get("window_summary"), list) else []

    media_platform_rows: list[str] = []
    media_by_platform = media_summary.get("by_platform") if isinstance(media_summary.get("by_platform"), dict) else {}
    for platform, counters in sorted(
        media_by_platform.items(),
        key=lambda item: (
            -_safe_int(item[1].get("events") if isinstance(item[1], dict) else 0),
            str(item[0]),
        ),
    ):
        if not isinstance(counters, dict):
            continue
        consumed = _safe_int(counters.get("consumed_seconds"))
        content = _safe_int(counters.get("content_duration_seconds"))
        media_platform_rows.append(
            "<tr>"
            f"<td><code>{escape(str(platform))}</code></td>"
            f"<td>{_safe_int(counters.get('events'))}</td>"
            f"<td>{_safe_int(counters.get('items_observed'))}</td>"
            f"<td>{_format_seconds_compact(consumed)}</td>"
            f"<td>{_format_seconds_compact(content)}</td>"
            f"<td>{(_ratio(consumed, content, digits=3) * 100.0):.1f}%</td>"
            "</tr>"
        )

    agent_edit_rows: list[str] = []
    for row in agent_edit_summary.get("files") or []:
        if not isinstance(row, dict):
            continue
        line_numbers = [str(_safe_int(v)) for v in (row.get("line_numbers") or []) if _safe_int(v) > 0]
        line_ref_text = ", ".join(line_numbers[:10]) if line_numbers else "-"
        if len(line_numbers) > 10:
            line_ref_text += " ..."
        agent_edit_rows.append(
            "<tr>"
            f"<td><code>{escape(str(row.get('path') or ''))}</code></td>"
            f"<td>{_safe_int(row.get('blocks'))}</td>"
            f"<td>+{_safe_int(row.get('lines_added'))} / -{_safe_int(row.get('lines_removed'))}</td>"
            f"<td>{_safe_int(row.get('total_edits'))}</td>"
            f"<td>{(_safe_float(row.get('share')) * 100.0):.1f}%</td>"
            f"<td>{escape(line_ref_text)}</td>"
            "</tr>"
        )

    artifact_rows = []
    for item in artifacts:
        target = str(item.get("path", ""))
        label = escape(str(item.get("label", target)))
        href = escape(_rel_href(target, html_path))
        artifact_rows.append(f"<li><a href='{href}'>{label}</a><code>{escape(target)}</code></li>")

    overlay_join_by_annotation: dict[str, dict[str, Any]] = {}
    if isinstance(itir_overlay_joins, list):
        for item in itir_overlay_joins:
            if not isinstance(item, dict):
                continue
            ann = str(item.get("annotation_id") or "").strip()
            if ann:
                overlay_join_by_annotation[ann] = item

    observer_overlay_rows = ""
    if isinstance(itir_overlay_records, list):
        overlay_rows: list[str] = []
        for rec in itir_overlay_records:
            if not isinstance(rec, dict):
                continue
            ann = str(rec.get("annotation_id") or "").strip()
            kind = str(rec.get("observer_kind") or "").strip()
            evt = str(rec.get("activity_event_id") or "").strip()
            sdate = str(rec.get("state_date") or "").strip()
            status = str(rec.get("status") or "").strip()
            conf = str(rec.get("confidence") or "").strip()

            join = overlay_join_by_annotation.get(ann, {})
            join_bits: list[str] = []
            fuzz = join.get("fuzzymodo_decision") if isinstance(join.get("fuzzymodo_decision"), dict) else None
            if isinstance(fuzz, dict):
                decision_id = str(fuzz.get("decision_id") or "").strip()
                matched = fuzz.get("matched")
                state = str(fuzz.get("decision_state") or "").strip()
                if decision_id:
                    join_bits.append(f"fuzz: <code>{escape(decision_id)}</code>")
                if matched in (0, 1):
                    join_bits.append(f"matched=<code>{matched}</code>")
                if state:
                    join_bits.append(f"state=<code>{escape(state)}</code>")
            casey_op = join.get("casey_operation") if isinstance(join.get("casey_operation"), dict) else None
            if isinstance(casey_op, dict):
                op_id = str(casey_op.get("operation_id") or "").strip()
                op_kind = str(casey_op.get("operation_kind") or "").strip()
                if op_id:
                    join_bits.append(f"casey op: <code>{escape(op_id)}</code>")
                if op_kind:
                    join_bits.append(f"kind=<code>{escape(op_kind)}</code>")
            casey_build = join.get("casey_build") if isinstance(join.get("casey_build"), dict) else None
            if isinstance(casey_build, dict):
                build_id = str(casey_build.get("build_id") or "").strip()
                if build_id:
                    join_bits.append(f"casey build: <code>{escape(build_id)}</code>")

            join_text = " · ".join(join_bits) if join_bits else ""
            overlay_rows.append(
                "<tr>"
                + f"<td><code title='{escape(ann)}'>{escape(_short_id(ann, 12))}</code></td>"
                + f"<td><code>{escape(kind)}</code></td>"
                + f"<td><code title='{escape(evt)}'>{escape(_short_id(evt, 12))}</code></td>"
                + f"<td><code>{escape(sdate)}</code></td>"
                + f"<td>{escape(status)}</td>"
                + f"<td>{escape(conf)}</td>"
                + f"<td>{join_text}</td>"
                + "</tr>"
            )
        observer_overlay_rows = "".join(overlay_rows)

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
        if isinstance(variant_groups, list) and variant_groups:
            grouped_lines: list[str] = []
            for group in variant_groups:
                if not isinstance(group, dict):
                    continue
                group_name = str(group.get("group") or "other")
                group_count = _safe_int(group.get("count"))
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
                group_label = f"rg {group_name}" if family.get("family") == "rg" else group_name
                grouped_lines.append(
                    f"<li><code>{escape(group_label)}</code> <code>{group_count}</code>{mode_html}</li>"
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
            f"<span class='wf-swatch wf-colorable' data-thread-index='{_safe_int(thread.get('color_index'))}' data-thread-start-hour='{_safe_int(thread.get('thread_start_hour'))}' data-role='thread' data-switch='stay' data-default-color='{escape(color_hex)}' style='background:{escape(color_hex)};'></span>"
            f"<code>{message_count}</code> {escape(thread_label)} <code>{share_pct:.1f}% of chat messages</code>"
            "</li>"
        )

    flow_item_dicts = [item for item in (chat_flow.get("waterfall") or []) if isinstance(item, dict)]
    segment_widths, segment_layout = _waterfall_segment_widths(flow_item_dicts)
    flow_segments: list[str] = []
    for segment, width_rem in zip(flow_item_dicts, segment_widths):
        color_hex = str(segment.get("color_hex") or "#6b7280")
        thread_title = str(segment.get("thread_title") or "(no title)")
        thread_id = str(segment.get("thread_id") or "")
        role_text = str(segment.get("role") or "unknown")
        ts_text = str(segment.get("ts") or "")
        hour_value = _safe_int(segment.get("hour"))
        thread_start_hour = _safe_int(segment.get("thread_start_hour"))
        gap_to_next = _safe_int(segment.get("gap_to_next_seconds"), fallback=60)
        thread_index = _safe_int(segment.get("color_index"))
        switch_text = "switch" if bool(segment.get("switch")) else "stay"
        title_parts = [ts_text, role_text, thread_title, switch_text]
        if thread_id:
            title_parts.append(_short_id(thread_id, width=12))
        title_text = " | ".join(item for item in title_parts if item)
        class_text = "wf-seg switch" if bool(segment.get("switch")) else "wf-seg"
        flow_segments.append(
            f"<span class='{class_text} wf-seg-colorable' data-thread-index='{thread_index}' data-hour='{hour_value}' data-thread-start-hour='{thread_start_hour}' data-gap-sec='{gap_to_next}' data-role='{escape(role_text)}' data-switch='{escape(switch_text)}' data-default-color='{escape(color_hex)}' style='background:{escape(color_hex)}; width:{width_rem:.4f}rem;' title='{escape(title_text)}' aria-label='{escape(title_text)}'></span>"
        )
    wf_seg_h = _safe_float(segment_layout.get("seg_height_rem")) or 0.95
    wf_strip_gap = _safe_float(segment_layout.get("strip_gap_rem")) or 0.10
    lane_message_limit = 600
    lane_thread_limit = 40
    lane_blockers: list[str] = []
    if _safe_int(chat_flow.get("message_count")) > lane_message_limit:
        lane_blockers.append(
            f"message_count={_safe_int(chat_flow.get('message_count'))} exceeds {lane_message_limit}"
        )
    if _safe_int(chat_flow.get("thread_count")) > lane_thread_limit:
        lane_blockers.append(
            f"thread_count={_safe_int(chat_flow.get('thread_count'))} exceeds {lane_thread_limit}"
        )
    if not flow_item_dicts:
        lane_blockers.append("no chat messages for this date")
    lane_available = not lane_blockers
    lane_svg_markup = ""
    if lane_available:
        lane_rows = [row for row in (chat_flow.get("threads") or []) if isinstance(row, dict)]
        lane_index_by_key = {
            str(row.get("thread_key") or ""): idx
            for idx, row in enumerate(lane_rows)
            if str(row.get("thread_key") or "")
        }
        lane_points: list[dict[str, Any]] = []
        for item in flow_item_dicts:
            thread_key = str(item.get("thread_key") or "")
            lane_index = lane_index_by_key.get(thread_key, -1)
            if lane_index < 0:
                continue
            dt = _parse_ts(item.get("ts"))
            ts_epoch = int(dt.timestamp()) if dt else 0
            lane_points.append(
                {
                    "thread_key": thread_key,
                    "thread_title": str(item.get("thread_title") or "(no title)"),
                    "thread_id": str(item.get("thread_id") or ""),
                    "lane_index": lane_index,
                    "ts": str(item.get("ts") or ""),
                    "ts_epoch": ts_epoch,
                    "hour": _safe_int(item.get("hour")),
                    "thread_start_hour": _safe_int(item.get("thread_start_hour")),
                    "role": str(item.get("role") or "unknown"),
                    "switch": bool(item.get("switch")),
                    "color_index": _safe_int(item.get("color_index")),
                    "color_hex": str(item.get("color_hex") or "#6b7280"),
                }
            )
        if lane_points and lane_rows:
            min_epoch = min(point["ts_epoch"] for point in lane_points)
            max_epoch = max(point["ts_epoch"] for point in lane_points)
            span = max(1, max_epoch - min_epoch)
            left_pad = 190.0
            right_pad = 26.0
            top_pad = 26.0
            bottom_pad = 32.0
            row_h = 26.0
            plot_width = float(max(880, min(3800, 16 * len(lane_points))))
            svg_width = left_pad + plot_width + right_pad
            svg_height = top_pad + (row_h * len(lane_rows)) + bottom_pad

            def _x_for_epoch(ts_epoch: int) -> float:
                return left_pad + ((float(ts_epoch - min_epoch) / float(span)) * plot_width)

            lane_bg_parts: list[str] = []
            lane_label_parts: list[str] = []
            for idx, row in enumerate(lane_rows):
                y_center = top_pad + (idx * row_h) + (row_h / 2.0)
                y_line = y_center
                lane_bg_parts.append(
                    f"<line x1='{left_pad:.2f}' y1='{y_line:.2f}' x2='{(left_pad + plot_width):.2f}' y2='{y_line:.2f}' class='wf-lane-line' />"
                )
                lane_label = str(row.get("thread_title") or "(no title)")
                lane_msg_count = _safe_int(row.get("message_count"))
                lane_label_parts.append(
                    (
                        f"<text x='{(left_pad - 8.0):.2f}' y='{(y_center + 4.0):.2f}' class='wf-lane-label' "
                        f"text-anchor='end'>{escape(lane_label)} [{lane_msg_count}]</text>"
                    )
                )

            edge_parts: list[str] = []
            point_parts: list[str] = []
            for idx, point in enumerate(lane_points):
                x = _x_for_epoch(point["ts_epoch"])
                y = top_pad + (point["lane_index"] * row_h) + (row_h / 2.0)
                point["x"] = x
                point["y"] = y
                if idx > 0:
                    prev = lane_points[idx - 1]
                    edge_class = "wf-edge switch" if bool(point.get("switch")) else "wf-edge stay"
                    edge_parts.append(
                        f"<line x1='{prev['x']:.2f}' y1='{prev['y']:.2f}' x2='{x:.2f}' y2='{y:.2f}' class='{edge_class}' />"
                    )
                point_title = " | ".join(
                    part
                    for part in [
                        str(point.get("ts") or ""),
                        str(point.get("role") or "unknown"),
                        str(point.get("thread_title") or "(no title)"),
                        "switch" if bool(point.get("switch")) else "stay",
                    ]
                    if part
                )
                point_parts.append(
                    (
                        f"<circle cx='{x:.2f}' cy='{y:.2f}' r='4.0' class='wf-node wf-lane-colorable' "
                        f"data-thread-index='{_safe_int(point.get('color_index'))}' "
                        f"data-hour='{_safe_int(point.get('hour'))}' "
                        f"data-thread-start-hour='{_safe_int(point.get('thread_start_hour'))}' "
                        f"data-role='{escape(str(point.get('role') or 'unknown'))}' "
                        f"data-switch='{'switch' if bool(point.get('switch')) else 'stay'}' "
                        f"data-default-color='{escape(str(point.get('color_hex') or '#6b7280'))}' "
                        f"style='fill:{escape(str(point.get('color_hex') or '#6b7280'))};'>"
                        f"<title>{escape(point_title)}</title></circle>"
                    )
                )

            axis_text = (
                f"<text x='{left_pad:.2f}' y='{(top_pad - 8.0):.2f}' class='wf-axis'>{escape(str(chat_flow.get('first_ts') or ''))}</text>"
                f"<text x='{(left_pad + plot_width):.2f}' y='{(top_pad - 8.0):.2f}' class='wf-axis' text-anchor='end'>{escape(str(chat_flow.get('last_ts') or ''))}</text>"
            )
            lane_svg_markup = (
                f"<svg class='wf-lane-svg' viewBox='0 0 {svg_width:.2f} {svg_height:.2f}' preserveAspectRatio='xMinYMin meet'>"
                f"<rect x='0' y='0' width='{svg_width:.2f}' height='{svg_height:.2f}' class='wf-lane-bg' />"
                f"{''.join(lane_bg_parts)}"
                f"{''.join(edge_parts)}"
                f"{''.join(point_parts)}"
                f"{''.join(lane_label_parts)}"
                f"{axis_text}"
                "</svg>"
            )
        else:
            lane_available = False
            lane_blockers.append("insufficient lane data")
    lane_blocker_rows = "".join(f"<li><code>{escape(item)}</code></li>" for item in lane_blockers)
    lane_available_json = json.dumps(lane_available)

    context_thread_rows: list[str] = []
    for thread in context_threads_usage:
        if not isinstance(thread, dict):
            continue
        thread_id = str(thread.get("thread_id") or "").strip()
        thread_title = str(thread.get("thread_title") or "(no title)")
        thread_label = thread_title
        if thread_id:
            thread_label = f"{thread_label} [{_short_id(thread_id, width=12)}]"
        context_thread_rows.append(
            "<tr>"
            f"<td>{escape(thread_label)}</td>"
            f"<td>{_safe_int(thread.get('message_count'))}</td>"
            f"<td>{_safe_int(thread.get('chars_est'))}</td>"
            f"<td>{_safe_int(thread.get('tokens_est'))}</td>"
            f"<td>{(_safe_float(thread.get('window_usage_pct')) * 100.0):.1f}%</td>"
            f"<td>{_safe_int(thread.get('overflow_tokens'))}</td>"
            f"<td>{(_safe_float(thread.get('share_tokens_pct')) * 100.0):.1f}%</td>"
            "</tr>"
        )
    context_window_rows = "".join(
        (
            f"<li><code>{_safe_int(item.get('context_window_tokens'))}</code>: "
            f"overflow_threads=<code>{_safe_int(item.get('overflow_threads'))}</code>, "
            f"overflow_tokens=<code>{_safe_int(item.get('overflow_tokens'))}</code>, "
            f"max_thread_usage=<code>{(_safe_float(item.get('max_thread_usage_pct')) * 100.0):.1f}%</code></li>"
        )
        for item in context_windows
        if isinstance(item, dict)
    )

    messages_per_hour_active = _safe_float(summary.get("messages_per_hour_active"))
    messages_per_chat = _safe_float(summary.get("messages_per_chat"))
    switches_per_active_hour = _safe_float(summary.get("switches_per_active_hour"))
    chat_switch_rate_pct = _safe_float(summary.get("chat_switch_rate")) * 100.0
    top_thread_share_pct = _safe_float(summary.get("top_thread_share")) * 100.0
    context_switch_rate_pct = _safe_float(summary.get("context_switch_rate")) * 100.0

    trailing_available_days = _safe_int(trailing.get("available_days"))
    trailing_has_baseline = bool(trailing.get("has_baseline")) and trailing_available_days > 0
    trailing_window_days = _safe_int(trailing.get("window_days"))
    trailing_current = trailing.get("current") if isinstance(trailing.get("current"), dict) else {}
    trailing_baseline = trailing.get("baseline_avg") if isinstance(trailing.get("baseline_avg"), dict) else {}
    trailing_delta = trailing.get("delta") if isinstance(trailing.get("delta"), dict) else {}
    trailing_sign = "+" if _safe_float(trailing_delta.get("context_switch_rate")) > 0 else ""
    trailing_text = (
        (
            f"7-day trailing avg ({trailing_available_days}/{trailing_window_days} available): "
            f"switch rate {(_safe_float(trailing_current.get('context_switch_rate')) * 100.0):.1f}% vs "
            f"{(_safe_float(trailing_baseline.get('context_switch_rate')) * 100.0):.1f}% "
            f"({trailing_sign}{(_safe_float(trailing_delta.get('context_switch_rate')) * 100.0):.1f} pts), "
            f"switches/hour {(_safe_float(trailing_current.get('switches_per_active_hour'))):.2f} vs "
            f"{(_safe_float(trailing_baseline.get('switches_per_active_hour'))):.2f}, "
            f"messages/chat {(_safe_float(trailing_current.get('messages_per_chat'))):.2f} vs "
            f"{(_safe_float(trailing_baseline.get('messages_per_chat'))):.2f}, "
            f"top-thread share {(_safe_float(trailing_current.get('top_thread_share')) * 100.0):.1f}% vs "
            f"{(_safe_float(trailing_baseline.get('top_thread_share')) * 100.0):.1f}%."
        )
        if trailing_has_baseline
        else "7-day trailing avg: insufficient prior daily dashboards."
    )
    waterfall_palette_names = ("viridis", "turbo", "plasma", "rdylgn")
    waterfall_palette_labels = {
        "viridis": "Viridis",
        "turbo": "Turbo (Rainbow)",
        "plasma": "Plasma (Blue-Pink-Yellow)",
        "rdylgn": "RdYlGn (Red-Yellow-Green)",
    }
    palette_options_html = "".join(
        f"<option value='{escape(name)}'>{escape(waterfall_palette_labels.get(name, name))}</option>"
        for name in waterfall_palette_names
    ) + "<option value='custom'>Custom</option>"
    algo_options_html = (
        "<option value='thread'>Thread</option>"
        "<option value='hour'>Time of Day</option>"
        "<option value='role'>Chat Role</option>"
        "<option value='switch'>Switch vs Stay</option>"
    )
    palette_json = json.dumps({name: list(WATERFALL_PALETTES[name]) for name in waterfall_palette_names})

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
    agent_warning_rows = "\n".join(
        f"<li>{escape(str(warn))}</li>"
        for warn in (agent_edit_summary.get("warnings") if isinstance(agent_edit_summary.get("warnings"), list) else [])
    )
    media_warning_rows = "\n".join(
        f"<li>{escape(str(warn))}</li>"
        for warn in (media_summary.get("warnings") if isinstance(media_summary.get("warnings"), list) else [])
    )
    notes_warning_rows = "\n".join(
        f"<li>{escape(str(warn))}</li>"
        for warn in (notes_meta_summary.get("warnings") if isinstance(notes_meta_summary.get("warnings"), list) else [])
    )
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
      --git: #2f6f3e;
      --activity: #9333ea;
      --media: #0f766e;
      --input: #a16207;
      --window: #9d174d;
      --branch: #0f766e;
      --pr: #7c3aed;
      --line: #d9e1d9;
    }}
    body {{ margin: 0; background: radial-gradient(circle at top left, #e7f2ea, var(--bg)); color: var(--ink); font-family: "IBM Plex Sans", "Segoe UI", sans-serif; }}
    main {{ width: min(1200px, calc(100vw - 0.6rem)); margin: 0 auto; padding: 1.2rem; box-sizing: border-box; display: grid; gap: 1rem; overflow-x: hidden; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 0.9rem; min-width: 0; }}
    h1,h2 {{ margin: 0 0 0.6rem 0; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .meta {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.92rem; }}
    .grid {{ display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); min-width: 0; }}
    .metric {{ border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem; }}
    .metric b {{ display:block; font-size: 1.3rem; margin-top: 0.2rem; }}
    .metric small {{ display:block; margin-top: 0.2rem; color: #4b5563; font-size: 0.78rem; }}
    .bars {{ display: grid; gap: 0.8rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); min-width: 0; }}
    .bars ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 0.3rem; }}
    .bars li {{ display: grid; grid-template-columns: 2.2rem 1fr 2rem; align-items: center; gap: 0.4rem; }}
    .bar-wrap {{ border: 1px solid var(--line); border-radius: 7px; overflow: hidden; height: 0.7rem; }}
    .bar {{ height: 100%; }}
    .chat {{ background: var(--chat); }} .shell {{ background: var(--shell); }} .git {{ background: var(--git); }} .activity {{ background: var(--activity); }} .media {{ background: var(--media); }} .input {{ background: var(--input); }} .window {{ background: var(--window); }} .branch {{ background: var(--branch); }} .pr {{ background: var(--pr); }}
    .table-scroll {{ max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    .table-scroll table {{ width: max-content; min-width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 0.35rem; vertical-align: top; }}
    .filter-grid {{ display: grid; gap: 0.65rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-bottom: 0.7rem; min-width: 0; }}
    .filter-block {{ border: 1px solid var(--line); border-radius: 8px; padding: 0.45rem; background: #fbfcfb; }}
    .filter-search {{ display: flex; gap: 0.4rem; margin-top: 0.35rem; }}
    .filter-search input[type="search"] {{ flex: 1; border: 1px solid var(--line); border-radius: 6px; padding: 0.25rem 0.4rem; font: inherit; }}
    .filter-search button {{ border: 1px solid var(--line); border-radius: 6px; background: #f5f7f4; padding: 0.25rem 0.5rem; cursor: pointer; }}
    .filter-options {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.35rem; }}
    .filter-options label {{ display: inline-flex; align-items: center; gap: 0.2rem; border: 1px solid var(--line); border-radius: 999px; padding: 0.1rem 0.35rem; background: #f7faf7; font-size: 0.82rem; }}
    .timeline-count {{ margin-top: 0.4rem; font-size: 0.82rem; color: #4b5563; }}
    code {{ background: #eff2ef; border-radius: 4px; padding: 0.05rem 0.2rem; white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; }}
    pre {{ white-space: pre-wrap; word-break: break-word; margin: 0.45rem 0 0 0; font-family: "IBM Plex Mono", "Consolas", monospace; font-size: 0.82rem; }}
    th, td {{ overflow-wrap: anywhere; word-break: break-word; }}
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
    .wf-strip {{ display: flex; gap: var(--wf-gap, 0.1rem); overflow-x: auto; padding: 0.25rem 0 0.35rem 0; }}
    .wf-seg {{ width: 0.24rem; height: var(--wf-seg-h, 0.95rem); border-radius: 2px; border: 1px solid rgba(0, 0, 0, 0.15); flex: 0 0 auto; }}
    .wf-seg.switch {{ outline: 2px solid rgba(17, 24, 39, 0.65); outline-offset: 1px; }}
    .wf-controls {{ display: flex; gap: 0.6rem; flex-wrap: wrap; align-items: center; margin-top: 0.45rem; }}
    .wf-controls label {{ font-size: 0.84rem; color: #374151; display: inline-flex; align-items: center; gap: 0.35rem; }}
    .wf-controls select, .wf-controls input {{ border: 1px solid var(--line); border-radius: 6px; padding: 0.25rem 0.4rem; font: inherit; max-width: 28rem; }}
    .wf-controls button {{ border: 1px solid var(--line); border-radius: 6px; background: #f5f7f4; padding: 0.28rem 0.55rem; cursor: pointer; }}
    .wf-controls code {{ font-size: 0.76rem; }}
    .wf-legend {{ list-style: none; margin: 0.5rem 0 0 0; padding: 0; display: grid; gap: 0.3rem; }}
    .wf-legend li {{ display: flex; align-items: center; gap: 0.35rem; }}
    .wf-swatch {{ width: 0.75rem; height: 0.75rem; border-radius: 3px; border: 1px solid rgba(0, 0, 0, 0.25); display: inline-block; }}
    .wf-note {{ margin-top: 0.45rem; color: #4b5563; font-size: 0.84rem; }}
    .wf-view {{ margin-top: 0.5rem; }}
    .wf-waterfall-wrap {{ max-width: 100%; overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: #f9fbf9; padding: 0.35rem; }}
    .wf-lane-svg {{ display: block; width: 100%; min-width: 52rem; height: auto; }}
    .wf-lane-bg {{ fill: #f9fbf9; }}
    .wf-lane-line {{ stroke: #d9e1d9; stroke-width: 1; }}
    .wf-lane-label {{ fill: #374151; font-size: 11px; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .wf-axis {{ fill: #4b5563; font-size: 11px; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .wf-edge {{ fill: none; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }}
    .wf-edge.stay {{ stroke: rgba(75, 85, 99, 0.42); }}
    .wf-edge.switch {{ stroke: rgba(17, 24, 39, 0.75); stroke-dasharray: 3 2; }}
    .wf-node {{ stroke: rgba(17, 24, 39, 0.65); stroke-width: 0.8; }}
    .role-topbar {{ position: sticky; top: 0; z-index: 50; background: rgba(243, 246, 240, 0.88); backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }}
    .role-topbar-inner {{ width: min(1200px, calc(100vw - 0.6rem)); margin: 0 auto; padding: 0.55rem 1.2rem; box-sizing: border-box; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }}
    .role-topbar b {{ font-family: "IBM Plex Mono", "Consolas", monospace; font-size: 0.82rem; color: #374151; margin-right: 0.25rem; }}
    .role-tab {{ border: 1px solid var(--line); border-radius: 999px; background: #ffffff; padding: 0.25rem 0.55rem; cursor: pointer; font: inherit; font-size: 0.88rem; }}
    .role-tab[aria-pressed="true"] {{ background: #e7f2ea; border-color: #8ecfb4; color: #0b6e4f; }}
    .role-topbar-spacer {{ flex: 1 1 auto; }}
    .role-topbar-link {{ font-size: 0.86rem; color: #1d4ed8; text-decoration: none; border-bottom: 1px dashed rgba(29, 78, 216, 0.45); }}
    .role-topbar-link:hover {{ border-bottom-style: solid; }}
    @media (max-width: 760px) {{
      main {{ width: min(1200px, calc(100vw - 0.2rem)); padding: 0.75rem; }}
      .table-scroll table {{ font-size: 0.82rem; }}
      .wf-controls {{ flex-direction: column; align-items: flex-start; }}
      .wf-controls input {{ max-width: 100%; width: 100%; }}
      .wf-lane-svg {{ min-width: 38rem; }}
    }}
  </style>
</head>
<body>
  <div class="role-topbar">
    <div class="role-topbar-inner">
      <b>View</b>
      <button class="role-tab" type="button" data-role="StatiBaker" aria-pressed="true">StatiBaker</button>
      <button class="role-tab" type="button" data-role="TiRC (transcript and recording)" aria-pressed="false">TiRC (transcript and recording)</button>
      <button class="role-tab" type="button" data-role="Fuzzymodo" aria-pressed="false">Fuzzymodo</button>
      <button class="role-tab" type="button" data-role="casey-git-clone" aria-pressed="false">casey-git-clone</button>
      <button class="role-tab" type="button" data-role="SensibLaw" aria-pressed="false">SensibLaw</button>
      <button class="role-tab" type="button" data-role="All" aria-pressed="false">All</button>
      <span class="role-topbar-spacer"></span>
      <a class="role-topbar-link" href="#" id="role-show-all">Show all sections</a>
    </div>
  </div>
  <main>
    <section class="panel" data-role="SensibLaw">
      <h2>SensibLaw</h2>
      <p><small>No SensibLaw data in this dashboard view.</small></p>
    </section>
    <section class="panel" data-role="casey-git-clone">
      <h2>casey-git-clone</h2>
      <p><small>No casey-git-clone specific panels in this dashboard view (yet).</small></p>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h1>SB Activity Dashboard</h1>
      <div class="meta">
        <div><b>Date:</b> <code>{escape(str(payload.get("date", "")))}</code></div>
        <div><b>Generated:</b> <code>{escape(str(payload.get("generated_at", "")))}</code></div>
        <div><b>Chat source:</b> <code>{escape(str(payload.get("chat_source", "")))}</code></div>
        <div><b>Chat scope:</b> <code>{escape(str(payload.get("chat_scope_mode", "scoped")))}</code></div>
      </div>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Summary</h2>
      <p class="wf-note"><small>Use the top tabs to switch between tool/role views.</small></p>
      <div class="grid">
        <div class="metric">Chat messages<b>{summary.get("chat_messages", 0)}</b></div>
        <div class="metric">Chat threads<b>{summary.get("chat_threads", 0)}</b></div>
        <div class="metric">Context switch rate<b>{context_switch_rate_pct:.1f}%</b><small>primary score</small></div>
        <div class="metric">Messages/hour (active)<b>{messages_per_hour_active:.2f}</b><small>{_safe_int(summary.get("chat_active_hours"))} active hour(s)</small></div>
        <div class="metric">Messages/chat<b>{messages_per_chat:.2f}</b></div>
        <div class="metric">Switches/hour (active)<b>{switches_per_active_hour:.2f}</b></div>
        <div class="metric">Top-thread share<b>{top_thread_share_pct:.1f}%</b></div>
        <div class="metric">Chat switches<b>{_safe_int(summary.get("chat_switches"))}</b><small>{chat_switch_rate_pct:.1f}% of transitions</small></div>
        <div class="metric">Chat tokens (est)<b>{chat_tokens_est}</b><small>input={chat_input_tokens_est}, output={chat_output_tokens_est}, chars/4 heuristic</small></div>
        <div class="metric">Context overflow (est)<b>{chat_context_overflow_threads} thread(s)</b><small>overflow_tokens={chat_context_overflow_tokens}, max-thread-usage={chat_context_max_thread_usage_pct:.1f}% of {chat_context_default_window_tokens} tokens</small></div>
        <div class="metric">Shell commands<b>{summary.get("shell_commands", 0)}</b><small>host={_safe_int(summary.get("shell_commands_host"))}, agent_exec={_safe_int(summary.get("shell_commands_agent_exec"))}</small></div>
        <div class="metric">Agent edit blocks<b>{agent_edit_blocks}</b><small>messages with edits={_safe_int(agent_edit_summary.get("messages_with_edits"))}</small></div>
        <div class="metric">Agent files touched<b>{agent_edit_files}</b><small>focus={escape(agent_edit_focus_mode)}, top-file-share={agent_edit_top_file_share * 100.0:.1f}%</small></div>
        <div class="metric">Agent line deltas<b>+{agent_edit_lines_added} / -{agent_edit_lines_removed}</b></div>
        <div class="metric">Media events<b>{media_events_total}</b></div>
        <div class="metric">Media items observed<b>{media_items_total}</b></div>
        <div class="metric">Media consumed<b>{_format_seconds_compact(media_consumed_seconds)}</b><small>{media_consumed_seconds / 3600.0:.2f}h total</small></div>
        <div class="metric">Media completion/churn<b>{media_completion_ratio * 100.0:.1f}% / {media_churn_rate * 100.0:.1f}%</b><small>completion by watched/content and churn by low-complete early switches</small></div>
        <div class="metric">iNaturalist insects<b>{inat_insects_today}</b><small>{escape(inat_phase)} · {escape(inat_expectation)} · {inat_available_days}/{inat_window_days}d window</small></div>
        <div class="metric">Mood reports<b>{mood_reports_today}</b><small>{escape(mood_latest_code)} {escape(mood_latest_ts)}</small></div>
        <div class="metric">Chat-media overlap<b>{chat_media_overlap_hours}h ({chat_media_overlap_rate_pct:.1f}%)</b><small>hour buckets where chat and media co-occur</small></div>
        <div class="metric">Concurrent chat messages<b>{chat_messages_with_media_nearby}/{_safe_int(summary.get("chat_messages", 0))}</b><small>within ±{concurrency_window_minutes}m of media event ({chat_messages_with_media_nearby_rate_pct:.1f}%)</small></div>
        <div class="metric">Voice/transcribe overlap<b>{chat_messages_with_voice_activity_nearby}/{_safe_int(summary.get("chat_messages", 0))}</b><small>within ±{concurrency_window_minutes}m of voice-like activity ({chat_messages_with_voice_activity_nearby_rate_pct:.1f}%), voice events={voice_activity_events}</small></div>
        <div class="metric">Chat-input/activity overlap<b>{chat_input_overlap_hours}h / {chat_activity_overlap_hours}h</b><small>chat+input={chat_input_overlap_rate_pct:.1f}%, chat+activity={chat_activity_overlap_rate_pct:.1f}% of chat-active hours; chat msgs near input={chat_messages_with_input_nearby}/{_safe_int(summary.get("chat_messages", 0))} ({chat_messages_with_input_nearby_rate_pct:.1f}%)</small></div>
        <div class="metric">Input events<b>{summary.get("input_events", 0)}</b></div>
        <div class="metric">Window focus events<b>{summary.get("window_focus_events", 0)}</b></div>
        <div class="metric">Activity events<b>{summary.get("activity_events", 0)}</b></div>
        <div class="metric">Notes meta events<b>{notes_total_events}</b></div>
        <div class="metric">NotebookLM meta events<b>{notebooklm_events}</b><small>{escape(notes_app_counts_text)}</small></div>
        <div class="metric">Git branch events<b>{summary.get("git_branch_events", 0)}</b></div>
        <div class="metric">PR events<b>{summary.get("pr_events", 0)}</b></div>
        <div class="metric">PR merged/commented/received<b>{summary.get("pr_merged", 0)}/{summary.get("pr_commented", 0)}/{summary.get("pr_received", 0)}</b></div>
      </div>
      <p class="wf-note">{escape(trailing_text)}</p>
    </section>
    <section class="panel" data-role="Fuzzymodo">
      <h2>Observer Overlays</h2>
      <p class="wf-note"><small>Note: this panel may include non-Fuzzymodo overlays today; finer per-tool tab splits can come next.</small></p>
      <p><small>Tip: Casey overlays will also be shown under <code>casey-git-clone</code> once overlays are split by kind.</small></p>
      <p><small>Observer-class overlays only; reference-heavy. Joins (when present) are read-only lookups by locator/id.</small></p>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Observer</th>
              <th>Annotation</th>
              <th>Activity</th>
              <th>Date</th>
              <th>Status</th>
              <th>Join</th>
            </tr>
          </thead>
          <tbody>{observer_overlay_rows if observer_overlay_rows else "<tr><td colspan='6'>No overlays.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
    <section class="panel bars" data-role="StatiBaker">
      <div><h2>Messages/hour</h2><ul>{_render_hour_rows(freq.get("chat", _empty_bins()), "chat")}</ul></div>
      <div><h2>Shell/hour</h2><ul>{_render_hour_rows(freq.get("shell", _empty_bins()), "shell")}</ul></div>
      <div><h2>Commits/hour</h2><ul>{_render_hour_rows(freq.get("git", _empty_bins()), "git")}</ul></div>
      <div><h2>Activity/hour</h2><ul>{_render_hour_rows(freq.get("activity", _empty_bins()), "activity")}</ul></div>
      <div><h2>Media/hour</h2><ul>{_render_hour_rows(freq.get("media", _empty_bins()), "media")}</ul></div>
      <div><h2>Input/hour</h2><ul>{_render_hour_rows(freq.get("input", _empty_bins()), "input")}</ul></div>
      <div><h2>Window/hour</h2><ul>{_render_hour_rows(freq.get("window", _empty_bins()), "window")}</ul></div>
      <div><h2>Branch/hour</h2><ul>{_render_hour_rows(freq.get("git_branch", _empty_bins()), "branch")}</ul></div>
      <div><h2>PR/hour</h2><ul>{_render_hour_rows(freq.get("pr", _empty_bins()), "pr")}</ul></div>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Process Artifacts</h2>
      <ul class="links">{"".join(artifact_rows) if artifact_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel" data-role="TiRC (transcript and recording)">
      <h2>Chat Threads</h2>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Thread ID</th><th>Title</th><th>Origin</th><th>Messages</th><th>First</th><th>Last</th><th>Roles</th></tr></thead>
          <tbody>{"".join(thread_rows) if thread_rows else "<tr><td colspan='7'>No chat thread activity for this date.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
    <section class="panel" data-role="TiRC (transcript and recording)">
      <h2>Chat Context Usage (Estimated)</h2>
      <p>
        chars=<code>{_safe_int(chat_context_usage.get("chars_est"))}</code>,
        tokens=<code>{chat_tokens_est}</code>,
        input=<code>{chat_input_tokens_est}</code>,
        output=<code>{chat_output_tokens_est}</code>,
        default_window=<code>{chat_context_default_window_tokens}</code>,
        overflow_threads=<code>{chat_context_overflow_threads}</code>,
        overflow_tokens=<code>{chat_context_overflow_tokens}</code>
      </p>
      <p><small>Heuristic only: token estimate uses <code>max(1, round(chars/4.0))</code>. Day-scoped logs may undercount true full-thread history.</small></p>
      <p><small>Window sweep:</small></p>
      <ul>{context_window_rows if context_window_rows else "<li>None</li>"}</ul>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Thread</th><th>Messages</th><th>Chars (est)</th><th>Tokens (est)</th><th>Usage ({chat_context_default_window_tokens})</th><th>Overflow tokens</th><th>Token share</th></tr></thead>
          <tbody>{"".join(context_thread_rows) if context_thread_rows else "<tr><td colspan='7'>No chat thread activity for this date.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
    <section class="panel" data-role="TiRC (transcript and recording)">
      <h2>Chat Flow Visualizations</h2>
      <p>
        messages=<code>{_safe_int(chat_flow.get("message_count"))}</code>,
        threads=<code>{_safe_int(chat_flow.get("thread_count"))}</code>,
        switches=<code>{_safe_int(chat_flow.get("switch_count"))}</code>,
        switch_rate=<code>{_safe_float(chat_flow.get("switch_rate")) * 100.0:.1f}%</code>,
        window=<code>{escape(str(chat_flow.get("first_ts") or ""))}</code> to
        <code>{escape(str(chat_flow.get("last_ts") or ""))}</code>
      </p>
      <div class="wf-controls">
        <label>View
          <select id="wf-view-mode">
            <option value="linear">Legacy / Linear</option>
            <option value="waterfall">Actual Waterfall</option>
          </select>
        </label>
        <label>Palette
          <select id="wf-palette">
            {palette_options_html}
          </select>
        </label>
        <label>Color by
          <select id="wf-color-algo">
            {algo_options_html}
          </select>
        </label>
        <label>Custom colors
          <input id="wf-custom" type="text" placeholder="#440154,#31688e,#35b779,#fde725">
        </label>
        <button id="wf-custom-apply" type="button">Apply</button>
        <button id="wf-custom-reset" type="button">Reset</button>
        <code>comma-separated css colors</code>
      </div>
      <div id="wf-linear-wrap" class="wf-view wf-linear-wrap">
        <div class="wf-strip" style="--wf-gap: {wf_strip_gap:.2f}rem; --wf-seg-h: {wf_seg_h:.2f}rem;">{"".join(flow_segments) if flow_segments else "<span>No chat messages for this date.</span>"}</div>
        <p class="wf-note">
          {(
            f"Showing newest {_safe_int(chat_flow.get('waterfall_render_limit'))} of {_safe_int(chat_flow.get('message_count'))} messages. This is a linear time strip (not a classical waterfall); width encodes elapsed time until the next message."
            if bool(chat_flow.get("waterfall_truncated"))
            else "Each block is one chat message. This is a linear time strip (not a classical waterfall). Width encodes elapsed time until the next message; outlined blocks mark a jump to a different thread."
          )}
        </p>
      </div>
      <div id="wf-waterfall-wrap" class="wf-view wf-waterfall-wrap" style="display:none;">
        {lane_svg_markup if lane_available else "<p class='wf-note'>Actual waterfall unavailable for this date.</p>"}
      </div>
      <p class="wf-note" id="wf-waterfall-note" style="display:none;">
        Actual waterfall mode uses thread lanes over time. Nodes are messages, connectors follow chronological message order, and dashed connectors indicate cross-thread switches.
      </p>
      <div id="wf-waterfall-blockers" style="display:none;">
        <p class="wf-note">Why unavailable:</p>
        <ul class="wf-legend">{lane_blocker_rows if lane_blocker_rows else "<li>None</li>"}</ul>
      </div>
      <ul class="wf-legend">{"".join(flow_thread_rows) if flow_thread_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel">
      <h2>Media Consumption</h2>
      <p>
        events=<code>{media_events_total}</code>,
        unique_items=<code>{media_items_total}</code>,
        consumed=<code>{_format_seconds_compact(media_consumed_seconds)}</code>,
        content=<code>{_format_seconds_compact(media_content_seconds)}</code>,
        completion=<code>{media_completion_ratio * 100.0:.1f}%</code>,
        churn=<code>{media_churn_events}</code> (<code>{media_churn_rate * 100.0:.1f}%</code>)
      </p>
      <p><small>Churn candidate heuristic: completion ratio &lt; 35% and next different item appears within 15 minutes.</small></p>
      <p><small>Concurrency view: chat-media overlap=<code>{chat_media_overlap_hours}h</code>; chat messages near media (<code>±{concurrency_window_minutes}m</code>)=<code>{chat_messages_with_media_nearby}</code>/<code>{_safe_int(summary.get("chat_messages", 0))}</code>.</small></p>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Platform</th><th>Events</th><th>Items</th><th>Consumed</th><th>Content</th><th>Completion</th></tr></thead>
          <tbody>{"".join(media_platform_rows) if media_platform_rows else "<tr><td colspan='6'>No media events for this date.</td></tr>"}</tbody>
        </table>
      </div>
      <p><b>Media warnings:</b></p>
      <ul>{media_warning_rows if media_warning_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel" data-role="TiRC (transcript and recording)">
      <h2>NotebookLM Lifecycle (Metadata)</h2>
      <p><small>Snapshot/observed rows are tracked as <code>seen</code>. Lifecycle events are inferred from each row&apos;s event name.</small></p>
      <div class="grid">
        <div class="metric">Notebooks created<b>{_safe_int(notebook_lifecycle.get("created"))}</b></div>
        <div class="metric">Notebooks modified<b>{_safe_int(notebook_lifecycle.get("modified"))}</b></div>
        <div class="metric">Notebooks moved/renamed<b>{_safe_int(notebook_lifecycle.get("moved"))}</b></div>
        <div class="metric">Notebooks deleted<b>{_safe_int(notebook_lifecycle.get("deleted"))}</b></div>
        <div class="metric">Notebooks seen<b>{_safe_int(notebook_lifecycle.get("seen"))}</b></div>
        <div class="metric">Files created<b>{_safe_int(file_lifecycle.get("created"))}</b></div>
        <div class="metric">Files modified<b>{_safe_int(file_lifecycle.get("modified"))}</b></div>
        <div class="metric">Files moved/renamed<b>{_safe_int(file_lifecycle.get("moved"))}</b></div>
        <div class="metric">Files deleted<b>{_safe_int(file_lifecycle.get("deleted"))}</b></div>
        <div class="metric">Files seen<b>{_safe_int(file_lifecycle.get("seen"))}</b></div>
      </div>
      <p><b>Lifecycle warnings:</b></p>
      <ul>{notes_warning_rows if notes_warning_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Tool Use Summary</h2>
      <p>
        source=<code>{escape(str(tool_use_summary.get("source", "none")))}</code>,
        tool_messages=<code>{_safe_int(tool_use_summary.get("total_tool_messages"))}</code>,
        exec_command(run requests)=<code>{_safe_int(tool_use_summary.get("exec_command_count"))}</code>,
        with_workdir=<code>{_safe_int(tool_use_summary.get("exec_with_workdir_count"))}</code>,
        without_workdir=<code>{_safe_int(tool_use_summary.get("exec_without_workdir_count"))}</code>,
        unique_commands=<code>{_safe_int(tool_use_summary.get("unique_commands"))}</code>
      </p>
      <p><small>Only structured <code>role=tool</code> <code>exec_command</code> payloads are counted as agent-run requests; printed command text is not counted.</small></p>
      <p><b>Top directories touched:</b></p>
      <ul>{"".join(tool_dir_rows) if tool_dir_rows else "<li>None</li>"}</ul>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Command Family</th><th>Count</th><th>Unique Variants</th><th>Top Dirs</th><th>Variants</th></tr></thead>
          <tbody>{"".join(tool_family_rows) if tool_family_rows else "<tr><td colspan='5'>No tool command activity parsed.</td></tr>"}</tbody>
        </table>
      </div>
      <p><b>Tool summary warnings:</b></p>
      <ul>{tool_warning_rows if tool_warning_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Agent Edit Activity</h2>
      <p>
        source=<code>{escape(str(agent_edit_summary.get("source") or "none"))}</code>,
        messages_scanned=<code>{_safe_int(agent_edit_summary.get("messages_scanned"))}</code>,
        messages_with_edits=<code>{_safe_int(agent_edit_summary.get("messages_with_edits"))}</code>,
        edit_blocks=<code>{agent_edit_blocks}</code>,
        files_touched=<code>{agent_edit_files}</code>,
        top_file_share=<code>{agent_edit_top_file_share * 100.0:.1f}%</code>,
        mode=<code>{escape(agent_edit_focus_mode)}</code>
      </p>
      <p><small>Parsed from assistant/tool message text using <code>Edited &lt;file&gt; (+a -b)</code> blocks. Line refs are best-effort when snippets include explicit line numbers.</small></p>
      <div class="table-scroll">
        <table>
          <thead><tr><th>File</th><th>Blocks</th><th>Delta</th><th>Total Edits</th><th>Share</th><th>Line Refs</th></tr></thead>
          <tbody>{"".join(agent_edit_rows) if agent_edit_rows else "<tr><td colspan='6'>No parsed agent edit blocks for this date.</td></tr>"}</tbody>
        </table>
      </div>
      <p><b>Agent edit warnings:</b></p>
      <ul>{agent_warning_rows if agent_warning_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel" data-role="TiRC (transcript and recording)">
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
      <div class="table-scroll">
        <table id="timeline-table">
          <thead><tr><th>TS</th><th>Kind</th><th>Detail</th><th>Chars</th><th>Source</th></tr></thead>
          <tbody>{"".join(timeline_rows) if timeline_rows else "<tr><td colspan='5'>No timeline events.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Warnings</h2>
      <ul>{warning_rows if warning_rows else "<li>None</li>"}</ul>
    </section>
  </main>
  <script>
    (() => {{
      const ROLE_KEY = "sb_dashboard_role_tab";
      const tabs = Array.from(document.querySelectorAll(".role-tab[data-role]"));
      const panels = Array.from(document.querySelectorAll("section.panel[data-role]"));
      if (!tabs.length || !panels.length) return;

      const setRole = (role) => {{
        const chosen = String(role || "StatiBaker");
        try {{ localStorage.setItem(ROLE_KEY, chosen); }} catch (_) {{}}
        tabs.forEach((btn) => {{
          const pressed = (btn.dataset.role || "") === chosen;
          btn.setAttribute("aria-pressed", pressed ? "true" : "false");
        }});
        panels.forEach((panel) => {{
          const panelRole = panel.dataset.role || "";
          panel.style.display = (chosen === "All" || panelRole === chosen) ? "" : "none";
        }});
      }};

      tabs.forEach((btn) => {{
        btn.addEventListener("click", () => setRole(btn.dataset.role || "StatiBaker"));
      }});

      const showAllLink = document.getElementById("role-show-all");
      if (showAllLink) {{
        showAllLink.addEventListener("click", (evt) => {{
          evt.preventDefault();
          setRole("All");
        }});
      }}

      let initial = "StatiBaker";
      try {{ initial = localStorage.getItem(ROLE_KEY) || initial; }} catch (_) {{}}
      if (!tabs.some((b) => (b.dataset.role || "") === initial)) initial = "StatiBaker";
      setRole(initial);
    }})();

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
    (() => {{
      const modeSelect = document.getElementById("wf-view-mode");
      const paletteSelect = document.getElementById("wf-palette");
      const algoSelect = document.getElementById("wf-color-algo");
      const customInput = document.getElementById("wf-custom");
      const customApply = document.getElementById("wf-custom-apply");
      const customReset = document.getElementById("wf-custom-reset");
      const linearWrap = document.getElementById("wf-linear-wrap");
      const waterfallWrap = document.getElementById("wf-waterfall-wrap");
      const waterfallNote = document.getElementById("wf-waterfall-note");
      const waterfallBlockers = document.getElementById("wf-waterfall-blockers");
      const segNodes = Array.from(document.querySelectorAll(".wf-seg-colorable"));
      const laneNodes = Array.from(document.querySelectorAll(".wf-lane-colorable"));
      const swatchNodes = Array.from(document.querySelectorAll(".wf-swatch.wf-colorable"));
      if (!modeSelect || !paletteSelect || !algoSelect || !customInput || !customApply || !customReset || !linearWrap || !waterfallWrap) return;

      const laneAvailable = {lane_available_json};
      const PALETTE_KEY = "sb_dashboard_waterfall_palette";
      const ALGO_KEY = "sb_dashboard_waterfall_color_algo";
      const CUSTOM_KEY = "sb_dashboard_waterfall_custom";
      const MODE_KEY = "sb_dashboard_waterfall_view_mode";
      const defaultPalette = "viridis";
      const defaultAlgo = "thread";
      const defaultMode = laneAvailable ? "waterfall" : "linear";
      const palettes = {palette_json};
      const colorableNodes = segNodes.concat(laneNodes);
      const roleValues = Array.from(
        new Set(
          colorableNodes.map((node) => String(node.dataset.role || "unknown").trim().toLowerCase() || "unknown")
        )
      ).sort();
      const roleIndex = new Map(roleValues.map((role, idx) => [role, idx]));

      const parseCustomColors = (value) => {{
        return String(value || "")
          .split(",")
          .map((item) => item.trim())
          .filter((item) => item.length > 0);
      }};

      const resolveColors = (paletteName) => {{
        if (paletteName === "custom") {{
          const customColors = parseCustomColors(customInput.value);
          if (customColors.length) return customColors;
          return palettes[defaultPalette] || [];
        }}
        return palettes[paletteName] || palettes[defaultPalette] || [];
      }};

      const segmentIndex = (node, algoName, paletteSize) => {{
        const threadIdx = Number(node.dataset.threadIndex || "0");
        if (algoName === "hour") {{
          const hour = Math.max(0, Math.min(23, Number(node.dataset.threadStartHour || node.dataset.hour || "0")));
          return Math.floor((hour / 24) * Math.max(1, paletteSize));
        }}
        if (algoName === "role") {{
          const role = String(node.dataset.role || "unknown").trim().toLowerCase() || "unknown";
          return roleIndex.get(role) || 0;
        }}
        if (algoName === "switch") {{
          const isSwitch = String(node.dataset.switch || "stay").toLowerCase() === "switch";
          return isSwitch ? Math.max(1, paletteSize - 1) : 0;
        }}
        return threadIdx;
      }};

      const applyColors = (paletteName, algoName) => {{
        const colors = resolveColors(paletteName);
        colorableNodes.forEach((node) => {{
          const idx = segmentIndex(node, algoName, colors.length);
          const fallback = node.dataset.defaultColor || "#6b7280";
          const color = colors.length ? colors[Math.abs(idx) % colors.length] : fallback;
          const tagName = String(node.tagName || "").toLowerCase();
          if (tagName === "circle") {{
            node.style.fill = color;
          }} else {{
            node.style.background = color;
          }}
        }});
        swatchNodes.forEach((node) => {{
          const idx = algoName === "hour"
            ? Math.floor((Math.max(0, Math.min(23, Number(node.dataset.threadStartHour || "0"))) / 24) * Math.max(1, colors.length))
            : Number(node.dataset.threadIndex || "0");
          const fallback = node.dataset.defaultColor || "#6b7280";
          const color = colors.length ? colors[Math.abs(idx) % colors.length] : fallback;
          node.style.background = color;
        }});
      }};

      const setMode = (modeName, persist = true) => {{
        const mode = modeName === "waterfall" ? "waterfall" : "linear";
        modeSelect.value = mode;
        linearWrap.style.display = mode === "linear" ? "block" : "none";
        waterfallWrap.style.display = mode === "waterfall" ? "block" : "none";
        if (waterfallNote) {{
          waterfallNote.style.display = mode === "waterfall" ? "block" : "none";
        }}
        if (waterfallBlockers) {{
          waterfallBlockers.style.display = mode === "waterfall" && !laneAvailable ? "block" : "none";
        }}
        if (persist) {{
          localStorage.setItem(MODE_KEY, mode);
        }}
      }};

      const setStyle = (paletteName, algoName, persist = true) => {{
        const name = paletteName || defaultPalette;
        const algo = algoName || defaultAlgo;
        paletteSelect.value = name;
        algoSelect.value = algo;
        applyColors(name, algo);
        if (persist) {{
          localStorage.setItem(PALETTE_KEY, name);
          localStorage.setItem(ALGO_KEY, algo);
          localStorage.setItem(CUSTOM_KEY, customInput.value.trim());
        }}
      }};

      const storedCustom = localStorage.getItem(CUSTOM_KEY) || "";
      const storedPalette = localStorage.getItem(PALETTE_KEY) || defaultPalette;
      const storedAlgo = localStorage.getItem(ALGO_KEY) || defaultAlgo;
      const storedMode = localStorage.getItem(MODE_KEY) || defaultMode;
      if (storedCustom) {{
        customInput.value = storedCustom;
      }}
      if (!paletteSelect.querySelector(`option[value="${{storedPalette}}"]`)) {{
        setStyle(defaultPalette, storedAlgo, false);
      }} else if (!algoSelect.querySelector(`option[value="${{storedAlgo}}"]`)) {{
        setStyle(storedPalette, defaultAlgo, false);
      }} else {{
        setStyle(storedPalette, storedAlgo, false);
      }}
      setMode(storedMode, false);

      modeSelect.addEventListener("change", () => {{
        setMode(modeSelect.value, true);
      }});
      paletteSelect.addEventListener("change", () => {{
        setStyle(paletteSelect.value, algoSelect.value, true);
      }});
      algoSelect.addEventListener("change", () => {{
        setStyle(paletteSelect.value, algoSelect.value, true);
      }});
      customApply.addEventListener("click", () => {{
        paletteSelect.value = "custom";
        setStyle("custom", algoSelect.value, true);
      }});
      customReset.addEventListener("click", () => {{
        customInput.value = "";
        setStyle(defaultPalette, algoSelect.value, true);
      }});
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
    agent_edit_summary = _load_agent_edit_summary_sqlite(
        db_path=chat_db_path,
        date_text=date_text,
        thread_scope=thread_scope,
    )

    cli_events, shell_commands = _load_cli_events(logs_dir / "cli" / f"{date_text}.jsonl")
    agent_shell_commands = _safe_int(tool_use_summary.get("exec_command_count"))
    total_shell_commands = shell_commands + agent_shell_commands
    input_events, input_count, input_keys_total, input_mouse_total = _load_input_events(
        logs_dir / "input" / f"{date_text}.jsonl"
    )
    window_events, window_count = _load_window_events(logs_dir / "windows" / f"{date_text}.jsonl")
    git_events, git_commits = _load_git_events(logs_dir / "git" / f"{date_text}.jsonl")
    git_branch_events, git_branch_count = _load_git_branch_events(
        logs_dir / "git_branch" / f"{date_text}.jsonl"
    )
    pr_events, pr_count, pr_detail_counts = _load_pr_events(logs_dir / "pr" / f"{date_text}.jsonl")
    calendar_events, calendar_count = _load_calendar_events(logs_dir / "calendar" / f"{date_text}.jsonl")
    activity_events, activity_count = _load_activity_events(outputs_dir / "activity_ledger.json")
    media_events, media_summary = _load_media_events_and_summary(logs_dir / "media" / f"{date_text}.jsonl")
    notes_meta_summary = _load_notes_meta_summary(logs_dir / "notes" / f"{date_text}.jsonl")
    context_rows = _load_context_field_rows(logs_dir / "context" / f"{date_text}.jsonl")
    inat_day = _summarize_inaturalist_day(context_rows)
    mood_day = _summarize_mood_day(context_rows)
    inat_trend = _build_inaturalist_trend(end_date_text=date_text, runs_root=runs_root, days=42)
    concurrency_summary = _build_concurrency_summary(
        chat_events=chat_events,
        media_events=media_events,
        input_events=input_events,
        activity_events=activity_events,
        window_seconds=300,
    )

    all_events = (
        chat_events
        + cli_events
        + input_events
        + window_events
        + git_events
        + git_branch_events
        + pr_events
        + calendar_events
        + activity_events
        + media_events
    )
    all_events.sort(key=lambda item: item.dt)
    timeline_truncated = False
    if len(all_events) > max_timeline_events:
        all_events = all_events[-max_timeline_events:]
        timeline_truncated = True

    freq = {
        "chat": _empty_bins(),
        "shell": _empty_bins(),
        "git": _empty_bins(),
        "input": _empty_bins(),
        "window": _empty_bins(),
        "activity": _empty_bins(),
        "git_branch": _empty_bins(),
        "pr": _empty_bins(),
        "media": _empty_bins(),
        "calendar": _empty_bins(),
    }
    for event in all_events:
        if event.kind == "chat":
            _increment_bin(freq["chat"], event.dt)
        elif event.kind == "shell":
            _increment_bin(freq["shell"], event.dt)
        elif event.kind == "git":
            _increment_bin(freq["git"], event.dt)
        elif event.kind == "input":
            _increment_bin(freq["input"], event.dt)
        elif event.kind == "window":
            _increment_bin(freq["window"], event.dt)
        elif event.kind == "activity":
            _increment_bin(freq["activity"], event.dt)
        elif event.kind == "git_branch":
            _increment_bin(freq["git_branch"], event.dt)
        elif event.kind == "pr":
            _increment_bin(freq["pr"], event.dt)
        elif event.kind == "media":
            _increment_bin(freq["media"], event.dt)
        elif event.kind == "calendar":
            _increment_bin(freq["calendar"], event.dt)

    chat_flow = _build_chat_flow(chat_events)
    chat_context_usage = _build_chat_context_usage(chat_events)

    artifacts = _collect_artifact_links(
        repo_root,
        outputs_dir,
        context_root,
        scoped_thread_ids,
        include_all_chat=include_all_chat,
    )

    # Observer overlays are persisted in the dashboard sqlite DB (SB-owned). For the
    # daily payload, we expose the overlay records and a reference-heavy join view
    # that can resolve external ledgers without copying selector/norm payloads.
    itir_overlay_records: list[dict[str, Any]] = []
    itir_overlay_joins: list[dict[str, Any]] = []
    try:
        from sb.dashboard_store_sqlite import load_itir_overlay_records
        from sb.overlay_join import join_overlay_ledgers

        overlay_db_path = runs_root / "dashboard.sqlite"
        itir_overlay_records = load_itir_overlay_records(db_path=overlay_db_path)

        # Ledger db paths are optional. Join helper is resilient if db paths are not
        # provided or locators are absent.
        fuzz_ledger = None
        casey_ledger = None
        for record in itir_overlay_records:
            joined = join_overlay_ledgers(
                overlay=record,
                fuzzymodo_ledger_db_path=fuzz_ledger,
                casey_ledger_db_path=casey_ledger,
            )
            join_row: dict[str, Any] = {
                "annotation_id": str(record.get("annotation_id") or ""),
                "observer_kind": record.get("observer_kind"),
            }
            if joined.fuzzymodo_decisions:
                # Keep this minimal: stable ids/outcomes only.
                join_row["fuzzymodo_decision"] = {
                    "decision_id": joined.fuzzymodo_decisions.get("decision_id"),
                    "selector_hash": joined.fuzzymodo_decisions.get("selector_hash"),
                    "decision_state": joined.fuzzymodo_decisions.get("decision_state"),
                    "matched": joined.fuzzymodo_decisions.get("matched"),
                    "created_at": joined.fuzzymodo_decisions.get("created_at"),
                }
            if joined.casey_operation:
                join_row["casey_operation"] = {
                    "operation_id": joined.casey_operation.get("operation_id"),
                    "operation_kind": joined.casey_operation.get("operation_kind"),
                    "ws_id": joined.casey_operation.get("ws_id"),
                    "path": joined.casey_operation.get("path"),
                    "created_at": joined.casey_operation.get("created_at"),
                    "receipt_hash": joined.casey_operation.get("receipt_hash"),
                }
            if joined.casey_build:
                join_row["casey_build"] = {
                    "build_id": joined.casey_build.get("build_id"),
                    "tree_id": joined.casey_build.get("tree_id"),
                    "selection_digest": joined.casey_build.get("selection_digest"),
                    "created_at": joined.casey_build.get("created_at"),
                }
            if len(join_row) > 2:
                itir_overlay_joins.append(join_row)
    except Exception:
        # Overlays should never break dashboard generation.
        itir_overlay_records = []
        itir_overlay_joins = []
    if timeline_truncated:
        warnings.append(
            f"Timeline truncated to {max_timeline_events} events (newest retained)."
        )
    if include_all_chat:
        warnings.append(
            "Debug mode enabled: chat scope filter disabled (all chat threads scanned for this date)."
        )
    if agent_edit_summary.get("source") == "none":
        preview_agent_summary = _load_agent_edit_summary_from_chat_events(chat_events)
        if _safe_int(preview_agent_summary.get("edit_blocks")) > 0:
            agent_edit_summary = preview_agent_summary
    agent_warnings = agent_edit_summary.get("warnings") if isinstance(agent_edit_summary.get("warnings"), list) else []
    warnings.extend(str(item) for item in agent_warnings if str(item).strip())
    media_warnings = media_summary.get("warnings") if isinstance(media_summary.get("warnings"), list) else []
    warnings.extend(str(item) for item in media_warnings if str(item).strip())
    if _safe_int(chat_context_usage.get("overflow_threads")) > 0:
        warnings.append(
            "Estimated chat context overflow detected for one or more threads (heuristic chars/token model)."
        )

    overlay_kind_counts: dict[str, int] = {}
    if isinstance(itir_overlay_records, list):
        for rec in itir_overlay_records:
            if not isinstance(rec, dict):
                continue
            kind = str(rec.get("observer_kind") or "").strip() or "unknown"
            overlay_kind_counts[kind] = overlay_kind_counts.get(kind, 0) + 1

    summary = {
        "chat_messages": len(chat_events),
        "chat_threads": len(thread_activity),
        "itir_overlays_total": sum(overlay_kind_counts.values()),
        "itir_overlays_fuzzymodo_selector_v1": overlay_kind_counts.get("fuzzymodo_selector_v1", 0),
        "itir_overlays_casey_workspace_v1": overlay_kind_counts.get("casey_workspace_v1", 0),
        "itir_overlays_itir_mission_graph_v1": overlay_kind_counts.get("itir_mission_graph_v1", 0),
        "itir_overlays_other": sum(
            count
            for kind, count in overlay_kind_counts.items()
            if kind not in ("fuzzymodo_selector_v1", "casey_workspace_v1", "itir_mission_graph_v1")
        ),
        "chat_active_hours": _safe_int(chat_flow.get("active_hours")),
        "messages_per_hour_active": _safe_float(chat_flow.get("messages_per_hour_active")),
        "messages_per_hour_day": _safe_float(chat_flow.get("messages_per_hour_day")),
        "messages_per_chat": _safe_float(chat_flow.get("messages_per_chat")),
        "chat_switches": _safe_int(chat_flow.get("switch_count")),
        "chat_switch_rate": _safe_float(chat_flow.get("switch_rate")),
        "context_switch_rate": _safe_float(chat_flow.get("switch_rate")),
        "switches_per_active_hour": _safe_float(chat_flow.get("switches_per_active_hour")),
        "top_thread_share": _safe_float(chat_flow.get("dominant_thread_share")),
        "chat_chars_est": _safe_int(chat_context_usage.get("chars_est")),
        "chat_tokens_est": _safe_int(chat_context_usage.get("tokens_est")),
        "chat_input_tokens_est": _safe_int(chat_context_usage.get("input_tokens_est")),
        "chat_output_tokens_est": _safe_int(chat_context_usage.get("output_tokens_est")),
        "chat_other_tokens_est": _safe_int(chat_context_usage.get("other_tokens_est")),
        "chat_context_default_window_tokens": _safe_int(chat_context_usage.get("default_context_window_tokens"), fallback=DEFAULT_CONTEXT_WINDOW_TOKENS),
        "chat_context_overflow_threads": _safe_int(chat_context_usage.get("overflow_threads")),
        "chat_context_overflow_tokens": _safe_int(chat_context_usage.get("overflow_tokens")),
        "chat_context_max_thread_usage_pct": _safe_float(chat_context_usage.get("max_thread_usage_pct")),
        # Combined shell activity: host CLI logs + structured agent exec requests.
        "shell_commands": total_shell_commands,
        "shell_commands_host": shell_commands,
        "shell_commands_agent_exec": agent_shell_commands,
        "agent_edit_blocks": _safe_int(agent_edit_summary.get("edit_blocks")),
        "agent_edit_files": _safe_int(agent_edit_summary.get("files_touched")),
        "agent_edit_lines_added": _safe_int(agent_edit_summary.get("lines_added")),
        "agent_edit_lines_removed": _safe_int(agent_edit_summary.get("lines_removed")),
        "agent_edit_top_file_share": _safe_float(agent_edit_summary.get("top_file_share")),
        "media_events": _safe_int(media_summary.get("events")),
        "media_items_observed": _safe_int(media_summary.get("items_observed")),
        "media_consumed_seconds": _safe_int(media_summary.get("consumed_seconds")),
        "media_content_seconds": _safe_int(media_summary.get("content_duration_seconds")),
        "media_completion_ratio": _safe_float(media_summary.get("completion_ratio")),
        "media_churn_events": _safe_int(media_summary.get("churn_events")),
        "media_churn_rate": _safe_float(media_summary.get("churn_rate")),
        "inaturalist_events": _safe_int(inat_day.get("events")),
        "inaturalist_insect_observations": _safe_int(inat_day.get("insect_observations")),
        "mood_reports": _safe_int(mood_day.get("reports")),
        "concurrency_window_seconds": _safe_int(concurrency_summary.get("window_seconds"), fallback=300),
        "chat_media_overlap_hours": _safe_int(concurrency_summary.get("chat_media_overlap_hours")),
        "chat_media_overlap_rate": _safe_float(concurrency_summary.get("chat_media_overlap_rate")),
        "chat_input_overlap_hours": _safe_int(concurrency_summary.get("chat_input_overlap_hours")),
        "chat_input_overlap_rate": _safe_float(concurrency_summary.get("chat_input_overlap_rate")),
        "chat_activity_overlap_hours": _safe_int(concurrency_summary.get("chat_activity_overlap_hours")),
        "chat_activity_overlap_rate": _safe_float(concurrency_summary.get("chat_activity_overlap_rate")),
        "voice_activity_events": _safe_int(concurrency_summary.get("voice_activity_events")),
        "voice_activity_overlap_hours": _safe_int(concurrency_summary.get("voice_activity_overlap_hours")),
        "voice_activity_overlap_rate": _safe_float(concurrency_summary.get("voice_activity_overlap_rate")),
        "chat_messages_with_media_nearby": _safe_int(concurrency_summary.get("chat_messages_with_media_nearby")),
        "chat_messages_with_media_nearby_rate": _safe_float(concurrency_summary.get("chat_messages_with_media_nearby_rate")),
        "chat_messages_with_input_nearby": _safe_int(concurrency_summary.get("chat_messages_with_input_nearby")),
        "chat_messages_with_input_nearby_rate": _safe_float(concurrency_summary.get("chat_messages_with_input_nearby_rate")),
        "chat_messages_with_voice_activity_nearby": _safe_int(concurrency_summary.get("chat_messages_with_voice_activity_nearby")),
        "chat_messages_with_voice_activity_nearby_rate": _safe_float(concurrency_summary.get("chat_messages_with_voice_activity_nearby_rate")),
        "input_events": input_count,
        "input_keys_total": input_keys_total,
        "input_mouse_total": input_mouse_total,
        "window_focus_events": window_count,
        "activity_events": activity_count,
        "notes_meta_events": _safe_int(notes_meta_summary.get("total_events")),
        "notebooklm_events": _safe_int(notes_meta_summary.get("notebooklm_events")),
        "git_commits": git_commits,
        "git_branch_events": git_branch_count,
        "pr_events": pr_count,
        "pr_received": pr_detail_counts.get("pr_received", 0),
        "pr_commented": pr_detail_counts.get("pr_commented", 0),
        "pr_merged": pr_detail_counts.get("pr_merged", 0),
        "calendar_events": calendar_count,
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
        "chat_context_usage": chat_context_usage,
        "chat_context_trailing": trailing_chat_context,
        "chat_threads": thread_activity,
        "agent_edit_summary": agent_edit_summary,
        "media_summary": media_summary,
        "concurrency_summary": concurrency_summary,
        "notes_meta_summary": notes_meta_summary,
        "context_field_counts": {
            "total_rows": len(context_rows),
            "inaturalist_events": _safe_int(inat_day.get("events")),
            "mood_reports": _safe_int(mood_day.get("reports")),
        },
        "inaturalist_trend": inat_trend,
        "mood_latest": mood_day.get("latest") if isinstance(mood_day.get("latest"), dict) else {},
        "tool_use_summary": tool_use_summary,
        "artifact_links": artifacts,
        "itir_overlay_records": itir_overlay_records,
        "itir_overlay_joins": itir_overlay_joins,
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
    notes_meta_totals = _empty_notes_meta_summary()
    daily: list[dict[str, Any]] = []
    chat_source_counts: dict[str, int] = {}
    warning_days: list[dict[str, Any]] = []
    daily_payloads: list[tuple[str, dict[str, Any]]] = []

    for date_text in dates:
        payload = _load_or_build_daily_payload(
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
        notes_meta_summary = payload.get("notes_meta_summary")
        if not isinstance(notes_meta_summary, dict):
            notes_meta_summary = _load_notes_meta_summary(
                runs_root / date_text / "logs" / "notes" / f"{date_text}.jsonl"
            )
        notes_meta_totals = _merge_notes_meta_summaries(notes_meta_totals, notes_meta_summary)

        day_summary = {}
        for key in WEEKLY_SUMMARY_KEYS:
            value = _safe_int(summary.get(key))
            totals[key] += value
            day_summary[key] = value
        day_summary["context_switch_rate"] = _safe_float(summary.get("context_switch_rate"))
        day_summary["switches_per_active_hour"] = _safe_float(summary.get("switches_per_active_hour"))
        day_summary["messages_per_chat"] = _safe_float(summary.get("messages_per_chat"))
        day_summary["top_thread_share"] = _safe_float(summary.get("top_thread_share"))
        day_summary["agent_edit_top_file_share"] = _safe_float(summary.get("agent_edit_top_file_share"))
        day_summary["media_completion_ratio"] = _safe_float(summary.get("media_completion_ratio"))
        day_summary["media_churn_rate"] = _safe_float(summary.get("media_churn_rate"))

        daily_outputs = runs_root / date_text / "outputs"
        if include_all_chat:
            daily_json_path = daily_outputs / "dashboard_all.json"
            daily_html_path = daily_outputs / "dashboard_all.html"
        else:
            daily_json_path = daily_outputs / "dashboard.json"
            daily_html_path = daily_outputs / "dashboard.html"
        daily.append(
            {
                "date": date_text,
                "chat_source": source,
                "chat_scope_mode": str(payload.get("chat_scope_mode") or "scoped"),
                "summary": day_summary,
                "notes_meta_events": _safe_int(notes_meta_summary.get("total_events")),
                "notebooklm_events": _safe_int(notes_meta_summary.get("notebooklm_events")),
                "notebooklm_lifecycle": _notebooklm_lifecycle_focus(notes_meta_summary),
                "warning_count": len(day_warnings),
                "warning_preview": str(day_warnings[0]) if day_warnings else "",
                "daily_json_path": str(daily_json_path),
                "daily_html_path": str(daily_html_path),
            }
        )
        daily_payloads.append((date_text, payload))

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
    media_averages = {
        "completion_ratio": round(
            sum(_safe_float((row.get("summary") or {}).get("media_completion_ratio")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
        "churn_rate": round(
            sum(_safe_float((row.get("summary") or {}).get("media_churn_rate")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
    }
    agent_edit_averages = {
        "top_file_share": round(
            sum(_safe_float((row.get("summary") or {}).get("agent_edit_top_file_share")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
        "edits_per_file": round(
            _ratio(_safe_int(totals.get("agent_edit_lines_added")) + _safe_int(totals.get("agent_edit_lines_removed")), max(1, _safe_int(totals.get("agent_edit_files"))), digits=2),
            2,
        ),
    }
    warnings: list[str] = []
    if warning_days:
        warnings.append(f"{len(warning_days)} day(s) reported one or more warnings.")
    if include_all_chat:
        warnings.append(
            "Debug mode enabled: chat scope filter disabled (all chat threads scanned for each day)."
        )
    notes_meta_averages = {
        "total_events": round(_safe_int(notes_meta_totals.get("total_events")) / max(1, len(dates)), 2),
        "notebooklm_events": round(_safe_int(notes_meta_totals.get("notebooklm_events")) / max(1, len(dates)), 2),
    }
    weekday_hour_heatmaps = _build_weekday_hour_heatmaps_from_daily_payloads(daily_payloads)

    return {
        "period_start": dates[0],
        "period_end": dates[-1],
        "days": len(dates),
        "generated_at": _iso_utc(datetime.now(UTC)),
        "chat_scope_mode": "all" if include_all_chat else "scoped",
        "totals": totals,
        "averages_per_day": averages,
        "chat_context_averages": context_averages,
        "agent_edit_averages": agent_edit_averages,
        "media_averages": media_averages,
        "chat_source_counts": chat_source_counts,
        "notes_meta_totals": notes_meta_totals,
        "notes_meta_averages_per_day": notes_meta_averages,
        "notebooklm_lifecycle_totals": _notebooklm_lifecycle_focus(notes_meta_totals),
        "daily": daily,
        "warning_days": warning_days,
        "warnings": warnings,
        "weekday_hour_heatmaps": weekday_hour_heatmaps,
    }


def build_lifetime_dashboard(
    *,
    end_date_text: str,
    repo_root: Path,
    runs_root: Path,
    context_root: Path,
    convo_ids_path: Path,
    chat_db_path: Path,
    chat_exports_dir: Path,
    max_timeline_events: int = 600,
    include_all_chat: bool = False,
    start_date_text: str | None = None,
) -> dict[str, Any]:
    dates = _available_run_dates(
        runs_root=runs_root,
        end_date_text=end_date_text,
        start_date_text=start_date_text,
    )
    if not dates:
        raise ValueError("no run directories found for lifetime dashboard window")

    totals = {key: 0 for key in WEEKLY_SUMMARY_KEYS}
    state_totals = {key: 0 for key in LIFETIME_STATE_SUMMARY_KEYS}
    notes_meta_totals = _empty_notes_meta_summary()
    daily: list[dict[str, Any]] = []
    chat_source_counts: dict[str, int] = {}
    warning_days: list[dict[str, Any]] = []
    state_days = 0
    daily_payloads: list[tuple[str, dict[str, Any]]] = []

    for date_text in dates:
        payload = _load_or_build_daily_payload(
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
        notes_meta_summary = payload.get("notes_meta_summary")
        if not isinstance(notes_meta_summary, dict):
            notes_meta_summary = _load_notes_meta_summary(
                runs_root / date_text / "logs" / "notes" / f"{date_text}.jsonl"
            )
        notes_meta_totals = _merge_notes_meta_summaries(notes_meta_totals, notes_meta_summary)

        day_summary: dict[str, Any] = {}
        for key in WEEKLY_SUMMARY_KEYS:
            value = _safe_int(summary.get(key))
            totals[key] += value
            day_summary[key] = value
        day_summary["context_switch_rate"] = _safe_float(summary.get("context_switch_rate"))
        day_summary["switches_per_active_hour"] = _safe_float(summary.get("switches_per_active_hour"))
        day_summary["messages_per_chat"] = _safe_float(summary.get("messages_per_chat"))
        day_summary["top_thread_share"] = _safe_float(summary.get("top_thread_share"))
        day_summary["agent_edit_top_file_share"] = _safe_float(summary.get("agent_edit_top_file_share"))
        day_summary["media_completion_ratio"] = _safe_float(summary.get("media_completion_ratio"))
        day_summary["media_churn_rate"] = _safe_float(summary.get("media_churn_rate"))

        daily_json_path, daily_html_path = _daily_output_paths(
            runs_root=runs_root,
            date_text=date_text,
            include_all_chat=include_all_chat,
        )
        state_path = runs_root / date_text / "outputs" / "state.json"
        state_payload = _load_json_dict(state_path)
        if state_payload is None:
            state_volume = {
                "raw_events": 0,
                "compressed_events": 0,
                "junk_events_raw": 0,
                "junk_events_compressed": 0,
                "state_json_bytes": 0,
                "compression_ratio": 0.0,
                "expansion_ratio": 0.0,
                "junk_share_raw": 0.0,
                "junk_share_compressed": 0.0,
            }
            state_available = False
        else:
            state_volume = _estimate_state_volume(state_payload=state_payload, state_path=state_path)
            state_available = True
            state_days += 1
            for key in LIFETIME_STATE_SUMMARY_KEYS:
                state_totals[key] += _safe_int(state_volume.get(key))

        daily.append(
            {
                "date": date_text,
                "chat_source": source,
                "chat_scope_mode": str(payload.get("chat_scope_mode") or "scoped"),
                "summary": day_summary,
                "notes_meta_events": _safe_int(notes_meta_summary.get("total_events")),
                "notebooklm_events": _safe_int(notes_meta_summary.get("notebooklm_events")),
                "notebooklm_lifecycle": _notebooklm_lifecycle_focus(notes_meta_summary),
                "warning_count": len(day_warnings),
                "warning_preview": str(day_warnings[0]) if day_warnings else "",
                "daily_json_path": str(daily_json_path),
                "daily_html_path": str(daily_html_path),
                "state_available": state_available,
                "state_volume": state_volume,
            }
        )
        daily_payloads.append((date_text, payload))

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
    media_averages = {
        "completion_ratio": round(
            sum(_safe_float((row.get("summary") or {}).get("media_completion_ratio")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
        "churn_rate": round(
            sum(_safe_float((row.get("summary") or {}).get("media_churn_rate")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
    }
    agent_edit_averages = {
        "top_file_share": round(
            sum(_safe_float((row.get("summary") or {}).get("agent_edit_top_file_share")) for row in daily)
            / max(1, len(daily)),
            3,
        ),
        "edits_per_file": round(
            _ratio(_safe_int(totals.get("agent_edit_lines_added")) + _safe_int(totals.get("agent_edit_lines_removed")), max(1, _safe_int(totals.get("agent_edit_files"))), digits=2),
            2,
        ),
    }
    state_averages = {
        key: round(state_totals[key] / max(1, state_days), 2)
        for key in LIFETIME_STATE_SUMMARY_KEYS
    }
    notes_meta_averages = {
        "total_events": round(_safe_int(notes_meta_totals.get("total_events")) / max(1, len(dates)), 2),
        "notebooklm_events": round(_safe_int(notes_meta_totals.get("notebooklm_events")) / max(1, len(dates)), 2),
    }
    state_ratios = {
        "compression_ratio": _ratio(
            state_totals["compressed_events"],
            state_totals["raw_events"],
            digits=3,
        ),
        "expansion_ratio": _ratio(
            state_totals["raw_events"],
            state_totals["compressed_events"],
            digits=3,
        ),
        "junk_share_raw": _ratio(
            state_totals["junk_events_raw"],
            state_totals["raw_events"],
            digits=3,
        ),
        "junk_share_compressed": _ratio(
            state_totals["junk_events_compressed"],
            state_totals["compressed_events"],
            digits=3,
        ),
    }
    warnings: list[str] = []
    if warning_days:
        warnings.append(f"{len(warning_days)} day(s) reported one or more warnings.")
    if include_all_chat:
        warnings.append(
            "Debug mode enabled: chat scope filter disabled (all chat threads scanned for each day)."
        )
    if state_days == 0:
        warnings.append("No state.json files found in selected run window.")
    elif state_days < len(dates):
        warnings.append(
            f"State metrics available for {state_days}/{len(dates)} day(s); missing days treated as zero."
        )
    weekday_hour_heatmaps = _build_weekday_hour_heatmaps_from_daily_payloads(daily_payloads)

    return {
        "period_start": dates[0],
        "period_end": dates[-1],
        "days": len(dates),
        "generated_at": _iso_utc(datetime.now(UTC)),
        "chat_scope_mode": "all" if include_all_chat else "scoped",
        "totals": totals,
        "averages_per_day": averages,
        "chat_context_averages": context_averages,
        "agent_edit_averages": agent_edit_averages,
        "media_averages": media_averages,
        "chat_source_counts": chat_source_counts,
        "notes_meta_totals": notes_meta_totals,
        "notes_meta_averages_per_day": notes_meta_averages,
        "notebooklm_lifecycle_totals": _notebooklm_lifecycle_focus(notes_meta_totals),
        "weekday_hour_heatmaps": weekday_hour_heatmaps,
        "state_days": state_days,
        "state_totals": state_totals,
        "state_averages_per_day": state_averages,
        "state_ratios": state_ratios,
        "state_definitions": {
            "raw_events": "estimated pre-compression count from event collapsed_count/collapsed_ids",
            "compressed_events": "post-compression events stored in state.json events[]",
            "junk_events": "events where low_signal=true",
            "compression_ratio": "compressed_events/raw_events (lower is more compressed)",
        },
        "daily": daily,
        "warning_days": warning_days,
        "warnings": warnings,
    }


def build_lifetime_costing_payload(
    *,
    lifetime_payload: dict[str, Any],
) -> dict[str, Any]:
    daily_rows = lifetime_payload.get("daily") if isinstance(lifetime_payload.get("daily"), list) else []
    profiles = [dict(profile) for profile in INDICATIVE_COST_PROFILES]
    totals = {
        "chat_messages": 0,
        "chat_tokens_est": 0,
        "chat_input_tokens_est": 0,
        "chat_output_tokens_est": 0,
        "chat_context_overflow_threads": 0,
        "chat_context_overflow_tokens": 0,
    }
    profile_totals = {str(profile.get("id")): 0.0 for profile in profiles}
    output_daily: list[dict[str, Any]] = []

    for row in daily_rows:
        if not isinstance(row, dict):
            continue
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        chat_messages = _safe_int(summary.get("chat_messages"))
        chat_tokens_est = _safe_int(summary.get("chat_tokens_est"))
        chat_input_tokens_est = _safe_int(summary.get("chat_input_tokens_est"))
        chat_output_tokens_est = _safe_int(summary.get("chat_output_tokens_est"))
        overflow_threads = _safe_int(summary.get("chat_context_overflow_threads"))
        overflow_tokens = _safe_int(summary.get("chat_context_overflow_tokens"))

        totals["chat_messages"] += chat_messages
        totals["chat_tokens_est"] += chat_tokens_est
        totals["chat_input_tokens_est"] += chat_input_tokens_est
        totals["chat_output_tokens_est"] += chat_output_tokens_est
        totals["chat_context_overflow_threads"] += overflow_threads
        totals["chat_context_overflow_tokens"] += overflow_tokens

        profile_costs: dict[str, float] = {}
        for profile in profiles:
            profile_id = str(profile.get("id") or "")
            cost_est = _estimate_cost_usd(
                input_tokens=chat_input_tokens_est,
                output_tokens=chat_output_tokens_est,
                input_usd_per_mtok=_safe_float(profile.get("input_usd_per_mtok")),
                output_usd_per_mtok=_safe_float(profile.get("output_usd_per_mtok")),
            )
            profile_costs[profile_id] = cost_est
            profile_totals[profile_id] = round(_safe_float(profile_totals.get(profile_id)) + cost_est, 4)

        output_daily.append(
            {
                "date": str(row.get("date") or ""),
                "chat_scope_mode": str(row.get("chat_scope_mode") or "scoped"),
                "chat_messages": chat_messages,
                "chat_tokens_est": chat_tokens_est,
                "chat_input_tokens_est": chat_input_tokens_est,
                "chat_output_tokens_est": chat_output_tokens_est,
                "chat_context_overflow_threads": overflow_threads,
                "chat_context_overflow_tokens": overflow_tokens,
                "costs_usd": profile_costs,
                "daily_html_path": str(row.get("daily_html_path") or ""),
            }
        )

    warnings = lifetime_payload.get("warnings") if isinstance(lifetime_payload.get("warnings"), list) else []
    warnings_out = [str(item) for item in warnings]
    warnings_out.extend(
        [
            "Indicative costing only; char-based token estimation may differ from provider billing.",
            "Provider rates in this page are scenario presets, not live/API-queried prices.",
            "Planned upgrade: ingest provider billing logs (including historical Claude spend incidents) for estimate-vs-actual calibration.",
        ]
    )

    return {
        "period_start": str(lifetime_payload.get("period_start") or ""),
        "period_end": str(lifetime_payload.get("period_end") or ""),
        "days": _safe_int(lifetime_payload.get("days")),
        "generated_at": str(lifetime_payload.get("generated_at") or _iso_utc(datetime.now(UTC))),
        "chat_scope_mode": str(lifetime_payload.get("chat_scope_mode") or "scoped"),
        "token_estimation": {
            "chars_per_token": TOKEN_EST_CHARS_PER_TOKEN,
            "method": "max(1, round(chars/4.0)) when chars > 0",
        },
        "profiles": profiles,
        "totals": totals,
        "profile_cost_totals_usd": profile_totals,
        "daily": output_daily,
        "warnings": warnings_out,
        "positioning_note": (
            "Objective: reduce unnecessary token spend via orchestration/state coordination and better context handling, "
            "even without increases in base model skill."
        ),
    }


def render_weekly_dashboard_html(payload: dict[str, Any], html_path: Path) -> str:
    totals = payload.get("totals") or {}
    averages = payload.get("averages_per_day") or {}
    context_averages = payload.get("chat_context_averages") or {}
    agent_edit_averages = payload.get("agent_edit_averages") or {}
    media_averages = payload.get("media_averages") or {}
    notes_totals = payload.get("notes_meta_totals") or {}
    notes_averages = payload.get("notes_meta_averages_per_day") or {}
    notes_lifecycle = payload.get("notebooklm_lifecycle_totals") or {}
    notebook_lifecycle = notes_lifecycle.get("notebook") if isinstance(notes_lifecycle.get("notebook"), dict) else {}
    file_lifecycle = notes_lifecycle.get("file") if isinstance(notes_lifecycle.get("file"), dict) else {}
    rows = payload.get("daily") or []
    warnings = payload.get("warnings") or []
    heatmaps = payload.get("weekday_hour_heatmaps") if isinstance(payload.get("weekday_hour_heatmaps"), dict) else {}
    interactive = _render_signal_heatmap_interactive(heatmaps=heatmaps, dom_id_prefix="weekly") if heatmaps else ""

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
            f"<td>{(_safe_float(summary.get('context_switch_rate')) * 100.0):.1f}%</td>"
            f"<td>{_safe_float(summary.get('switches_per_active_hour')):.2f}</td>"
            f"<td>{_safe_float(summary.get('messages_per_chat')):.2f}</td>"
            f"<td>{(_safe_float(summary.get('top_thread_share')) * 100.0):.1f}%</td>"
            f"<td>{_safe_int(summary.get('shell_commands'))}</td>"
            f"<td>{_safe_int(summary.get('agent_edit_blocks'))}</td>"
            f"<td>{_safe_int(summary.get('agent_edit_files'))}</td>"
            f"<td>+{_safe_int(summary.get('agent_edit_lines_added'))} / -{_safe_int(summary.get('agent_edit_lines_removed'))}</td>"
            f"<td>{(_safe_float(summary.get('agent_edit_top_file_share')) * 100.0):.1f}%</td>"
            f"<td>{_safe_int(summary.get('media_events'))}</td>"
            f"<td>{_safe_int(summary.get('media_items_observed'))}</td>"
            f"<td>{_safe_int(summary.get('media_consumed_seconds')) / 3600.0:.2f}</td>"
            f"<td>{(_safe_float(summary.get('media_churn_rate')) * 100.0):.1f}%</td>"
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
    .table-scroll {{ max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    .table-scroll table {{ width: max-content; min-width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 0.35rem; vertical-align: top; }}
    code {{ background: #edf2f4; border-radius: 4px; padding: 0.05rem 0.2rem; }}
    .filter-grid {{ display: grid; gap: 0.65rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin-top: 0.45rem; }}
    .filter-block {{ border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem; background: #fbfcfb; }}
    .filter-options {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.35rem; }}
    .filter-options label {{ display: inline-flex; align-items: center; gap: 0.2rem; border: 1px solid var(--line); border-radius: 999px; padding: 0.1rem 0.45rem; background: #f7faf7; font-size: 0.86rem; }}
    .wf-controls {{ display: flex; gap: 0.6rem; flex-wrap: wrap; align-items: center; }}
    .wf-controls label {{ font-size: 0.9rem; color: #334155; display: inline-flex; align-items: center; gap: 0.35rem; }}
    .wf-controls button {{ border: 1px solid var(--line); border-radius: 6px; background: #f5f7f4; padding: 0.28rem 0.55rem; cursor: pointer; }}
    .rollup-grid {{ display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .rollup ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 0.3rem; }}
    .rollup li {{ display: grid; grid-template-columns: 3.1rem 1fr 5.6rem; align-items: center; gap: 0.4rem; }}
    .bar-wrap {{ border: 1px solid var(--line); border-radius: 7px; overflow: hidden; height: 0.7rem; }}
    .bar {{ height: 100%; background: #216e39; }}
    .bar.work {{ background: #216e39; }}
    .bar.git {{ background: #2f6f3e; }}
    .hm-wrap {{ overflow-x: auto; padding-bottom: 0.2rem; }}
    .hm-grid {{ display: grid; grid-template-columns: 2.6rem repeat(24, 0.62rem); gap: 0.2rem; align-items: center; width: max-content; }}
    .hm-corner {{ width: 2.6rem; height: 0.9rem; }}
    .hm-hour {{ font-size: 0.62rem; color: #475569; text-align: center; height: 0.9rem; line-height: 0.9rem; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .hm-hour-muted {{ color: transparent; }}
    .hm-dow {{ font-size: 0.72rem; color: #334155; text-align: right; padding-right: 0.15rem; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .hm-cell {{ width: 0.62rem; height: 0.62rem; border-radius: 2px; border: 1px solid rgba(15, 23, 42, 0.10); background: #ebedf0; }}
    .hm-cell.l0 {{ background: #ebedf0; }}
    .hm-cell.l1 {{ background: #9be9a8; }}
    .hm-cell.l2 {{ background: #40c463; }}
    .hm-cell.l3 {{ background: #30a14e; }}
    .hm-cell.l4 {{ background: #216e39; }}
    .hm-legend {{ display: flex; align-items: center; gap: 0.25rem; justify-content: flex-end; margin-top: 0.45rem; color: #475569; font-size: 0.78rem; }}
    .hm-sq {{ width: 0.62rem; height: 0.62rem; border-radius: 2px; border: 1px solid rgba(15, 23, 42, 0.10); display: inline-block; }}
    .hm-sq.l0 {{ background: #ebedf0; }}
    .hm-sq.l1 {{ background: #9be9a8; }}
    .hm-sq.l2 {{ background: #40c463; }}
    .hm-sq.l3 {{ background: #30a14e; }}
    .hm-sq.l4 {{ background: #216e39; }}
    .hm-note {{ margin-top: 0.35rem; }}
    @media (max-width: 760px) {{ table {{ font-size: 0.82rem; }} }}
  </style>
</head>
<body>
  <div class="role-topbar">
    <div class="role-topbar-inner">
      <b>View</b>
      <button class="role-tab" type="button" data-role="StatiBaker" aria-pressed="true">StatiBaker</button>
      <button class="role-tab" type="button" data-role="TiRC (transcript and recording)" aria-pressed="false">TiRC (transcript and recording)</button>
      <button class="role-tab" type="button" data-role="Fuzzymodo" aria-pressed="false">Fuzzymodo</button>
      <button class="role-tab" type="button" data-role="casey-git-clone" aria-pressed="false">casey-git-clone</button>
      <button class="role-tab" type="button" data-role="SensibLaw" aria-pressed="false">SensibLaw</button>
      <button class="role-tab" type="button" data-role="All" aria-pressed="false">All</button>
      <span class="role-topbar-spacer"></span>
      <a class="role-topbar-link" href="#" id="role-show-all">Show all sections</a>
    </div>
  </div>
  <main>
    <section class="panel" data-role="StatiBaker">
      <h1>SB Weekly Dashboard</h1>
      <p>
        <b>Window:</b> <code>{escape(str(payload.get("period_start", "")))}</code> to
        <code>{escape(str(payload.get("period_end", "")))}</code> |
        <b>Days:</b> <code>{escape(str(payload.get("days", 0)))}</code> |
        <b>Chat scope:</b> <code>{escape(str(payload.get("chat_scope_mode", "scoped")))}</code>
      </p>
    </section>
    {interactive}
    <section class="panel" data-role="StatiBaker">
      <h2>Totals</h2>
      <div class="grid">
        <div class="metric">Chat messages<b>{_safe_int(totals.get("chat_messages"))}</b></div>
        <div class="metric">Chat threads<b>{_safe_int(totals.get("chat_threads"))}</b></div>
        <div class="metric">Chat switches<b>{_safe_int(totals.get("chat_switches"))}</b></div>
        <div class="metric">Shell commands<b>{_safe_int(totals.get("shell_commands"))}</b></div>
        <div class="metric">Agent edit blocks<b>{_safe_int(totals.get("agent_edit_blocks"))}</b></div>
        <div class="metric">Agent files touched<b>{_safe_int(totals.get("agent_edit_files"))}</b></div>
        <div class="metric">Agent line deltas<b>+{_safe_int(totals.get("agent_edit_lines_added"))} / -{_safe_int(totals.get("agent_edit_lines_removed"))}</b></div>
        <div class="metric">Media events<b>{_safe_int(totals.get("media_events"))}</b></div>
        <div class="metric">Media items observed<b>{_safe_int(totals.get("media_items_observed"))}</b></div>
        <div class="metric">Media consumed<b>{_safe_int(totals.get("media_consumed_seconds")) / 3600.0:.2f} h</b></div>
        <div class="metric">Media completion/churn<b>{(_ratio(_safe_int(totals.get("media_consumed_seconds")), _safe_int(totals.get("media_content_seconds")), digits=3) * 100.0):.1f}% / {(_ratio(_safe_int(totals.get("media_churn_events")), _safe_int(totals.get("media_items_observed")), digits=3) * 100.0):.1f}%</b></div>
        <div class="metric">iNaturalist events<b>{_safe_int(totals.get("inaturalist_events"))}</b></div>
        <div class="metric">iNaturalist insects<b>{_safe_int(totals.get("inaturalist_insect_observations"))}</b></div>
        <div class="metric">Mood reports<b>{_safe_int(totals.get("mood_reports"))}</b></div>
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
        switch_rate=<code>{(_safe_float(context_averages.get("context_switch_rate")) * 100.0):.1f}%</code>,
        switches/hour=<code>{_safe_float(context_averages.get("switches_per_active_hour")):.2f}</code>,
        messages/chat=<code>{_safe_float(context_averages.get("messages_per_chat")):.2f}</code>,
        top-thread-share=<code>{(_safe_float(context_averages.get("top_thread_share")) * 100.0):.1f}%</code>,
        agent-top-file-share=<code>{(_safe_float(agent_edit_averages.get("top_file_share")) * 100.0):.1f}%</code>,
        agent-edits/file=<code>{_safe_float(agent_edit_averages.get("edits_per_file")):.2f}</code>,
        media-completion=<code>{(_safe_float(media_averages.get("completion_ratio")) * 100.0):.1f}%</code>,
        media-churn=<code>{(_safe_float(media_averages.get("churn_rate")) * 100.0):.1f}%</code>,
        shell=<code>{escape(str(averages.get("shell_commands", 0)))}</code>,
        commits=<code>{escape(str(averages.get("git_commits", 0)))}</code>,
        prs=<code>{escape(str(averages.get("pr_events", 0)))}</code>
      </p>
    </section>
    <section class="panel" data-role="TiRC (transcript and recording)">
      <h2>NotebookLM Lifecycle (Metadata)</h2>
      <div class="grid">
        <div class="metric">Notes meta events<b>{_safe_int(notes_totals.get("total_events"))}</b></div>
        <div class="metric">NotebookLM meta events<b>{_safe_int(notes_totals.get("notebooklm_events"))}</b></div>
        <div class="metric">Notebooks created/modified/moved/deleted/seen<b>{_safe_int(notebook_lifecycle.get("created"))}/{_safe_int(notebook_lifecycle.get("modified"))}/{_safe_int(notebook_lifecycle.get("moved"))}/{_safe_int(notebook_lifecycle.get("deleted"))}/{_safe_int(notebook_lifecycle.get("seen"))}</b></div>
        <div class="metric">Files created/modified/moved/deleted/seen<b>{_safe_int(file_lifecycle.get("created"))}/{_safe_int(file_lifecycle.get("modified"))}/{_safe_int(file_lifecycle.get("moved"))}/{_safe_int(file_lifecycle.get("deleted"))}/{_safe_int(file_lifecycle.get("seen"))}</b></div>
      </div>
      <p>
        <b>Daily averages:</b>
        notes_meta=<code>{escape(str(notes_averages.get("total_events", 0)))}</code>,
        notebooklm=<code>{escape(str(notes_averages.get("notebooklm_events", 0)))}</code>
      </p>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Per-Day Summary</h2>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Date</th><th>Chat Source</th><th>Scope</th><th>Chat Msg</th><th>Chat Threads</th><th>Switches</th><th>Switch Rate</th><th>Switch/hr</th><th>Msg/chat</th><th>Top Thread</th><th>Shell</th><th>Agent blocks</th><th>Agent files</th><th>Agent delta</th><th>Agent top file</th><th>Media evt</th><th>Media items</th><th>Media h</th><th>Media churn</th><th>Commits</th><th>Branch</th><th>PR</th><th>Warnings</th><th>Daily</th></tr></thead>
          <tbody>{"".join(day_rows) if day_rows else "<tr><td colspan='24'>No days found.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Warnings</h2>
      <ul>{warning_rows if warning_rows else "<li>None</li>"}</ul>
    </section>
  </main>
  <script>
    (() => {{
      const ROLE_KEY = "sb_dashboard_role_tab";
      const tabs = Array.from(document.querySelectorAll(".role-tab[data-role]"));
      const panels = Array.from(document.querySelectorAll("section.panel[data-role]"));
      if (!tabs.length || !panels.length) return;

      const setRole = (role) => {{
        const chosen = String(role || "StatiBaker");
        try {{ localStorage.setItem(ROLE_KEY, chosen); }} catch (_) {{}}
        tabs.forEach((btn) => {{
          const pressed = (btn.dataset.role || "") === chosen;
          btn.setAttribute("aria-pressed", pressed ? "true" : "false");
        }});
        panels.forEach((panel) => {{
          const panelRole = panel.dataset.role || "";
          panel.style.display = (chosen === "All" || panelRole === chosen) ? "" : "none";
        }});
      }};

      tabs.forEach((btn) => {{
        btn.addEventListener("click", () => setRole(btn.dataset.role || "StatiBaker"));
      }});

      const showAllLink = document.getElementById("role-show-all");
      if (showAllLink) {{
        showAllLink.addEventListener("click", (evt) => {{
          evt.preventDefault();
          setRole("All");
        }});
      }}

      let initial = "StatiBaker";
      try {{ initial = localStorage.getItem(ROLE_KEY) || initial; }} catch (_) {{}}
      if (!tabs.some((b) => (b.dataset.role || "") === initial)) initial = "StatiBaker";
      setRole(initial);
    }})();
  </script>
</body>
</html>
"""


def render_lifetime_dashboard_html(payload: dict[str, Any], html_path: Path) -> str:
    totals = payload.get("totals") or {}
    averages = payload.get("averages_per_day") or {}
    context_averages = payload.get("chat_context_averages") or {}
    agent_edit_averages = payload.get("agent_edit_averages") or {}
    media_averages = payload.get("media_averages") or {}
    notes_totals = payload.get("notes_meta_totals") or {}
    notes_averages = payload.get("notes_meta_averages_per_day") or {}
    notes_lifecycle = payload.get("notebooklm_lifecycle_totals") or {}
    notebook_lifecycle = notes_lifecycle.get("notebook") if isinstance(notes_lifecycle.get("notebook"), dict) else {}
    file_lifecycle = notes_lifecycle.get("file") if isinstance(notes_lifecycle.get("file"), dict) else {}
    state_totals = payload.get("state_totals") or {}
    state_averages = payload.get("state_averages_per_day") or {}
    state_ratios = payload.get("state_ratios") or {}
    rows = payload.get("daily") or []
    warnings = payload.get("warnings") or []
    definitions = payload.get("state_definitions") or {}
    heatmaps = payload.get("weekday_hour_heatmaps") if isinstance(payload.get("weekday_hour_heatmaps"), dict) else {}
    interactive = _render_signal_heatmap_interactive(heatmaps=heatmaps, dom_id_prefix="lifetime") if heatmaps else ""

    day_rows: list[str] = []
    for row in rows:
        summary = row.get("summary") or {}
        state_volume = row.get("state_volume") or {}
        html_target = str(row.get("daily_html_path") or "")
        day_rows.append(
            "<tr>"
            f"<td><code>{escape(str(row.get('date') or ''))}</code></td>"
            f"<td>{escape(str(row.get('chat_source') or 'none'))}</td>"
            f"<td>{escape(str(row.get('chat_scope_mode') or 'scoped'))}</td>"
            f"<td>{_safe_int(summary.get('chat_messages'))}</td>"
            f"<td>{_safe_int(summary.get('chat_threads'))}</td>"
            f"<td>{_safe_int(summary.get('chat_switches'))}</td>"
            f"<td>{(_safe_float(summary.get('context_switch_rate')) * 100.0):.1f}%</td>"
            f"<td>{_safe_float(summary.get('switches_per_active_hour')):.2f}</td>"
            f"<td>{_safe_float(summary.get('messages_per_chat')):.2f}</td>"
            f"<td>{(_safe_float(summary.get('top_thread_share')) * 100.0):.1f}%</td>"
            f"<td>{_safe_int(summary.get('agent_edit_blocks'))}</td>"
            f"<td>{_safe_int(summary.get('agent_edit_files'))}</td>"
            f"<td>+{_safe_int(summary.get('agent_edit_lines_added'))} / -{_safe_int(summary.get('agent_edit_lines_removed'))}</td>"
            f"<td>{(_safe_float(summary.get('agent_edit_top_file_share')) * 100.0):.1f}%</td>"
            f"<td>{_safe_int(summary.get('media_events'))}</td>"
            f"<td>{_safe_int(summary.get('media_items_observed'))}</td>"
            f"<td>{_safe_int(summary.get('media_consumed_seconds')) / 3600.0:.2f}</td>"
            f"<td>{(_safe_float(summary.get('media_churn_rate')) * 100.0):.1f}%</td>"
            f"<td>{_safe_int(state_volume.get('raw_events'))}</td>"
            f"<td>{_safe_int(state_volume.get('junk_events_raw'))}</td>"
            f"<td>{_safe_int(state_volume.get('compressed_events'))}</td>"
            f"<td>{(_safe_float(state_volume.get('compression_ratio')) * 100.0):.1f}%</td>"
            f"<td>{_safe_int(state_volume.get('state_json_bytes')) / 1024.0:.1f}</td>"
            f"<td>{_safe_int(row.get('warning_count'))}</td>"
            f"<td><a href='{escape(_rel_href(html_target, html_path))}'>daily</a></td>"
            "</tr>"
        )

    warning_rows = "\n".join(f"<li>{escape(str(item))}</li>" for item in warnings)
    definition_rows = "\n".join(
        f"<li><b>{escape(str(key))}</b>: {escape(str(value))}</li>"
        for key, value in definitions.items()
    )
    costing_name = "dashboard_costing_all.html" if html_path.name.endswith("_all.html") else "dashboard_costing.html"
    costing_href = _rel_href(str(html_path.parent / costing_name), html_path)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SB Lifetime Dashboard {escape(str(payload.get("period_start", "")))} to {escape(str(payload.get("period_end", "")))}</title>
  <style>
    :root {{
      --bg: #f4f8f7;
      --ink: #17222a;
      --panel: #ffffff;
      --line: #d7e1e7;
    }}
    body {{ margin: 0; background: linear-gradient(170deg, #eaf2f6, var(--bg)); color: var(--ink); font-family: "IBM Plex Sans", "Segoe UI", sans-serif; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 1.2rem; display: grid; gap: 1rem; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 0.9rem; }}
    .grid {{ display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }}
    .metric {{ border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem; }}
    .metric b {{ display:block; font-size: 1.25rem; margin-top: 0.2rem; }}
    h1,h2 {{ margin: 0 0 0.6rem 0; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .table-scroll table {{ width: max-content; min-width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 0.35rem; vertical-align: top; }}
    code {{ background: #edf2f4; border-radius: 4px; padding: 0.05rem 0.2rem; }}
    .table-scroll {{ overflow-x: auto; }}
    .role-topbar {{ position: sticky; top: 0; z-index: 50; background: rgba(244, 248, 247, 0.88); backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }}
    .role-topbar-inner {{ max-width: 1280px; margin: 0 auto; padding: 0.55rem 1.2rem; box-sizing: border-box; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }}
    .role-topbar b {{ font-family: "IBM Plex Mono", "Consolas", monospace; font-size: 0.82rem; color: #334155; margin-right: 0.25rem; }}
    .role-tab {{ border: 1px solid var(--line); border-radius: 999px; background: #ffffff; padding: 0.25rem 0.55rem; cursor: pointer; font: inherit; font-size: 0.88rem; }}
    .role-tab[aria-pressed="true"] {{ background: #eaf2f6; border-color: #adc3f4; color: #1d4ed8; }}
    .role-topbar-spacer {{ flex: 1 1 auto; }}
    .role-topbar-link {{ font-size: 0.86rem; color: #1d4ed8; text-decoration: none; border-bottom: 1px dashed rgba(29, 78, 216, 0.45); }}
    .role-topbar-link:hover {{ border-bottom-style: solid; }}
    @media (max-width: 760px) {{ table {{ font-size: 0.82rem; }} }}
    .filter-grid {{ display: grid; gap: 0.65rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin-top: 0.45rem; }}
    .filter-block {{ border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem; background: #fbfcfb; }}
    .filter-options {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.35rem; }}
    .filter-options label {{ display: inline-flex; align-items: center; gap: 0.2rem; border: 1px solid var(--line); border-radius: 999px; padding: 0.1rem 0.45rem; background: #f7faf7; font-size: 0.86rem; }}
    .wf-controls {{ display: flex; gap: 0.6rem; flex-wrap: wrap; align-items: center; }}
    .wf-controls label {{ font-size: 0.9rem; color: #334155; display: inline-flex; align-items: center; gap: 0.35rem; }}
    .wf-controls button {{ border: 1px solid var(--line); border-radius: 6px; background: #f5f7f4; padding: 0.28rem 0.55rem; cursor: pointer; }}
    .rollup-grid {{ display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .rollup ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 0.3rem; }}
    .rollup li {{ display: grid; grid-template-columns: 3.1rem 1fr 5.6rem; align-items: center; gap: 0.4rem; }}
    .bar-wrap {{ border: 1px solid var(--line); border-radius: 7px; overflow: hidden; height: 0.7rem; }}
    .bar {{ height: 100%; background: #216e39; }}
    .bar.work {{ background: #216e39; }}
    .bar.git {{ background: #2f6f3e; }}
    .hm-wrap {{ overflow-x: auto; padding-bottom: 0.2rem; }}
    .hm-grid {{ display: grid; grid-template-columns: 2.6rem repeat(24, 0.62rem); gap: 0.2rem; align-items: center; width: max-content; }}
    .hm-corner {{ width: 2.6rem; height: 0.9rem; }}
    .hm-hour {{ font-size: 0.62rem; color: #475569; text-align: center; height: 0.9rem; line-height: 0.9rem; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .hm-hour-muted {{ color: transparent; }}
    .hm-dow {{ font-size: 0.72rem; color: #334155; text-align: right; padding-right: 0.15rem; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .hm-cell {{ width: 0.62rem; height: 0.62rem; border-radius: 2px; border: 1px solid rgba(15, 23, 42, 0.10); background: #ebedf0; }}
    .hm-cell.l0 {{ background: #ebedf0; }}
    .hm-cell.l1 {{ background: #9be9a8; }}
    .hm-cell.l2 {{ background: #40c463; }}
    .hm-cell.l3 {{ background: #30a14e; }}
    .hm-cell.l4 {{ background: #216e39; }}
    .hm-legend {{ display: flex; align-items: center; gap: 0.25rem; justify-content: flex-end; margin-top: 0.45rem; color: #475569; font-size: 0.78rem; }}
    .hm-sq {{ width: 0.62rem; height: 0.62rem; border-radius: 2px; border: 1px solid rgba(15, 23, 42, 0.10); display: inline-block; }}
    .hm-sq.l0 {{ background: #ebedf0; }}
    .hm-sq.l1 {{ background: #9be9a8; }}
    .hm-sq.l2 {{ background: #40c463; }}
    .hm-sq.l3 {{ background: #30a14e; }}
    .hm-sq.l4 {{ background: #216e39; }}
    .hm-note {{ margin-top: 0.35rem; }}
  </style>
</head>
<body>
  <div class="role-topbar">
    <div class="role-topbar-inner">
      <b>View</b>
      <button class="role-tab" type="button" data-role="StatiBaker" aria-pressed="true">StatiBaker</button>
      <button class="role-tab" type="button" data-role="TiRC (transcript and recording)" aria-pressed="false">TiRC (transcript and recording)</button>
      <button class="role-tab" type="button" data-role="Fuzzymodo" aria-pressed="false">Fuzzymodo</button>
      <button class="role-tab" type="button" data-role="casey-git-clone" aria-pressed="false">casey-git-clone</button>
      <button class="role-tab" type="button" data-role="SensibLaw" aria-pressed="false">SensibLaw</button>
      <button class="role-tab" type="button" data-role="All" aria-pressed="false">All</button>
      <span class="role-topbar-spacer"></span>
      <a class="role-topbar-link" href="#" id="role-show-all">Show all sections</a>
    </div>
  </div>
  <main>
    <section class="panel" data-role="StatiBaker">
      <h1>SB Lifetime Dashboard</h1>
      <p>
        <b>Window:</b> <code>{escape(str(payload.get("period_start", "")))}</code> to
        <code>{escape(str(payload.get("period_end", "")))}</code> |
        <b>Days:</b> <code>{escape(str(payload.get("days", 0)))}</code> |
        <b>State days:</b> <code>{escape(str(payload.get("state_days", 0)))}</code> |
        <b>Chat scope:</b> <code>{escape(str(payload.get("chat_scope_mode", "scoped")))}</code>
      </p>
      <p><small>Indicative API costing companion: <a href='{escape(costing_href)}'>{escape(costing_name)}</a></small></p>
    </section>
    {interactive}
    <section class="panel" data-role="StatiBaker">
      <h2>State Volume</h2>
      <div class="grid">
        <div class="metric">Ingested events (raw est)<b>{_safe_int(state_totals.get("raw_events"))}</b></div>
        <div class="metric">Junk events (raw est)<b>{_safe_int(state_totals.get("junk_events_raw"))}</b><small>{(_safe_float(state_ratios.get("junk_share_raw")) * 100.0):.1f}% raw</small></div>
        <div class="metric">Stored events (compressed)<b>{_safe_int(state_totals.get("compressed_events"))}</b></div>
        <div class="metric">Junk events (compressed)<b>{_safe_int(state_totals.get("junk_events_compressed"))}</b><small>{(_safe_float(state_ratios.get("junk_share_compressed")) * 100.0):.1f}% compressed</small></div>
        <div class="metric">Compression ratio<b>{(_safe_float(state_ratios.get("compression_ratio")) * 100.0):.1f}%</b><small>compressed/raw</small></div>
        <div class="metric">Expansion ratio<b>{_safe_float(state_ratios.get("expansion_ratio")):.2f}x</b><small>raw/compressed</small></div>
        <div class="metric">state.json size<b>{_safe_int(state_totals.get("state_json_bytes")) / (1024.0 * 1024.0):.2f} MiB</b></div>
      </div>
      <p>
        <b>Per-state-day averages:</b>
        raw=<code>{escape(str(state_averages.get("raw_events", 0)))}</code>,
        junk(raw)=<code>{escape(str(state_averages.get("junk_events_raw", 0)))}</code>,
        compressed=<code>{escape(str(state_averages.get("compressed_events", 0)))}</code>,
        state bytes=<code>{escape(str(state_averages.get("state_json_bytes", 0)))}</code>
      </p>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Activity Totals</h2>
      <div class="grid">
        <div class="metric">Chat messages<b>{_safe_int(totals.get("chat_messages"))}</b></div>
        <div class="metric">Chat threads<b>{_safe_int(totals.get("chat_threads"))}</b></div>
        <div class="metric">Chat switches<b>{_safe_int(totals.get("chat_switches"))}</b></div>
        <div class="metric">Shell commands<b>{_safe_int(totals.get("shell_commands"))}</b></div>
        <div class="metric">Agent edit blocks<b>{_safe_int(totals.get("agent_edit_blocks"))}</b></div>
        <div class="metric">Agent files touched<b>{_safe_int(totals.get("agent_edit_files"))}</b></div>
        <div class="metric">Agent line deltas<b>+{_safe_int(totals.get("agent_edit_lines_added"))} / -{_safe_int(totals.get("agent_edit_lines_removed"))}</b></div>
        <div class="metric">Media events<b>{_safe_int(totals.get("media_events"))}</b></div>
        <div class="metric">Media items observed<b>{_safe_int(totals.get("media_items_observed"))}</b></div>
        <div class="metric">Media consumed<b>{_safe_int(totals.get("media_consumed_seconds")) / 3600.0:.2f} h</b></div>
        <div class="metric">Media completion/churn<b>{(_ratio(_safe_int(totals.get("media_consumed_seconds")), _safe_int(totals.get("media_content_seconds")), digits=3) * 100.0):.1f}% / {(_ratio(_safe_int(totals.get("media_churn_events")), _safe_int(totals.get("media_items_observed")), digits=3) * 100.0):.1f}%</b></div>
        <div class="metric">iNaturalist events<b>{_safe_int(totals.get("inaturalist_events"))}</b></div>
        <div class="metric">iNaturalist insects<b>{_safe_int(totals.get("inaturalist_insect_observations"))}</b></div>
        <div class="metric">Mood reports<b>{_safe_int(totals.get("mood_reports"))}</b></div>
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
        switch_rate=<code>{(_safe_float(context_averages.get("context_switch_rate")) * 100.0):.1f}%</code>,
        switches/hour=<code>{_safe_float(context_averages.get("switches_per_active_hour")):.2f}</code>,
        messages/chat=<code>{_safe_float(context_averages.get("messages_per_chat")):.2f}</code>,
        top-thread-share=<code>{(_safe_float(context_averages.get("top_thread_share")) * 100.0):.1f}%</code>,
        agent-top-file-share=<code>{(_safe_float(agent_edit_averages.get("top_file_share")) * 100.0):.1f}%</code>,
        agent-edits/file=<code>{_safe_float(agent_edit_averages.get("edits_per_file")):.2f}</code>,
        media-completion=<code>{(_safe_float(media_averages.get("completion_ratio")) * 100.0):.1f}%</code>,
        media-churn=<code>{(_safe_float(media_averages.get("churn_rate")) * 100.0):.1f}%</code>
      </p>
    </section>
    <section class="panel" data-role="TiRC (transcript and recording)">
      <h2>NotebookLM Lifecycle (Metadata)</h2>
      <div class="grid">
        <div class="metric">Notes meta events<b>{_safe_int(notes_totals.get("total_events"))}</b></div>
        <div class="metric">NotebookLM meta events<b>{_safe_int(notes_totals.get("notebooklm_events"))}</b></div>
        <div class="metric">Notebooks created/modified/moved/deleted/seen<b>{_safe_int(notebook_lifecycle.get("created"))}/{_safe_int(notebook_lifecycle.get("modified"))}/{_safe_int(notebook_lifecycle.get("moved"))}/{_safe_int(notebook_lifecycle.get("deleted"))}/{_safe_int(notebook_lifecycle.get("seen"))}</b></div>
        <div class="metric">Files created/modified/moved/deleted/seen<b>{_safe_int(file_lifecycle.get("created"))}/{_safe_int(file_lifecycle.get("modified"))}/{_safe_int(file_lifecycle.get("moved"))}/{_safe_int(file_lifecycle.get("deleted"))}/{_safe_int(file_lifecycle.get("seen"))}</b></div>
      </div>
      <p>
        <b>Daily averages:</b>
        notes_meta=<code>{escape(str(notes_averages.get("total_events", 0)))}</code>,
        notebooklm=<code>{escape(str(notes_averages.get("notebooklm_events", 0)))}</code>
      </p>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Per-Day Summary</h2>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Date</th><th>Chat Source</th><th>Scope</th><th>Chat Msg</th><th>Chat Threads</th><th>Switches</th><th>Switch Rate</th><th>Switch/hr</th><th>Msg/chat</th><th>Top Thread</th><th>Agent blocks</th><th>Agent files</th><th>Agent delta</th><th>Agent top file</th><th>Media evt</th><th>Media items</th><th>Media h</th><th>Media churn</th><th>Raw events</th><th>Junk(raw)</th><th>Compressed</th><th>Compr ratio</th><th>State KiB</th><th>Warnings</th><th>Daily</th></tr></thead>
          <tbody>{"".join(day_rows) if day_rows else "<tr><td colspan='25'>No days found.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Definitions</h2>
      <ul>{definition_rows if definition_rows else "<li>None</li>"}</ul>
    </section>
    <section class="panel" data-role="StatiBaker">
      <h2>Warnings</h2>
      <ul>{warning_rows if warning_rows else "<li>None</li>"}</ul>
    </section>
  </main>
  <script>
    (() => {{
      const ROLE_KEY = "sb_dashboard_role_tab";
      const tabs = Array.from(document.querySelectorAll(".role-tab[data-role]"));
      const panels = Array.from(document.querySelectorAll("section.panel[data-role]"));
      if (!tabs.length || !panels.length) return;

      const setRole = (role) => {{
        const chosen = String(role || "StatiBaker");
        try {{ localStorage.setItem(ROLE_KEY, chosen); }} catch (_) {{}}
        tabs.forEach((btn) => {{
          const pressed = (btn.dataset.role || "") === chosen;
          btn.setAttribute("aria-pressed", pressed ? "true" : "false");
        }});
        panels.forEach((panel) => {{
          const panelRole = panel.dataset.role || "";
          panel.style.display = (chosen === "All" || panelRole === chosen) ? "" : "none";
        }});
      }};

      tabs.forEach((btn) => {{
        btn.addEventListener("click", () => setRole(btn.dataset.role || "StatiBaker"));
      }});

      const showAllLink = document.getElementById("role-show-all");
      if (showAllLink) {{
        showAllLink.addEventListener("click", (evt) => {{
          evt.preventDefault();
          setRole("All");
        }});
      }}

      let initial = "StatiBaker";
      try {{ initial = localStorage.getItem(ROLE_KEY) || initial; }} catch (_) {{}}
      if (!tabs.some((b) => (b.dataset.role || "") === initial)) initial = "StatiBaker";
      setRole(initial);
    }})();
  </script>
</body>
</html>
"""


def render_costing_dashboard_html(payload: dict[str, Any], html_path: Path) -> str:
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), list) else []
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    rows = payload.get("daily") if isinstance(payload.get("daily"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    profile_cost_totals = payload.get("profile_cost_totals_usd") if isinstance(payload.get("profile_cost_totals_usd"), dict) else {}
    positioning_note = str(payload.get("positioning_note") or "")

    profile_cards = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("id") or "")
        label = str(profile.get("label") or profile_id)
        profile_cards.append(
            "<div class='metric'>"
            f"{escape(label)}<b>${_safe_float(profile_cost_totals.get(profile_id)):.2f}</b>"
            f"<small>input=${_safe_float(profile.get('input_usd_per_mtok')):.2f}/Mtok, output=${_safe_float(profile.get('output_usd_per_mtok')):.2f}/Mtok</small>"
            "</div>"
        )

    profile_headers = "".join(
        f"<th>{escape(str((profile if isinstance(profile, dict) else {}).get('label') or (profile if isinstance(profile, dict) else {}).get('id') or 'profile'))} (USD)</th>"
        for profile in profiles
        if isinstance(profile, dict)
    )
    day_rows: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        costs = row.get("costs_usd") if isinstance(row.get("costs_usd"), dict) else {}
        profile_cells = "".join(
            f"<td>${_safe_float(costs.get(str(profile.get('id') if isinstance(profile, dict) else ''))):.4f}</td>"
            for profile in profiles
            if isinstance(profile, dict)
        )
        html_target = str(row.get("daily_html_path") or "")
        day_rows.append(
            "<tr>"
            f"<td><code>{escape(str(row.get('date') or ''))}</code></td>"
            f"<td>{_safe_int(row.get('chat_messages'))}</td>"
            f"<td>{_safe_int(row.get('chat_tokens_est'))}</td>"
            f"<td>{_safe_int(row.get('chat_input_tokens_est'))}</td>"
            f"<td>{_safe_int(row.get('chat_output_tokens_est'))}</td>"
            f"<td>{_safe_int(row.get('chat_context_overflow_threads'))}</td>"
            f"<td>{_safe_int(row.get('chat_context_overflow_tokens'))}</td>"
            f"{profile_cells}"
            f"<td><a href='{escape(_rel_href(html_target, html_path))}'>daily</a></td>"
            "</tr>"
        )

    costing_colspan = 8 + len([profile for profile in profiles if isinstance(profile, dict)])
    warning_rows = "\n".join(f"<li>{escape(str(item))}</li>" for item in warnings)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SB Indicative API Costing {escape(str(payload.get("period_start", "")))} to {escape(str(payload.get("period_end", "")))}</title>
  <style>
    :root {{
      --bg: #f4f8f7;
      --ink: #17222a;
      --panel: #ffffff;
      --line: #d7e1e7;
    }}
    body {{ margin: 0; background: linear-gradient(170deg, #eaf2f6, var(--bg)); color: var(--ink); font-family: "IBM Plex Sans", "Segoe UI", sans-serif; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 1.2rem; display: grid; gap: 1rem; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 0.9rem; }}
    .grid {{ display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .metric {{ border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem; }}
    .metric b {{ display:block; font-size: 1.25rem; margin-top: 0.2rem; }}
    h1,h2 {{ margin: 0 0 0.6rem 0; font-family: "IBM Plex Mono", "Consolas", monospace; }}
    .table-scroll {{ overflow-x: auto; }}
    .table-scroll table {{ width: max-content; min-width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 0.35rem; vertical-align: top; }}
    code {{ background: #edf2f4; border-radius: 4px; padding: 0.05rem 0.2rem; }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>SB Indicative API Costing</h1>
      <p>
        <b>Window:</b> <code>{escape(str(payload.get("period_start", "")))}</code> to
        <code>{escape(str(payload.get("period_end", "")))}</code> |
        <b>Days:</b> <code>{escape(str(payload.get("days", 0)))}</code> |
        <b>Chat scope:</b> <code>{escape(str(payload.get("chat_scope_mode", "scoped")))}</code>
      </p>
      <p><small>Formula: <code>(input_tokens/1e6*input_rate) + (output_tokens/1e6*output_rate)</code>. Token estimate uses <code>max(1, round(chars/4.0))</code>.</small></p>
      <p><small>{escape(positioning_note)}</small></p>
    </section>
    <section class="panel">
      <h2>Token Totals (Estimated)</h2>
      <div class="grid">
        <div class="metric">Chat messages<b>{_safe_int(totals.get("chat_messages"))}</b></div>
        <div class="metric">Total tokens<b>{_safe_int(totals.get("chat_tokens_est"))}</b></div>
        <div class="metric">Input tokens<b>{_safe_int(totals.get("chat_input_tokens_est"))}</b></div>
        <div class="metric">Output tokens<b>{_safe_int(totals.get("chat_output_tokens_est"))}</b></div>
        <div class="metric">Overflow thread-days<b>{_safe_int(totals.get("chat_context_overflow_threads"))}</b></div>
        <div class="metric">Overflow tokens<b>{_safe_int(totals.get("chat_context_overflow_tokens"))}</b></div>
      </div>
    </section>
    <section class="panel">
      <h2>Scenario Cost Totals</h2>
      <div class="grid">{"".join(profile_cards) if profile_cards else "<div class='metric'>None</div>"}</div>
    </section>
    <section class="panel">
      <h2>Per-Day Indicative Cost</h2>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Date</th><th>Chat Msg</th><th>Tokens</th><th>Input</th><th>Output</th><th>Overflow threads</th><th>Overflow tokens</th>{profile_headers}<th>Daily</th></tr></thead>
          <tbody>{"".join(day_rows) if day_rows else f"<tr><td colspan='{costing_colspan}'>No days found.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
    <section class="panel" data-role="StatiBaker">
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


def write_lifetime_outputs(
    payload: dict[str, Any],
    *,
    json_path: Path,
    html_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    html_path.write_text(render_lifetime_dashboard_html(payload, html_path), encoding="utf-8")


def write_costing_outputs(
    payload: dict[str, Any],
    *,
    json_path: Path,
    html_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    html_path.write_text(render_costing_dashboard_html(payload, html_path), encoding="utf-8")
