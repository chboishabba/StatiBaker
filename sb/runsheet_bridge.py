from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

VALID_RUNSHEET_STATUSES = frozenset({"todo", "in_progress", "blocked", "done", "skipped"})


def build_runsheet_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    if not isinstance(payload, Mapping):
        return {
            "valid": False,
            "source_kind": "none",
            "rows": [],
            "progress": _empty_progress(),
            "errors": [
                {
                    "code": "invalid_payload",
                    "path": "$",
                    "message": "runsheet payload must be a JSON object",
                }
            ],
        }

    source_kind, items = _pick_source_items(payload)
    if source_kind == "none":
        errors.append(
            {
                "code": "missing_runsheet_source",
                "path": "$",
                "message": "expected runsheet.items, tasks, or timeline_cases",
            }
        )
    elif not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        errors.append(
            {
                "code": "invalid_items",
                "path": source_kind,
                "message": f"{source_kind} must be an array",
            }
        )
    else:
        for index, item in enumerate(items):
            _parse_item(
                payload=payload,
                source_kind=source_kind,
                item=item,
                path=f"{source_kind}[{index}]",
                depth=0,
                parent_id=None,
                rows=rows,
                errors=errors,
                seen_ids=seen_ids,
            )

    return {
        "valid": len(errors) == 0,
        "source_kind": source_kind,
        "rows": rows,
        "progress": _derive_progress(rows),
        "errors": errors,
    }


def _pick_source_items(payload: Mapping[str, Any]) -> tuple[str, Any]:
    runsheet = payload.get("runsheet")
    if isinstance(runsheet, Mapping) and "items" in runsheet:
        return "runsheet.items", runsheet.get("items")
    if "tasks" in payload:
        return "tasks", payload.get("tasks")
    if "timeline_cases" in payload:
        return "timeline_cases", payload.get("timeline_cases")
    return "none", None


def _parse_item(
    *,
    payload: Mapping[str, Any],
    source_kind: str,
    item: Any,
    path: str,
    depth: int,
    parent_id: str | None,
    rows: list[dict[str, Any]],
    errors: list[dict[str, str]],
    seen_ids: set[str],
) -> None:
    if not isinstance(item, Mapping):
        errors.append(
            {
                "code": "invalid_item",
                "path": path,
                "message": "item must be an object",
            }
        )
        return

    stable_id = _normalize_text(item.get("id"))
    if not stable_id and source_kind == "timeline_cases":
        stable_id = _normalize_text(item.get("case_id"))
    is_duplicate = False
    if not stable_id:
        errors.append(
            {
                "code": "missing_id",
                "path": f"{path}.id",
                "message": "item id is required",
            }
        )
    elif stable_id in seen_ids:
        is_duplicate = True
        errors.append(
            {
                "code": "duplicate_id",
                "path": f"{path}.id",
                "message": f"duplicate id: {stable_id}",
            }
        )
    else:
        seen_ids.add(stable_id)

    title = _normalize_text(item.get("title"))
    if not title and source_kind == "timeline_cases":
        title = _normalize_text(item.get("name"))
    if not title:
        errors.append(
            {
                "code": "missing_title",
                "path": f"{path}.title",
                "message": "item title is required",
            }
        )

    status = _normalize_text(item.get("status"))
    if status not in VALID_RUNSHEET_STATUSES:
        errors.append(
            {
                "code": "malformed_status",
                "path": f"{path}.status",
                "message": f"status must be one of: {', '.join(sorted(VALID_RUNSHEET_STATUSES))}",
            }
        )

    row_is_valid = bool(stable_id) and not is_duplicate and bool(title) and status in VALID_RUNSHEET_STATUSES
    if row_is_valid:
        rows.append(
            {
                "stable_id": stable_id,
                "title": title,
                "status": status,
                "runner_id": _normalize_text(payload.get("orchestrator_id")) or _normalize_text(payload.get("runner_id")),
                "lane": _normalize_text(payload.get("lane")),
                "parent_id": parent_id,
                "depth": depth,
                "source": "timeline_cases" if source_kind == "timeline_cases" else "status",
                "provenance": item.get("provenance") if isinstance(item.get("provenance"), Mapping) else {},
                "acceptance_criteria": _normalize_text(item.get("acceptance_criteria")),
                "labels": _normalize_labels(item.get("labels")),
            }
        )

    subtasks = item.get("subtasks")
    if subtasks is None:
        return
    if source_kind == "timeline_cases":
        errors.append(
            {
                "code": "timeline_cases_no_subtasks",
                "path": f"{path}.subtasks",
                "message": "timeline_cases rows must not contain subtasks",
            }
        )
        return
    if not isinstance(subtasks, Sequence) or isinstance(subtasks, (str, bytes)):
        errors.append(
            {
                "code": "invalid_subtasks",
                "path": f"{path}.subtasks",
                "message": "subtasks must be an array",
            }
        )
        return
    if depth >= 1 and len(subtasks) > 0:
        errors.append(
            {
                "code": "nested_subtask",
                "path": f"{path}.subtasks",
                "message": "nested subtasks are not allowed (max depth is 1)",
            }
        )
        return
    for index, subtask in enumerate(subtasks):
        _parse_item(
            payload=payload,
            source_kind=source_kind,
            item=subtask,
            path=f"{path}.subtasks[{index}]",
            depth=depth + 1,
            parent_id=stable_id or parent_id,
            rows=rows,
            errors=errors,
            seen_ids=seen_ids,
        )


def _derive_progress(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    top_level = [row for row in rows if int(row.get("depth", 0)) == 0 and row.get("status") != "skipped"]
    completed = len([row for row in top_level if row.get("status") == "done"])
    current = next(
        (row.get("title") for row in top_level if row.get("status") in {"in_progress", "blocked"}),
        None,
    )
    return {
        "completed": completed,
        "total": len(top_level),
        "current_milestone": current,
    }


def _empty_progress() -> dict[str, Any]:
    return {"completed": 0, "total": 0, "current_milestone": None}


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_labels(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    labels: list[str] = []
    for label in value:
        normalized = _normalize_text(label)
        if normalized:
            labels.append(normalized)
    return labels
