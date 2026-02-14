from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_dashboard_store_round_trip_minimal(tmp_path: Path) -> None:
    from sb.dashboard_store_sqlite import DashboardKey, load_dashboard_payload, upsert_dashboard_payload

    db_path = tmp_path / "dashboard.sqlite"
    key = DashboardKey(date="2026-02-08", view="daily", scope="all", window_days=0)
    payload = {
        "date": "2026-02-08",
        "generated_at": "2026-02-08T00:00:00Z",
        "period_start": "2026-02-01",
        "period_end": "2026-02-08",
        "days": 8,
        "chat_source": "sqlite",
        "chat_scope_mode": "scoped",
        "chat_scope_thread_count": 3,
        "warnings": ["w1", "w2"],
        "artifact_links": [{"label": "a", "path": "/tmp/a.txt"}],
        "frequency_by_hour": {"chat": [0] * 24, "shell": [1] * 24},
        "timeline": [
            {
                "ts": "2026-02-08T10:00:00Z",
                "hour": 10,
                "kind": "chat",
                "detail": "hello",
                "source_path": "/tmp/x",
                "meta": {"role": "user", "preview": "exec_command {\"cmd\":\"echo hi\"}"},
            }
        ],
        "chat_flow": {
            "message_count": 5,
            "thread_count": 1,
            "switch_count": 0,
            "switch_rate": 0.0,
            "dominant_thread_share": 1.0,
            "active_hours": 1,
            "first_ts": "2026-02-08T10:00:00Z",
            "last_ts": "2026-02-08T10:02:00Z",
            "hour_bins": [0] * 24,
            "threads": [{"thread_id": "t1", "thread_title": "T", "message_count": 5, "share": 1.0}],
            "waterfall": [
                {"ts": "2026-02-08T10:00:00Z", "hour": 10, "role": "user", "thread_id": "t1", "switch": False}
            ],
            "waterfall_render_limit": 400,
            "waterfall_truncated": False,
        },
        "chat_threads": [
            {
                "thread_id": "t1",
                "title": "Title",
                "origin": "codex",
                "message_count": 5,
                "first_ts": "2026-02-08T10:00:00Z",
                "last_ts": "2026-02-08T10:02:00Z",
                "first_user_preview": "hi",
                "roles": {"user": 2, "assistant": 3},
                "source_ids": ["codex_1", "codex_2"],
            }
        ],
        "summary": {"nested": {"a": 1, "b": [True, None, "x"]}},
        "tool_use_summary": {"families": [{"name": "git", "count": 2}]},
        "notes_meta_summary": {"lifecycle": {"notebook": {"created": 1}}},
    }

    upsert_dashboard_payload(db_path=db_path, key=key, payload=payload)
    loaded = load_dashboard_payload(db_path=db_path, key=key)
    assert loaded is not None

    # The store only persists known contract fields; ensure those round-trip.
    for k in (
        "date",
        "generated_at",
        "period_start",
        "period_end",
        "days",
        "chat_source",
        "chat_scope_mode",
        "chat_scope_thread_count",
        "warnings",
        "artifact_links",
        "frequency_by_hour",
        "timeline",
        "chat_flow",
        "chat_threads",
        "summary",
        "tool_use_summary",
        "notes_meta_summary",
    ):
        assert loaded.get(k) == payload.get(k)


@pytest.mark.skipif(
    not Path("StatiBaker/runs/2026-02-08/outputs/dashboard_all.json").exists(),
    reason="Repo-local dashboard JSON fixtures not present",
)
def test_dashboard_store_matches_existing_json_fixture(tmp_path: Path) -> None:
    from sb.dashboard_store_sqlite import DashboardKey, load_dashboard_payload, upsert_dashboard_payload

    fixture = Path("StatiBaker/runs/2026-02-08/outputs/dashboard_all.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    db_path = tmp_path / "dashboard.sqlite"
    key = DashboardKey(date=str(payload.get("date") or "2026-02-08"), view="daily", scope="all", window_days=0)
    upsert_dashboard_payload(db_path=db_path, key=key, payload=payload)

    loaded = load_dashboard_payload(db_path=db_path, key=key)
    assert loaded is not None

    # Compare only the stable contract keys (ignore legacy passthrough extras).
    for k in (
        "date",
        "generated_at",
        "period_start",
        "period_end",
        "days",
        "chat_source",
        "chat_scope_mode",
        "chat_scope_thread_count",
        "warnings",
        "artifact_links",
        "frequency_by_hour",
        "timeline",
        "chat_flow",
        "chat_threads",
        "summary",
        "tool_use_summary",
        "notes_meta_summary",
    ):
        assert loaded.get(k) == payload.get(k)

