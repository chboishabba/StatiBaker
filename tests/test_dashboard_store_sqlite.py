from __future__ import annotations

import json
from pathlib import Path

import pytest


def _normalize_optional_summary(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _normalize_optional_summary(inner)
            for key, inner in value.items()
            if _normalize_optional_summary(inner) not in ({}, [], None)
        }
    if isinstance(value, list):
        normalized = [_normalize_optional_summary(item) for item in value]
        return [item for item in normalized if item not in ({}, [], None)]
    return value


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
        "runsheet_progress_summary": {"runners_total": 1, "top_level_completed": 1, "top_level_total": 2},
        "runsheet_progress_rows": [{"runner_id": "runner-1", "progress": {"completed": 1, "total": 2}}],
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
        "runsheet_progress_summary",
        "runsheet_progress_rows",
    ):
        if k == "chat_flow":
            loaded_chat = loaded.get("chat_flow") or {}
            payload_chat = payload.get("chat_flow") or {}
            for field in (
                "message_count",
                "thread_count",
                "switch_count",
                "switch_rate",
                "dominant_thread_share",
                "active_hours",
                "first_ts",
                "last_ts",
                "threads",
                "waterfall",
                "waterfall_render_limit",
                "waterfall_truncated",
                "hour_bins",
            ):
                left = loaded_chat.get(field)
                right = payload_chat.get(field)
                if field in {"threads", "waterfall"} and left is None and right == []:
                    left = []
                assert left == right
            continue
        if k == "chat_threads" and loaded.get(k) is None and payload.get(k) == []:
            continue
        if k in {"tool_use_summary", "notes_meta_summary", "runsheet_progress_summary", "runsheet_progress_rows"}:
            assert _normalize_optional_summary(loaded.get(k) or {}) == _normalize_optional_summary(
                payload.get(k) or {}
            )
            continue
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
        "runsheet_progress_summary",
        "runsheet_progress_rows",
    ):
        if k == "chat_flow":
            loaded_chat = loaded.get("chat_flow") or {}
            payload_chat = payload.get("chat_flow") or {}
            for field in (
                "message_count",
                "thread_count",
                "switch_count",
                "switch_rate",
                "dominant_thread_share",
                "active_hours",
                "first_ts",
                "last_ts",
                "threads",
                "waterfall",
                "waterfall_render_limit",
                "waterfall_truncated",
                "hour_bins",
            ):
                left = loaded_chat.get(field)
                right = payload_chat.get(field)
                if field in {"threads", "waterfall"} and left is None and right == []:
                    left = []
                assert left == right
            continue
        if k == "chat_threads" and loaded.get(k) is None and payload.get(k) == []:
            continue
        if k in {"tool_use_summary", "notes_meta_summary", "runsheet_progress_summary", "runsheet_progress_rows"}:
            assert _normalize_optional_summary(loaded.get(k) or {}) == _normalize_optional_summary(
                payload.get(k) or {}
            )
            continue
        assert loaded.get(k) == payload.get(k)


def test_build_timeline_ribbon_payload_orders_by_ts() -> None:
    from sb.dashboard_store_sqlite import build_timeline_ribbon_payload

    dailies = [
        {
            "date": "2026-02-08",
            "timeline": [
                {"ts": "2026-02-08T10:00:00Z", "kind": "chat", "detail": "later", "hour": 10},
                {"ts": "2026-02-08T08:00:00Z", "kind": "chat", "detail": "early", "hour": 8},
            ],
        },
        {
            "date": "2026-02-09",
            "timeline": [
                {"ts": "2026-02-09T09:00:00Z", "kind": "chat", "detail": "next-day", "hour": 9},
            ],
        },
    ]
    payload = build_timeline_ribbon_payload(dailies=dailies, start="2026-02-08", end="2026-02-09")

    assert payload["date"] == "2026-02-09"
    assert payload["period_start"] == "2026-02-08"
    assert payload["period_end"] == "2026-02-09"
    assert payload["days"] == 2
    timeline = payload.get("timeline") or []
    assert [row["detail"] for row in timeline] == ["early", "later", "next-day"]


def test_load_timeline_ribbon_rows_for_range_prefers_all_scope(tmp_path: Path) -> None:
    from sb.dashboard_store_sqlite import DashboardKey, load_timeline_ribbon_rows_for_range, upsert_dashboard_payload

    db_path = tmp_path / "dashboard.sqlite"
    upsert_dashboard_payload(
        db_path=db_path,
        key=DashboardKey(date="2026-02-08", view="daily", scope="scoped", window_days=0),
        payload={
            "date": "2026-02-08",
            "timeline": [{"ts": "2026-02-08T08:00:00Z", "hour": 8, "kind": "chat", "detail": "scoped"}],
        },
    )
    upsert_dashboard_payload(
        db_path=db_path,
        key=DashboardKey(date="2026-02-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-02-08",
            "timeline": [{"ts": "2026-02-08T09:00:00Z", "hour": 9, "kind": "chat", "detail": "all"}],
        },
    )

    rows = load_timeline_ribbon_rows_for_range(
        db_path=db_path,
        start="2026-02-08",
        end="2026-02-08",
        prefer_all=True,
    )

    assert len(rows) == 1
    assert rows[0]["scope"] == "all"
    payload = rows[0]["payload"]
    assert isinstance(payload, dict)
    timeline = payload.get("timeline") if isinstance(payload, dict) else None
    assert isinstance(timeline, list)
    assert timeline[0]["detail"] == "all"
