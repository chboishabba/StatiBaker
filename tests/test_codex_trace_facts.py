from __future__ import annotations

import json
from pathlib import Path

from sb.codex_trace import (
    core_trace_digest,
    facts_from_chat_archive_rows,
    facts_from_dashboard_payload,
    facts_from_raw_codex_logs,
)


def test_dashboard_trace_facts_include_commitments_and_candidates() -> None:
    payload = {
        "warnings": ["missing verification"],
        "timeline": [
            {
                "ts": "2026-03-24T10:00:00Z",
                "kind": "chat",
                "detail": "plan work",
                "source_path": "/tmp/a",
                "meta": {"role": "user"},
            },
            {
                "ts": "2026-03-24T10:01:00Z",
                "kind": "shell",
                "detail": "exec_command {\"cmd\":\"pytest\"}",
                "source_path": "/tmp/b",
                "meta": {"role": "tool"},
            },
        ],
        "tool_use_summary": {"request_user_input_count": 1, "exec_command_count": 2},
        "task_completion_candidates": [{"candidate_id": "cand-1"}],
        "external_commitments": [
            {"external_item_id": "task-1", "status": "needs_action"},
            {"external_item_id": "task-2", "status": "completed"},
        ],
        "chat_threads": [{"thread_id": "thread-1"}],
        "artifact_links": [{"label": "ledger", "path": "/tmp/out.json"}],
    }

    facts = facts_from_dashboard_payload(payload)

    assert facts["contract_version"] == "codex_trace_facts_v1"
    assert facts["source_route"] == "sb_dashboard"
    assert facts["tool_use"]["request_user_input_count"] == 1
    assert facts["tool_use"]["exec_command_count"] == 2
    assert facts["outcomes"]["completion_candidates"][0]["candidate_id"] == "cand-1"
    assert facts["outcomes"]["open_commitments"][0]["external_item_id"] == "task-1"
    assert facts["outcomes"]["completed_commitments"][0]["external_item_id"] == "task-2"


def test_chat_archive_and_raw_logs_share_core_digest(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    log_path = tmp_path / "codex.log"
    history_path.write_text(
        json.dumps(
            {
                "session_id": "thread-1",
                "ts": "2026-03-24T00:00:00Z",
                "text": "hello from user",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log_path.write_text(
        '2026-03-24T00:01:00Z thread_id=123e4567-e89b-12d3-a456-426614174000 ToolCall: exec_command {"cmd":"pytest"}\n',
        encoding="utf-8",
    )

    archive_rows = [
        {
            "canonical_thread_id": "thread-1",
            "platform": "codex",
            "account_id": "local",
            "ts": "2026-03-24T00:00:00Z",
            "role": "user",
            "text": "hello from user",
            "title": None,
            "source_id": "codex_history_jsonl",
        },
        {
            "canonical_thread_id": "123e4567-e89b-12d3-a456-426614174000",
            "platform": "codex",
            "account_id": "local",
            "ts": "2026-03-24T00:01:00Z",
            "role": "tool",
            "text": 'exec_command {"cmd":"pytest"}',
            "title": None,
            "source_id": "codex_tui_log",
        },
    ]

    archive_facts = facts_from_chat_archive_rows(archive_rows)
    raw_facts = facts_from_raw_codex_logs(history_path=history_path, log_path=log_path)

    assert core_trace_digest(archive_facts) == core_trace_digest(raw_facts)
    assert raw_facts["tool_use"]["exec_command_count"] == 1
    assert raw_facts["message_flow"]["user_count"] == 1
