from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


class CorkysoftMCPError(RuntimeError):
    pass


DEFAULT_CORKYSOFT_ROOT = Path(__file__).resolve().parents[3] / "corkysoft"


def _resolve_repo_root(repo_root: str | Path | None = None) -> Path:
    target = Path(repo_root).expanduser().resolve() if repo_root else DEFAULT_CORKYSOFT_ROOT.resolve()
    if not target.exists():
        raise CorkysoftMCPError(f"corkysoft repo not found: {target}")
    return target


def _bridge_command(python_executable: str | None = None) -> list[str]:
    return [python_executable or sys.executable, "-m", "corkysoft.mcp", "--bridge"]


def _run_bridge_request(
    request: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    python_executable: str | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    root = _resolve_repo_root(repo_root)
    completed = subprocess.run(
        _bridge_command(python_executable),
        cwd=root,
        input=f"{json.dumps(dict(request), sort_keys=True)}\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    stdout = (completed.stdout or "").strip()
    if completed.returncode != 0:
        raise CorkysoftMCPError(
            f"corkysoft bridge failed with exit code {completed.returncode}: {(completed.stderr or '').strip()}"
        )
    if not stdout:
        raise CorkysoftMCPError("corkysoft bridge returned no output")
    first_line = stdout.splitlines()[0]
    try:
        response = json.loads(first_line)
    except json.JSONDecodeError as exc:
        raise CorkysoftMCPError(f"corkysoft bridge returned invalid json: {first_line}") from exc
    if not isinstance(response, dict):
        raise CorkysoftMCPError("corkysoft bridge returned a non-object response")
    return response


def health(*, repo_root: str | Path | None = None, python_executable: str | None = None) -> dict[str, Any]:
    return _run_bridge_request({"op": "health"}, repo_root=repo_root, python_executable=python_executable)


def list_tools(*, repo_root: str | Path | None = None, python_executable: str | None = None) -> dict[str, Any]:
    return _run_bridge_request({"op": "list"}, repo_root=repo_root, python_executable=python_executable)


def call_tool(
    name: str,
    payload: Mapping[str, Any] | None = None,
    *,
    repo_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    if not isinstance(name, str) or not name.strip():
        raise CorkysoftMCPError("tool name is required")
    response = _run_bridge_request(
        {"op": "call", "name": name, "payload": dict(payload or {})},
        repo_root=repo_root,
        python_executable=python_executable,
    )
    if response.get("ok") is False:
        error = response.get("error") if isinstance(response.get("error"), dict) else {}
        code = str(error.get("code") or "unknown_error")
        message = str(error.get("message") or "unknown error")
        raise CorkysoftMCPError(f"{code}: {message}")
    return response


def profitability_summary(
    payload: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    return call_tool(
        "corkysoft.profitability_summary",
        payload,
        repo_root=repo_root,
        python_executable=python_executable,
    )


def dispatch_recommendations(
    payload: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    return call_tool(
        "corkysoft.dispatch_recommendations",
        payload,
        repo_root=repo_root,
        python_executable=python_executable,
    )


def operations_diary_summary(
    payload: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    return call_tool(
        "corkysoft.operations_diary_summary",
        payload,
        repo_root=repo_root,
        python_executable=python_executable,
    )


def quote_guidance_preview(
    payload: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    return call_tool(
        "corkysoft.quote_guidance_preview",
        payload,
        repo_root=repo_root,
        python_executable=python_executable,
    )
