from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUIRED_STATUS_COLUMNS: dict[str, str] = {
    "todo": "Backlog",
    "in_progress": "Doing",
    "blocked": "Blocked",
    "done": "Done",
    "skipped": "Skipped",
}


class KanboardBootstrapError(RuntimeError):
    """Raised when the Kanboard bootstrap command cannot proceed."""


class KanboardRpcError(RuntimeError):
    """Raised when a JSON-RPC call fails."""


@dataclass
class KanboardRuntimeConfig:
    endpoint: str
    project_id: int | None
    project_name: str | None
    api_user: str
    api_token: str
    api_auth_header: str


class KanboardRpcClient:
    def __init__(
        self,
        *,
        endpoint: str,
        api_user: str,
        api_token: str,
        api_auth_header: str = "",
        timeout_seconds: float = 5.0,
        requester: Callable[[Request, float], bytes] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_user = api_user
        self.api_token = api_token
        self.api_auth_header = api_auth_header
        self.timeout_seconds = timeout_seconds
        self._id_counter = count(1)
        self._requester = requester or self._default_requester

    def _default_requester(self, request: Request, timeout_seconds: float) -> bytes:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_user and self.api_token:
            raw = f"{self.api_user}:{self.api_token}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
        if self.api_auth_header and self.api_token:
            headers[self.api_auth_header] = self.api_token
        return headers

    def call(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": next(self._id_counter),
            "params": dict(params or {}),
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(self.endpoint, data=body, headers=self._headers(), method="POST")
        try:
            raw = self._requester(request, self.timeout_seconds)
        except HTTPError as exc:
            raise KanboardRpcError(f"HTTP error from Kanboard ({exc.code}): {method}") from exc
        except URLError as exc:
            raise KanboardRpcError(f"Kanboard endpoint unreachable for {method}: {exc.reason}") from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive malformed response surface
            raise KanboardRpcError(f"Invalid JSON-RPC response for {method}") from exc

        if decoded.get("error"):
            message = decoded.get("error", {}).get("message") or "Unknown JSON-RPC error"
            raise KanboardRpcError(f"Kanboard JSON-RPC error for {method}: {message}")
        return decoded.get("result")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_title(value: Any) -> str:
    return _text(value).casefold()


def _coerce_int(value: Any) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_env_file(path: str | Path) -> dict[str, str]:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return {}
    parsed: dict[str, str] = {}
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            parsed[key] = value
    return parsed


def resolve_runtime_config(env: Mapping[str, str], overrides: Mapping[str, Any]) -> KanboardRuntimeConfig:
    def pick(name: str, default: str = "") -> str:
        override = _text(overrides.get(name))
        if override:
            return override
        return _text(env.get(name, default))

    endpoint = pick("KANBOARD_JSONRPC_ENDPOINT") or pick("KANBOARD_BASE_URL")
    if endpoint and endpoint.endswith("/"):
        endpoint = endpoint.rstrip("/")
    if endpoint and not endpoint.endswith("/jsonrpc.php"):
        endpoint = endpoint + "/jsonrpc.php"

    project_id = _coerce_int(overrides.get("KANBOARD_PROJECT_ID"))
    if project_id is None:
        project_id = _coerce_int(env.get("KANBOARD_PROJECT_ID"))

    project_name = pick("KANBOARD_PROJECT_NAME")

    return KanboardRuntimeConfig(
        endpoint=endpoint,
        project_id=project_id,
        project_name=project_name or None,
        api_user=pick("KANBOARD_API_USER", "jsonrpc"),
        api_token=pick("KANBOARD_API_TOKEN"),
        api_auth_header=pick("KANBOARD_API_AUTH_HEADER"),
    )


def _as_project_row(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _resolve_project(
    client: KanboardRpcClient,
    *,
    project_id: int | None,
    project_name: str | None,
    apply: bool,
    operations: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool, bool]:
    project: dict[str, Any] = {}
    if project_id is not None:
        project = _as_project_row(client.call("getProjectById", {"project_id": project_id}))
        operations.append({"op": "get_project_by_id", "project_id": project_id, "found": bool(project)})

    if not project and project_name:
        project = _as_project_row(client.call("getProjectByName", {"name": project_name}))
        operations.append({"op": "get_project_by_name", "name": project_name, "found": bool(project)})

    if project:
        return project, False, False

    if not project_name:
        if project_id is None:
            raise KanboardBootstrapError("Project not found and no project id/name was provided.")
        project_name = f"StatiBaker Board {project_id}"

    if not apply:
        operations.append({"op": "create_project", "status": "planned", "name": project_name})
        return {"id": project_id, "name": project_name}, False, True

    created_id = client.call("createProject", {"name": project_name})
    created_project_id = _coerce_int(created_id)
    if created_project_id is None:
        raise KanboardBootstrapError("Kanboard did not return a project id from createProject.")
    operations.append({"op": "create_project", "status": "applied", "name": project_name, "project_id": created_project_id})
    project = _as_project_row(client.call("getProjectById", {"project_id": created_project_id}))
    if not project:
        project = {"id": created_project_id, "name": project_name}
    return project, True, False


def _column_by_title(columns: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for column in columns:
        title_key = _normalize_title(column.get("title"))
        if title_key and title_key not in mapping:
            mapping[title_key] = column
    return mapping


def bootstrap_board(
    client: KanboardRpcClient,
    *,
    project_id: int | None,
    project_name: str | None,
    apply: bool,
    required_columns: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    required = dict(REQUIRED_STATUS_COLUMNS)
    for status, name in dict(required_columns or {}).items():
        required[_text(status)] = _text(name)

    operations: list[dict[str, Any]] = []
    project, project_created, project_create_planned = _resolve_project(
        client,
        project_id=project_id,
        project_name=project_name,
        apply=apply,
        operations=operations,
    )

    resolved_project_id = _coerce_int(project.get("id"))
    columns: list[dict[str, Any]] = []
    if resolved_project_id is not None:
        columns = [dict(row) for row in (client.call("getColumns", {"project_id": resolved_project_id}) or []) if isinstance(row, Mapping)]
        operations.append({"op": "get_columns", "project_id": resolved_project_id, "count": len(columns)})

    existing_by_title = _column_by_title(columns)
    missing_statuses: list[str] = []

    for status, column_name in required.items():
        existing = existing_by_title.get(_normalize_title(column_name))
        if existing:
            continue
        missing_statuses.append(status)
        if resolved_project_id is None:
            continue
        if not apply:
            operations.append({"op": "add_column", "status": "planned", "column_name": column_name, "status_key": status})
            continue
        created_column_id = client.call("addColumn", {"project_id": resolved_project_id, "title": column_name})
        operations.append(
            {
                "op": "add_column",
                "status": "applied",
                "column_name": column_name,
                "status_key": status,
                "column_id": _coerce_int(created_column_id),
            }
        )

    if resolved_project_id is not None and apply and missing_statuses:
        columns = [dict(row) for row in (client.call("getColumns", {"project_id": resolved_project_id}) or []) if isinstance(row, Mapping)]
        operations.append({"op": "refresh_columns", "project_id": resolved_project_id, "count": len(columns)})
        existing_by_title = _column_by_title(columns)

    column_map: dict[str, dict[str, Any]] = {}
    unresolved: list[str] = []
    for status, column_name in required.items():
        match = existing_by_title.get(_normalize_title(column_name))
        column_map[status] = {
            "column_id": _coerce_int(match.get("id") if match else None),
            "column_name": _text(match.get("title") if match else column_name),
        }
        if column_map[status]["column_id"] is None:
            unresolved.append(status)

    ready_for_sync = resolved_project_id is not None and not unresolved

    return {
        "schema_version": "sb.kanboard_bootstrap.v0_1",
        "mode": "apply" if apply else "dry_run",
        "authority_boundary": {
            "mutates_kanboard": bool(apply),
            "kanboard_is_not_source_of_truth": True,
            "secrets_emitted": False,
        },
        "project": {
            "project_id": resolved_project_id,
            "project_name": _text(project.get("name")) or project_name,
            "created": project_created,
            "create_planned": project_create_planned,
        },
        "column_map": column_map,
        "required_statuses": list(required.keys()),
        "unresolved_statuses": unresolved,
        "ready_for_sync": ready_for_sync,
        "operations": operations,
    }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> str:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(target)
