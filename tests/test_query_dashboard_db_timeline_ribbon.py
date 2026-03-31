from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_query_dashboard_db_timeline_ribbon_projection(tmp_path: Path) -> None:
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    db_path = tmp_path / "dashboard.sqlite"
    upsert_dashboard_payload(
        db_path=db_path,
        key=DashboardKey(date="2026-02-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-02-08",
            "timeline": [{"ts": "2026-02-08T11:00:00Z", "hour": 11, "kind": "chat", "detail": "d1-late"}],
        },
    )
    upsert_dashboard_payload(
        db_path=db_path,
        key=DashboardKey(date="2026-02-09", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-02-09",
            "timeline": [{"ts": "2026-02-09T07:00:00Z", "hour": 7, "kind": "chat", "detail": "d2-early"}],
        },
    )

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "StatiBaker" / "scripts" / "query_dashboard_db.py"
    out = subprocess.check_output(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--view",
            "daily",
            "--start",
            "2026-02-08",
            "--end",
            "2026-02-09",
            "--prefer-all",
            "--projection",
            "timeline_ribbon",
        ],
        cwd=str(repo_root),
        text=True,
    )
    doc = json.loads(out)
    assert doc["rows_loaded"] == 2
    assert doc["dates_loaded"] == ["2026-02-08", "2026-02-09"]
    assert doc["payload"]["period_start"] == "2026-02-08"
    assert doc["payload"]["period_end"] == "2026-02-09"
    assert [row["detail"] for row in doc["payload"]["timeline"]] == ["d1-late", "d2-early"]


def test_query_dashboard_db_list_dates_falls_back_to_runs_root(tmp_path: Path) -> None:
    db_path = tmp_path / "missing-dashboard.sqlite"
    runs_root = tmp_path / "runs"
    (runs_root / "2026-02-08").mkdir(parents=True)
    (runs_root / "2026-02-10").mkdir(parents=True)
    (runs_root / "not-a-date").mkdir(parents=True)

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "StatiBaker" / "scripts" / "query_dashboard_db.py"
    out = subprocess.check_output(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--view",
            "daily",
            "--list-dates",
            "--runs-root",
            str(runs_root),
        ],
        cwd=str(repo_root),
        text=True,
    )
    dates = json.loads(out)
    assert dates == ["2026-02-08", "2026-02-10"]
