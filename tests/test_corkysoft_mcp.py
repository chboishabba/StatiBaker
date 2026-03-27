from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb import corkysoft_mcp  # noqa: E402


class _Completed:
    def __init__(self, *, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_call_tool_sends_bridge_request(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "corkysoft"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        captured["input"] = kwargs.get("input")
        return _Completed(stdout='{"ok": true, "result": {"jobCount": 3}}\n')

    monkeypatch.setattr(corkysoft_mcp.subprocess, "run", fake_run)

    response = corkysoft_mcp.call_tool(
        "corkysoft.profitability_summary",
        {"start_date": "2026-03-01"},
        repo_root=repo_root,
    )

    assert response["ok"] is True
    assert response["result"]["jobCount"] == 3
    assert captured["cmd"][:3] == [sys.executable, "-m", "corkysoft.mcp"]
    assert captured["cwd"] == repo_root
    payload = json.loads(str(captured["input"]).strip())
    assert payload["op"] == "call"
    assert payload["name"] == "corkysoft.profitability_summary"
    assert payload["payload"]["start_date"] == "2026-03-01"


def test_call_tool_raises_on_bridge_error(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "corkysoft"
    repo_root.mkdir()

    monkeypatch.setattr(
        corkysoft_mcp.subprocess,
        "run",
        lambda *args, **kwargs: _Completed(
            stdout='{"ok": false, "error": {"code": "input_error", "message": "bad payload"}}\n'
        ),
    )

    try:
        corkysoft_mcp.call_tool("corkysoft.quote_guidance_preview", {}, repo_root=repo_root)
    except corkysoft_mcp.CorkysoftMCPError as exc:
        assert "input_error: bad payload" in str(exc)
    else:
        raise AssertionError("expected CorkysoftMCPError")


def test_list_tools_rejects_invalid_json(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "corkysoft"
    repo_root.mkdir()

    monkeypatch.setattr(
        corkysoft_mcp.subprocess,
        "run",
        lambda *args, **kwargs: _Completed(stdout="not-json\n"),
    )

    try:
        corkysoft_mcp.list_tools(repo_root=repo_root)
    except corkysoft_mcp.CorkysoftMCPError as exc:
        assert "invalid json" in str(exc)
    else:
        raise AssertionError("expected CorkysoftMCPError")
