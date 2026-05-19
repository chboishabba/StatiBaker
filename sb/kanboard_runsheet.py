from __future__ import annotations

import base64
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request

VALID_STATUSES = {
    "todo",
    "in_progress",
    "blocked",
    "done",
    "skipped",
    "queued",
    "running",
    "needs_retry",
    "blocked_upstream",
    "validation_needed",
}

DEFAULT_COLUMN_BY_STATUS = {
    "todo": "Backlog",
    "in_progress": "Doing",
    "blocked": "Blocked",
    "done": "Done",
    "skipped": "Skipped",
    "queued": "Queued",
    "running": "Running",
    "needs_retry": "Needs Retry",
    "blocked_upstream": "Blocked Upstream",
    "validation_needed": "Validation Needed",
}

METADATA_KEYS = (
    "statibaker.stable_id",
    "statibaker.source",
    "statibaker.runner_id",
    "statibaker.lane",
    "statibaker.parent_id",
    "statibaker.canonical_thread_id",
    "statibaker.source_message_id",
    "statibaker.lifecycle_residual",
    "statibaker.task_identity_residual",
    "statibaker.labels",
    "statibaker.ao.phase",
    "statibaker.ao.heartbeat",
    "statibaker.ao.current_step",
    "statibaker.ao.milestones",
    "statibaker.ao.runtime",
    "statibaker.ao.completed_at",
    "statibaker.ao.promotion",
    "statibaker.ao.validation",
    "statibaker.ao.retry_of",
    "statibaker.last_sync_at",
)
SYNC_REPORT_SCHEMA_VERSION = "sb.kanboard_sync_report.v0_1"
DEFAULT_KANBOARD_ENV_PATH = "/home/c/.local/state/kanboard-local/statibaker-kanboard.env"
APPLY_PHASE_ORDER = ("lookup", "create", "update", "move", "tags", "metadata")


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _as_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected object JSON: {path}")
    return dict(payload)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def _resolve_runsheet_source(payload: Mapping[str, Any], base_path: Path) -> dict[str, Any]:
    source_row = _as_dict(payload.get("runsheet_source"))
    source_path_text = _text(source_row.get("path"))
    if not source_path_text:
        return dict(payload)
    source_path = Path(source_path_text)
    if not source_path.is_absolute():
        source_path = (base_path.parent / source_path).resolve()
    return _read_json(source_path)


def _normalize_status(raw: Any) -> str:
    status = _text(raw).casefold()
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {raw!r}")
    return status


def _task_description(row: Mapping[str, Any]) -> str:
    lines: list[str] = []
    description = _text(row.get("description") or row.get("details"))
    if description:
        lines.append(description)
    acceptance = _text(row.get("acceptance_criteria"))
    if acceptance:
        if lines:
            lines.append("")
        lines.append(f"Acceptance: {acceptance}")
    subtasks = _as_list(row.get("subtasks"))
    if subtasks:
        lines.append("")
        lines.append("Subtasks:")
        for item in subtasks:
            subtask = _as_dict(item)
            sub_title = _text(subtask.get("title"))
            if not sub_title:
                continue
            try:
                sub_status = _normalize_status(subtask.get("status") or "todo")
            except ValueError:
                sub_status = "todo"
            marker = "x" if sub_status == "done" else " "
            lines.append(f"- [{marker}] {sub_title}")
    return "\n".join(lines).strip()


def _iter_runsheet_items(
    items: list[Any],
    *,
    source: str,
    runner_id: str,
    lane: str,
    parent_stable_id: str = "",
    depth: int = 0,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in items:
        item = _as_dict(raw)
        stable_id = _text(item.get("stable_id") or item.get("id"))
        if not stable_id:
            raise ValueError("runsheet item missing stable_id/id")
        title = _text(item.get("title") or stable_id)
        status = _normalize_status(item.get("status") or "todo")
        row = {
            "stable_id": stable_id,
            "title": title,
            "status": status,
            "runner_id": _text(item.get("runner_id") or runner_id),
            "lane": _text(item.get("lane") or lane),
            "parent_id": _text(item.get("parent_id") or parent_stable_id),
            "depth": depth,
            "source": _text(item.get("source") or source),
            "provenance": _as_dict(item.get("provenance")),
            "acceptance_criteria": _text(item.get("acceptance_criteria")),
            "description": _text(item.get("description") or item.get("details")),
            "labels": [str(v) for v in _as_list(item.get("labels")) if _text(v)],
            "subtasks": [_as_dict(v) for v in _as_list(item.get("subtasks")) if isinstance(v, Mapping)],
            "metadata": _as_dict(item.get("metadata")),
            "canonical_thread_id": _text(
                item.get("canonical_thread_id")
                or item.get("provenance", {}).get("canonical_thread_id")
                if isinstance(item.get("provenance"), Mapping)
                else ""
            ),
            "source_message_id": _text(
                item.get("source_message_id")
                or item.get("provenance", {}).get("source_message_id")
                if isinstance(item.get("provenance"), Mapping)
                else ""
            ),
            "lifecycle_residual": _text(
                item.get("lifecycle_residual")
                or item.get("provenance", {}).get("lifecycle_residual")
                if isinstance(item.get("provenance"), Mapping)
                else ""
            ),
            "task_identity_residual": _text(
                item.get("task_identity_residual")
                or item.get("provenance", {}).get("task_identity_residual")
                if isinstance(item.get("provenance"), Mapping)
                else ""
            ),
        }
        rows.append(row)

        child_rows = _iter_runsheet_items(
            _as_list(item.get("items")),
            source=source,
            runner_id=runner_id,
            lane=lane,
            parent_stable_id=stable_id,
            depth=depth + 1,
        )
        rows.extend(child_rows)
    return rows


def load_local_rows(path: str | Path) -> dict[str, Any]:
    source_path = Path(path).expanduser().resolve()
    payload = _resolve_runsheet_source(_read_json(source_path), source_path)

    schema_version = _text(payload.get("schema_version"))
    source = _text(payload.get("source") or "status")
    runner_id = _text(payload.get("orchestrator_id") or payload.get("runner_id"))
    lane = _text(payload.get("lane"))

    if schema_version.startswith("sl.statibaker_task_memory"):
        tasks = _as_list(payload.get("tasks"))
        rows = []
        for raw in tasks:
            task = _as_dict(raw)
            stable_id = _text(task.get("stable_id") or task.get("task_id") or task.get("id"))
            if not stable_id:
                raise ValueError("task row missing stable_id/task_id/id")
            status = _normalize_status(task.get("status") or "todo")
            rows.append(
                {
                    "stable_id": stable_id,
                    "title": _text(task.get("title") or task.get("summary") or stable_id),
                    "status": status,
                    "runner_id": _text(task.get("runner_id") or runner_id),
                    "lane": _text(task.get("lane") or lane),
                    "parent_id": _text(task.get("parent_id")),
                    "depth": int(task.get("depth") or 0),
                    "source": _text(task.get("source") or "statibaker_task_memory"),
                    "provenance": _as_dict(task.get("provenance")),
                    "acceptance_criteria": _text(task.get("acceptance_criteria")),
                    "description": _text(task.get("description") or task.get("details")),
                    "labels": [str(v) for v in _as_list(task.get("labels")) if _text(v)],
                    "subtasks": [_as_dict(v) for v in _as_list(task.get("subtasks")) if isinstance(v, Mapping)],
                    "metadata": _as_dict(task.get("metadata")),
                    "canonical_thread_id": _text(task.get("canonical_thread_id")),
                    "source_message_id": _text(task.get("source_message_id")),
                    "lifecycle_residual": _text(task.get("lifecycle_residual")),
                    "task_identity_residual": _text(task.get("task_identity_residual")),
                }
            )
        return {"rows": rows, "source_payload": payload, "source_path": str(source_path)}

    runsheet = _as_dict(payload.get("runsheet"))
    items = _as_list(runsheet.get("items"))
    if not items:
        items = _as_list(payload.get("tasks"))
        source = _text(payload.get("source") or "tasks")

    rows = _iter_runsheet_items(items, source=source, runner_id=runner_id, lane=lane)
    stable_ids = [row["stable_id"] for row in rows]
    duplicates = sorted({stable_id for stable_id in stable_ids if stable_ids.count(stable_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate stable_id values: {', '.join(duplicates)}")
    return {"rows": rows, "source_payload": payload, "source_path": str(source_path)}


def _build_metadata(row: Mapping[str, Any], now_iso: str) -> dict[str, str]:
    labels = [str(v) for v in _as_list(row.get("labels")) if _text(v)]
    values = {
        "statibaker.stable_id": _text(row.get("stable_id")),
        "statibaker.source": _text(row.get("source")),
        "statibaker.runner_id": _text(row.get("runner_id")),
        "statibaker.lane": _text(row.get("lane")),
        "statibaker.parent_id": _text(row.get("parent_id")),
        "statibaker.canonical_thread_id": _text(row.get("canonical_thread_id")),
        "statibaker.source_message_id": _text(row.get("source_message_id")),
        "statibaker.lifecycle_residual": _text(row.get("lifecycle_residual")),
        "statibaker.task_identity_residual": _text(row.get("task_identity_residual")),
        "statibaker.labels": ",".join(labels),
        "statibaker.last_sync_at": now_iso,
    }
    for key, value in _as_dict(row.get("metadata")).items():
        key_text = _text(key)
        if key_text.startswith("statibaker."):
            values[key_text] = _text(value)
    return {key: value for key, value in values.items() if value or key == "statibaker.last_sync_at"}


def _resolve_task_id(existing: Mapping[str, Any], stable_id: str) -> Any:
    task_id = existing.get("id")
    if task_id not in (None, ""):
        return task_id
    return f"$lookup_task_id:{stable_id}"


def load_kanboard_env(path: str | Path | None = None) -> dict[str, Any]:
    env_path = Path(path or DEFAULT_KANBOARD_ENV_PATH).expanduser()
    from_file = _read_env_file(env_path)
    merged = dict(from_file)
    merged.update({key: value for key, value in os.environ.items() if key.startswith("KANBOARD_")})
    project_id_text = _text(merged.get("KANBOARD_PROJECT_ID"))
    project_id = int(project_id_text) if project_id_text else None
    return {
        "env_path": str(env_path),
        "base_url": _text(merged.get("KANBOARD_BASE_URL")),
        "jsonrpc_endpoint": _text(merged.get("KANBOARD_JSONRPC_ENDPOINT")),
        "project_id": project_id,
        "api_user": _text(merged.get("KANBOARD_API_USER")),
        "api_token": _text(merged.get("KANBOARD_API_TOKEN")),
        "api_auth_header": _text(merged.get("KANBOARD_API_AUTH_HEADER")),
    }


class KanboardJsonRpcClient:
    def __init__(
        self,
        *,
        endpoint: str,
        api_user: str,
        api_token: str,
        api_auth_header: str = "",
        timeout_seconds: float = 10.0,
        transient_lock_retries: int = 2,
        transient_lock_retry_delay_seconds: float = 0.1,
    ) -> None:
        self.endpoint = _text(endpoint)
        self.api_user = _text(api_user)
        self.api_token = _text(api_token)
        self.api_auth_header = _text(api_auth_header)
        self.timeout_seconds = float(timeout_seconds)
        self.transient_lock_retries = max(0, int(transient_lock_retries))
        self.transient_lock_retry_delay_seconds = max(0.0, float(transient_lock_retry_delay_seconds))
        if not self.endpoint:
            raise ValueError("KANBOARD_JSONRPC_ENDPOINT is required for --apply")
        if not self.api_auth_header and (not self.api_user or not self.api_token):
            raise ValueError("KANBOARD_API_USER and KANBOARD_API_TOKEN are required for basic auth")

    @classmethod
    def from_env(cls, env_config: Mapping[str, Any], *, timeout_seconds: float = 10.0) -> "KanboardJsonRpcClient":
        return cls(
            endpoint=_text(env_config.get("jsonrpc_endpoint")),
            api_user=_text(env_config.get("api_user")),
            api_token=_text(env_config.get("api_token")),
            api_auth_header=_text(env_config.get("api_auth_header")),
            timeout_seconds=timeout_seconds,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_auth_header:
            if ":" in self.api_auth_header:
                key, value = self.api_auth_header.split(":", 1)
                headers[_text(key)] = value.strip()
            else:
                headers["Authorization"] = self.api_auth_header
            return headers
        credentials = f"{self.api_user}:{self.api_token}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")
        return headers

    def call(self, method: str, params: Mapping[str, Any]) -> Any:
        for attempt in range(self.transient_lock_retries + 1):
            body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": dict(params),
            }
            request = urllib_request.Request(
                self.endpoint,
                data=json.dumps(body).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            try:
                with urllib_request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
            except urllib_error.URLError as exc:
                raise RuntimeError(f"kanboard request failed for {method}: {exc}") from exc
            payload = json.loads(raw or "{}")
            if not isinstance(payload, Mapping):
                raise RuntimeError(f"invalid JSON-RPC response for {method}")
            error_row = _as_dict(payload.get("error"))
            if error_row:
                message = _text(error_row.get("message") or "unknown error")
                if "database is locked" in message.casefold() and attempt < self.transient_lock_retries:
                    if self.transient_lock_retry_delay_seconds > 0:
                        time.sleep(self.transient_lock_retry_delay_seconds)
                    continue
                raise RuntimeError(f"kanboard JSON-RPC error for {method}: {message}")
            return payload.get("result")
        raise RuntimeError(f"kanboard JSON-RPC error for {method}: unknown retry failure")


def _resolve_target_column_id(status: str, target_column: Any) -> int | None:
    if target_column is None:
        return None
    if isinstance(target_column, Mapping):
        raw_column_id = target_column.get("column_id")
        if raw_column_id in (None, ""):
            raise ValueError(f"missing column_id mapping for status: {status}")
        try:
            return int(raw_column_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid column_id mapping for status {status}: {raw_column_id!r}") from exc
    if isinstance(target_column, int):
        return target_column
    return None


def _normalize_column_by_status(column_by_status: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(column_by_status, Mapping):
        return {}
    payload = dict(column_by_status)
    wrapped = payload.get("column_map")
    if isinstance(wrapped, Mapping):
        return {str(key): value for key, value in dict(wrapped).items()}
    return {str(key): value for key, value in payload.items()}


def fetch_existing_by_reference(
    rows: list[Mapping[str, Any]],
    *,
    project_id: int,
    rpc_call: Callable[[str, Mapping[str, Any]], Any],
) -> dict[str, dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    for row in rows:
        if int(row.get("depth") or 0) != 0:
            continue
        stable_id = _text(row.get("stable_id"))
        if not stable_id or stable_id in existing:
            continue
        result = rpc_call("getTaskByReference", {"project_id": project_id, "reference": stable_id})
        if isinstance(result, Mapping) and result:
            existing[stable_id] = dict(result)
    return existing


def build_dry_run_plan(
    rows: list[Mapping[str, Any]],
    *,
    project_id: int,
    now_iso: str,
    existing_by_reference: Mapping[str, Mapping[str, Any]] | None = None,
    column_by_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    existing_ref = dict(existing_by_reference or {})
    column_map = dict(DEFAULT_COLUMN_BY_STATUS)
    for key, value in _normalize_column_by_status(column_by_status).items():
        column_map[key] = value

    operations: list[dict[str, Any]] = []
    summary = {"lookups": 0, "creates": 0, "updates": 0, "moves": 0, "tags": 0, "metadata": 0}

    top_level_rows = [row for row in rows if int(row.get("depth") or 0) == 0]
    for row in top_level_rows:
        stable_id = _text(row.get("stable_id"))
        status = _normalize_status(row.get("status"))
        title = _text(row.get("title") or stable_id)
        description = _task_description(row)
        labels = [str(label) for label in _as_list(row.get("labels")) if _text(label)]
        target_column = column_map.get(status)
        target_column_id = _resolve_target_column_id(status, target_column)

        lookup = {
            "op": "lookup",
            "stable_id": stable_id,
            "rpc": {
                "method": "getTaskByReference",
                "params": {"project_id": project_id, "reference": stable_id},
            },
        }
        operations.append(lookup)
        summary["lookups"] += 1

        existing = _as_dict(existing_ref.get(stable_id))
        if existing:
            task_id = _resolve_task_id(existing, stable_id)
            needs_update = (
                _text(existing.get("title")) != title
                or _text(existing.get("description")) != description
                or _text(existing.get("reference")) not in {"", stable_id}
            )
            if needs_update:
                update_params: dict[str, Any] = {
                    "id": task_id,
                    "title": title,
                    "description": description,
                    "reference": stable_id,
                }
                if labels:
                    update_params["tags"] = labels
                operations.append(
                    {
                        "op": "update",
                        "stable_id": stable_id,
                        "rpc": {"method": "updateTask", "params": update_params},
                    }
                )
                summary["updates"] += 1
            existing_column_id = existing.get("column_id")
            if target_column_id is not None and str(existing_column_id) != str(target_column_id):
                operations.append(
                    {
                        "op": "move",
                        "stable_id": stable_id,
                        "rpc": {
                            "method": "moveTaskPosition",
                            "params": {
                                "project_id": project_id,
                                "task_id": task_id,
                                "column_id": target_column_id,
                                "position": 1,
                            },
                        },
                    }
                )
                summary["moves"] += 1
            metadata_task_id = task_id
        else:
            create_params: dict[str, Any] = {
                "title": title,
                "project_id": project_id,
                "reference": stable_id,
                "description": description,
            }
            if target_column_id is not None:
                create_params["column_id"] = target_column_id
            if labels:
                create_params["tags"] = labels
            operations.append(
                {
                    "op": "create",
                    "stable_id": stable_id,
                    "rpc": {"method": "createTask", "params": create_params},
                }
            )
            summary["creates"] += 1
            metadata_task_id = f"$created_task_id:{stable_id}"

        if labels:
            operations.append(
                {
                    "op": "tags",
                    "stable_id": stable_id,
                    "rpc": {
                        "method": "setTaskTags",
                        "params": {
                            "project_id": project_id,
                            "task_id": metadata_task_id,
                            "tags": labels,
                        },
                    },
                }
            )
            summary["tags"] += 1

        operations.append(
            {
                "op": "metadata",
                "stable_id": stable_id,
                "rpc": {
                    "method": "saveTaskMetadata",
                    "params": {
                        "task_id": metadata_task_id,
                        "values": _build_metadata(row, now_iso),
                    },
                },
            }
        )
        summary["metadata"] += 1

    done_count = sum(1 for row in top_level_rows if _text(row.get("status")) == "done")
    return {
        "schema_version": "sb.kanboard_dry_run.v0_1",
        "mode": "dry_run",
        "authority_boundary": {
            "mutates_kanboard": False,
            "kanboard_is_not_source_of_truth": True,
        },
        "project_id": project_id,
        "task_count": len(top_level_rows),
        "progress": {
            "completed": done_count,
            "total": len(top_level_rows),
        },
        "required_rpc_shape": [
            "getTaskByReference",
            "createTask",
            "updateTask",
            "moveTaskPosition",
            "setTaskTags",
            "saveTaskMetadata",
        ],
        "metadata_keys": list(METADATA_KEYS),
        "apply_transaction_order": list(APPLY_PHASE_ORDER),
        "summary": summary,
        "operations": operations,
    }


def _resolve_task_placeholder(value: Any, task_ids_by_stable_id: Mapping[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith("$lookup_task_id:") or value.startswith("$created_task_id:"):
        stable_id = value.split(":", 1)[1]
        if stable_id not in task_ids_by_stable_id:
            raise KeyError(f"missing resolved task id for stable_id: {stable_id}")
        return task_ids_by_stable_id[stable_id]
    return value


def _resolve_param_placeholders(value: Any, task_ids_by_stable_id: Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _resolve_param_placeholders(raw, task_ids_by_stable_id) for key, raw in value.items()}
    if isinstance(value, list):
        return [_resolve_param_placeholders(item, task_ids_by_stable_id) for item in value]
    return _resolve_task_placeholder(value, task_ids_by_stable_id)


def _extract_task_id(result: Any, stable_id: str) -> Any:
    task_id = result.get("id") if isinstance(result, Mapping) else result
    if task_id in (None, "", False):
        raise RuntimeError(f"missing task id in createTask result for stable_id={stable_id}")
    return task_id


def apply_sync_plan(
    plan: Mapping[str, Any],
    rpc_call: Callable[[str, Mapping[str, Any]], Any],
) -> dict[str, Any]:
    schema_version = _text(plan.get("schema_version"))
    if schema_version != "sb.kanboard_dry_run.v0_1":
        raise ValueError(f"unsupported plan schema_version for apply: {schema_version!r}")

    operations = [_as_dict(row) for row in _as_list(plan.get("operations")) if isinstance(row, Mapping)]
    grouped: dict[str, list[dict[str, Any]]] = {phase: [] for phase in APPLY_PHASE_ORDER}
    for operation in operations:
        op_name = _text(operation.get("op"))
        if op_name in grouped:
            grouped[op_name].append(operation)

    task_ids: dict[str, Any] = {}
    executed = {phase: 0 for phase in APPLY_PHASE_ORDER}
    skipped = {phase: 0 for phase in APPLY_PHASE_ORDER}
    errors: list[dict[str, Any]] = []
    call_trace: list[str] = []
    aborted = False

    for phase in APPLY_PHASE_ORDER:
        for operation in grouped[phase]:
            stable_id = _text(operation.get("stable_id"))
            rpc = _as_dict(operation.get("rpc"))
            method = _text(rpc.get("method"))
            raw_params = _as_dict(rpc.get("params"))
            try:
                if phase == "create" and stable_id in task_ids:
                    skipped[phase] += 1
                    continue
                params = _resolve_param_placeholders(raw_params, task_ids)
                result = rpc_call(method, params)
                call_trace.append(method)
                executed[phase] += 1

                if phase == "lookup" and isinstance(result, Mapping):
                    lookup_task_id = result.get("id")
                    if lookup_task_id not in (None, ""):
                        task_ids[stable_id] = lookup_task_id
                elif phase == "create":
                    task_ids[stable_id] = _extract_task_id(result, stable_id)
            except Exception as exc:
                aborted = True
                errors.append(
                    {
                        "phase": phase,
                        "stable_id": stable_id,
                        "method": method,
                        "message": str(exc),
                    }
                )
                break
        if aborted:
            break

    return {
        "schema_version": "sb.kanboard_apply_report.v0_1",
        "transaction_order": list(APPLY_PHASE_ORDER),
        "aborted": aborted,
        "executed": executed,
        "skipped": skipped,
        "resolved_task_ids": task_ids,
        "errors": errors,
        "call_trace": call_trace,
        "operation_count": len(operations),
    }


def build_sync_report(
    *,
    plan: Mapping[str, Any],
    input_source_path: str,
    report_path: str = "",
    now_iso: str = "",
    errors: list[Mapping[str, Any]] | None = None,
    apply_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = _text(now_iso) or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    summary_row = _as_dict(plan.get("summary"))
    progress_row = _as_dict(plan.get("progress"))
    authority_boundary = _as_dict(plan.get("authority_boundary"))
    operations = [_as_dict(item) for item in _as_list(plan.get("operations")) if isinstance(item, Mapping)]

    reference_rows: list[dict[str, str]] = []
    seen_stable_ids: set[str] = set()
    for operation in operations:
        stable_id = _text(operation.get("stable_id"))
        if not stable_id or stable_id in seen_stable_ids:
            continue
        seen_stable_ids.add(stable_id)
        reference_rows.append(
            {
                "stable_id": stable_id,
                "kanboard_reference": stable_id,
            }
        )

    report_errors: list[dict[str, Any]] = []
    for item in _as_list(errors):
        if isinstance(item, Mapping):
            row = {str(key): value for key, value in dict(item).items()}
            if row:
                report_errors.append(row)

    apply_mode = _text(plan.get("mode") or "dry_run") == "apply"
    executed_row = _as_dict(apply_report.get("executed")) if isinstance(apply_report, Mapping) else {}
    summary = {
        "lookups": _as_int(executed_row.get("lookup"), _as_int(summary_row.get("lookups")))
        if apply_mode
        else _as_int(summary_row.get("lookups")),
        "creates": _as_int(executed_row.get("create"), _as_int(summary_row.get("creates")))
        if apply_mode
        else _as_int(summary_row.get("creates")),
        "updates": _as_int(executed_row.get("update"), _as_int(summary_row.get("updates")))
        if apply_mode
        else _as_int(summary_row.get("updates")),
        "moves": _as_int(executed_row.get("move"), _as_int(summary_row.get("moves")))
        if apply_mode
        else _as_int(summary_row.get("moves")),
        "tags": _as_int(executed_row.get("tags"), _as_int(summary_row.get("tags")))
        if apply_mode
        else _as_int(summary_row.get("tags")),
        "metadata": _as_int(executed_row.get("metadata"), _as_int(summary_row.get("metadata")))
        if apply_mode
        else _as_int(summary_row.get("metadata")),
        "errors": len(report_errors),
    }

    return {
        "schema_version": SYNC_REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "mode": _text(plan.get("mode") or "dry_run"),
        "authority_boundary": {
            "local_json_is_canonical": True,
            "kanboard_is_external_reference_only": True,
            "mutates_kanboard": bool(authority_boundary.get("mutates_kanboard")),
        },
        "input_source": {"path": _text(input_source_path)},
        "artifact": {
            "kind": "kanboard_sync_report",
            "path": _text(report_path),
        },
        "project": {"project_id": plan.get("project_id")},
        "summary": summary,
        "progress": {
            "completed": _as_int(progress_row.get("completed")),
            "total": _as_int(progress_row.get("total")),
        },
        "external_references": {
            "kanboard_task_references": reference_rows,
        },
        "errors": report_errors,
    }
