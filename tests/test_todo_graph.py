from __future__ import annotations

import subprocess
from pathlib import Path

from sb.todo_graph import analyze_repo_todos, discover_todo_files, parse_todo_file


def _write_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "TODO.md").write_text(
        "\n".join(
            [
                "# TODO",
                "## Active",
                "- [ ] Add `src/new_adapter.py` and wire `new_adapter` into the CLI",
                "- [x] Remove `legacy.py`",
                "- Add tests for adapter normalization",
                "## Completed",
                "- Document `README.md` changes",
                "Plain prose should not become an obligation.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "new_adapter.py").write_text("def new_adapter():\n    return 1\n", encoding="utf-8")
    (repo / "main.py").write_text("from src.new_adapter import new_adapter\n", encoding="utf-8")
    (repo / "README.md").write_text("# Docs\n", encoding="utf-8")
    (repo / "legacy.py").write_text("old = 1\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_adapter_normalization.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "logs" / "todo").mkdir(parents=True)
    (repo / "logs" / "todo" / "2026-03-24.md").write_text(
        "\n".join(
            [
                "# Daily TODO",
                "1. [ ] Add `src/daily.py`",
                "- [ ] Validate blocker handling @blocker",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "src" / "daily.py").write_text("daily = True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True, text=True)
    return repo


def test_parse_todo_file_extracts_bullets_and_ignores_prose(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    obligations = parse_todo_file(repo / "TODO.md", repo_root=repo)

    assert len(obligations) == 6
    assert obligations[0]["state"] == "open"
    assert obligations[1]["state"] == "checked_complete"
    assert obligations[3]["state"] == "checked_complete"
    assert all("Plain prose" not in item["text"] for item in obligations)




def test_discover_todo_files_includes_daily_logs(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    discovered = [str(path.relative_to(repo)) for path in discover_todo_files(repo)]
    assert "TODO.md" in discovered
    assert "logs/todo/2026-03-24.md" in discovered


def test_analyze_repo_todos_emits_candidates_and_alignment(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    payload = analyze_repo_todos(repo)

    assert payload["version"] == "todo_graph_v1"
    obligations = payload["obligations"]
    evaluations = payload["evaluations"]
    assert len(obligations) == 6
    by_text = {item["obligation"]["text"]: item for item in evaluations}

    assert by_text["Add `src/new_adapter.py` and wire `new_adapter` into the CLI"]["classification"] == "likely_complete"
    assert by_text["Remove `legacy.py`"]["classification"] == "contradicted"
    assert by_text["Add tests for adapter normalization"]["classification"] == "likely_complete"
    assert by_text["Document `README.md` changes"]["classification"] == "likely_complete"
    assert by_text["Add `src/daily.py`"]["obligation"]["source_kind"] == "daily_todo_log"
    assert by_text["Validate blocker handling @blocker"]["classification"] == "blocked"

    candidates = payload["completion_candidates"]
    assert len(candidates) == 4
    alignment = payload["alignment"]["project"]
    assert alignment["version"] == "todo_alignment_v1"
    assert alignment["task_alignment_score"] > 0
    assert alignment["penalty_counts"]["contradicted_obligations"] == 1
    assert alignment["penalty_counts"]["blocked_by_missing_evidence"] == 1
    assert payload["todo_predicates"]
    assert payload["todo_evidence_links"]
