from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

AO_CONTROL_STATUS_COLUMNS: dict[str, str] = {
    "queued": "Queued",
    "running": "Running",
    "needs_retry": "Needs Retry",
    "blocked_upstream": "Blocked Upstream",
    "validation_needed": "Validation Needed",
    "done": "Done",
    "skipped": "Skipped",
}

AO_CONTROL_SCHEMA_VERSION = "sb.ao_kanboard_control_surface.v0_1"


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _parse_utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _age_seconds(value: Any, now: datetime) -> int | None:
    parsed = _parse_utc(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds()))


def _duration_seconds(start: Any, end: Any, now: datetime) -> int | None:
    started = _parse_utc(start)
    if started is None:
        return None
    ended = _parse_utc(end) or now
    return max(0, int((ended - started).total_seconds()))


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    minutes, rem = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{rem:02d}s"
    return f"{rem}s"


def _completion_time(status: Mapping[str, Any], heartbeat: Mapping[str, Any]) -> str:
    for key in ("last_cycle_finished_at", "updated_at", "last_heartbeat"):
        value = _text(status.get(key) or heartbeat.get(key))
        if value:
            return value
    return ""


def _runsheet_items(status: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = _as_list(_as_dict(status.get("runsheet")).get("items"))
    return [dict(item) for item in items if isinstance(item, Mapping)]


def _has_blocked_item(items: list[Mapping[str, Any]]) -> bool:
    return any(_text(item.get("status")) == "blocked" for item in items)


def _has_pending_validation(items: list[Mapping[str, Any]]) -> bool:
    for item in items:
        item_id = _text(item.get("id") or item.get("title")).casefold()
        if "validation" not in item_id and "test" not in item_id:
            continue
        if _text(item.get("status")) not in {"done", "skipped"}:
            return True
    return False


def _progress(status: Mapping[str, Any], items: list[Mapping[str, Any]]) -> tuple[int, int]:
    if items:
        total = len(items)
        completed = sum(1 for item in items if _text(item.get("status")) in {"done", "skipped"})
        return completed, total
    remaining = status.get("milestones_remaining")
    try:
        remaining_int = int(remaining)
    except (TypeError, ValueError):
        return 0, 0
    if remaining_int <= 0:
        return 1, 1
    return 0, remaining_int


def _promotion_label(status: Mapping[str, Any]) -> str:
    promotion = _text(status.get("promotion") or status.get("promotion_state")).casefold()
    if promotion in {"false", "blocked", "held", "non_promotion", "non-promotion"}:
        return "ao:non-promotion"
    joined = " ".join(
        _text(status.get(key))
        for key in ("active_checklist", "lane_claim", "notes")
        if _text(status.get(key))
    ).casefold()
    if "promotion is intentionally held" in joined or "promote only after" in joined:
        return "ao:non-promotion"
    return ""


def _derive_status_and_labels(
    status: Mapping[str, Any],
    heartbeat: Mapping[str, Any],
    *,
    now: datetime,
    stale_seconds: int,
) -> tuple[str, list[str]]:
    labels = ["ao"]
    phase = _text(status.get("phase") or heartbeat.get("phase")).casefold()
    heartbeat_phase = _text(heartbeat.get("phase")).casefold()
    items = _runsheet_items(status)
    remaining = status.get("milestones_remaining")
    try:
        remaining_int = int(remaining)
    except (TypeError, ValueError):
        remaining_int = None

    exit_code = status.get("last_exit_code", heartbeat.get("exit_code"))
    try:
        exit_int = int(exit_code) if exit_code not in (None, "") else 0
    except (TypeError, ValueError):
        exit_int = 0

    if heartbeat_phase == "done":
        completed_at = _completion_time(status, heartbeat)
        if completed_at:
            labels.append("ao:completed")

    age = _age_seconds(heartbeat.get("last_heartbeat") or status.get("last_cycle_finished_at"), now)
    doneish = (
        phase in {"done", "complete", "completed"}
        or heartbeat_phase == "done"
        or remaining_int == 0
    )
    if age is not None and age > stale_seconds and not doneish:
        labels.append("ao:stale")
        identity = " ".join(
            _text(status.get(key))
            for key in ("orchestrator_id", "lane", "lane_claim", "active_checklist")
            if _text(status.get(key))
        ).casefold()
        if "supermanager" in identity or "root" in identity or "validation" in identity:
            labels.extend(["ao:root-validation-stale", "ao:blocked-upstream"])

    promotion_label = _promotion_label(status)
    if promotion_label:
        labels.append(promotion_label)

    if phase == "skipped" or (items and all(_text(item.get("status")) == "skipped" for item in items)):
        return "skipped", labels
    if exit_int != 0 or phase in {"failed", "error", "rejected"}:
        labels.append("ao:manager-rejected")
        return "needs_retry", labels
    if _text(heartbeat.get("blocker")) or _has_blocked_item(items):
        labels.append("ao:blocked-upstream")
        return "blocked_upstream", labels
    if not doneish and (heartbeat.get("child_pid") or heartbeat_phase in {"running", "implementing", "testing"}):
        return "running", labels
    if _has_pending_validation(items) or _text(status.get("tests")).casefold() in {"pending", "unknown", "failing"}:
        labels.append("ao:validation-needed")
        return "validation_needed", labels
    if doneish:
        labels.append("ao:manager-accepted")
        return "done", labels
    return "queued", labels


def _subtasks(items: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items:
        title = _text(item.get("title") or item.get("id"))
        if not title:
            continue
        status = _text(item.get("status") or "todo")
        if status == "in_progress":
            status = "running"
        elif status == "blocked":
            status = "blocked_upstream"
        elif status not in AO_CONTROL_STATUS_COLUMNS and status not in {"todo", "done", "skipped"}:
            status = "todo"
        rows.append({"title": title, "status": status})
    return rows


def _status_paths(status_root: Path) -> list[Path]:
    return sorted(
        path
        for path in status_root.glob("status.*.json")
        if path.is_file() and path.name != "status.json"
    )


def build_ao_control_runsheet(
    status_root: str | Path,
    *,
    now_iso: str | None = None,
    stale_seconds: int = 1800,
    include_prefix: str = "",
) -> dict[str, Any]:
    root = Path(status_root).expanduser().resolve()
    now = _parse_utc(now_iso) if now_iso else datetime.now(UTC).replace(microsecond=0)
    if now is None:
        raise ValueError(f"invalid now timestamp: {now_iso!r}")
    rendered_now = now.isoformat().replace("+00:00", "Z")

    items: list[dict[str, Any]] = []
    for status_path in _status_paths(root):
        payload = _read_json(status_path)
        orchestrator_id = _text(payload.get("orchestrator_id") or status_path.stem.removeprefix("status."))
        if orchestrator_id and not _text(payload.get("orchestrator_id")):
            payload["orchestrator_id"] = orchestrator_id
        if include_prefix and not orchestrator_id.startswith(include_prefix):
            continue
        heartbeat_path = status_path.with_name(status_path.name.replace("status.", "heartbeat.", 1))
        heartbeat = _read_json(heartbeat_path) if heartbeat_path.exists() else {}
        source_items = _runsheet_items(payload)
        derived_status, labels = _derive_status_and_labels(
            payload,
            heartbeat,
            now=now,
            stale_seconds=stale_seconds,
        )
        completed, total = _progress(payload, source_items)
        runtime = _duration_seconds(payload.get("last_cycle_started_at"), payload.get("last_cycle_finished_at"), now)
        current_step = _text(heartbeat.get("current_step") or payload.get("notes") or payload.get("active_checklist"))
        completed_at = _completion_time(payload, heartbeat) if derived_status in {"done", "skipped"} else ""
        progress_text = f"{completed}/{total}" if total else ""
        heartbeat_display = "done@" + completed_at if completed_at else ""
        if not heartbeat_display:
            heartbeat_display = "last@" + _text(heartbeat.get("last_heartbeat")) if _text(heartbeat.get("last_heartbeat")) else "-"
        description_lines = [
            f"Lane: {_text(payload.get('lane')) or '-'}",
            f"Phase: {_text(payload.get('phase') or heartbeat.get('phase')) or '-'}",
            f"Heartbeat: {heartbeat_display}",
            f"Progress: {progress_text or '-'}",
        ]
        if current_step:
            description_lines.extend(["", current_step])

        items.append(
            {
                "id": f"ao-control:{orchestrator_id}",
                "title": f"AO {orchestrator_id}",
                "status": derived_status,
                "runner_id": orchestrator_id,
                "lane": _text(payload.get("lane")),
                "parent_id": _text(payload.get("parent_orchestrator_id")),
                "source": "ao_control_surface",
                "labels": sorted(dict.fromkeys(labels)),
                "description": "\n".join(description_lines),
                "subtasks": _subtasks(source_items),
                "metadata": {
                    "statibaker.ao.phase": _text(payload.get("phase") or heartbeat.get("phase")),
                    "statibaker.ao.heartbeat": "done@" + completed_at if completed_at else _text(heartbeat.get("last_heartbeat")),
                    "statibaker.ao.current_step": current_step,
                    "statibaker.ao.milestones": progress_text,
                    "statibaker.ao.runtime": _format_duration(runtime),
                    "statibaker.ao.completed_at": completed_at,
                    "statibaker.ao.promotion": "false" if "ao:non-promotion" in labels else "",
                    "statibaker.ao.validation": "needed" if derived_status == "validation_needed" else "",
                    "statibaker.ao.retry_of": _text(payload.get("retry_of")),
                },
            }
        )

    return {
        "schema_version": AO_CONTROL_SCHEMA_VERSION,
        "generated_at": rendered_now,
        "source": "ao_control_surface",
        "status_root": str(root),
        "authority_boundary": {
            "ao_artifacts_are_source_of_truth": True,
            "kanboard_is_external_projection": True,
            "chat_summaries_are_not_source": True,
        },
        "orchestrator_id": "statibaker-ao-control-surface",
        "lane": "ao-kanboard-control-surface",
        "runsheet": {"items": items},
        "summary": {
            "cards": len(items),
            "by_status": {status: sum(1 for item in items if item["status"] == status) for status in AO_CONTROL_STATUS_COLUMNS},
        },
    }
