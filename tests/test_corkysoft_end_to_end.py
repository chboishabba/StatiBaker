from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb import query  # noqa: E402
from sb.corkysoft_ingest import persist_review_events  # noqa: E402
from sb.corkysoft_mcp import profitability_summary  # noqa: E402
from sb.dashboard import build_dashboard  # noqa: E402


CORKYSOFT_ROOT = Path(__file__).resolve().parents[3] / "corkysoft"
CORKYSOFT_VENV_PYTHON = CORKYSOFT_ROOT / "venv" / "bin" / "python"


@pytest.mark.skipif(not CORKYSOFT_ROOT.exists(), reason="local corkysoft repo not present")
@pytest.mark.skipif(not CORKYSOFT_VENV_PYTHON.exists(), reason="local corkysoft venv python not present")
def test_corkysoft_seeded_mcp_and_review_event_are_visible_in_dashboard() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        repo_root = tmp_path
        sb_root = repo_root / "StatiBaker"
        runs_root = sb_root / "runs"
        context_root = repo_root / "__CONTEXT"
        date = "2026-03-27"

        run_outputs = runs_root / date / "outputs"
        run_outputs.mkdir(parents=True, exist_ok=True)
        context_root.mkdir(parents=True, exist_ok=True)
        (context_root / "convo_ids.md").write_text("", encoding="utf-8")
        (run_outputs / "activity_ledger.json").write_text(
            json.dumps({"activity_events": [], "provenance": {}}),
            encoding="utf-8",
        )
        (run_outputs / "daily_brief.md").write_text("# brief\n", encoding="utf-8")
        (run_outputs / "retrospective.md").write_text("# retro\n", encoding="utf-8")
        (run_outputs / "state.json").write_text("{}", encoding="utf-8")
        (run_outputs / "drift.json").write_text("{}", encoding="utf-8")

        corkysoft_db = tmp_path / "corkysoft.sqlite"
        conn = sqlite3.connect(corkysoft_db)
        try:
            conn.executescript(
                """
                CREATE TABLE historical_jobs (
                    id INTEGER PRIMARY KEY,
                    price_per_m3 REAL,
                    revenue_total REAL,
                    volume_m3 REAL,
                    final_cost REAL,
                    distance_km REAL,
                    origin TEXT,
                    destination TEXT,
                    origin_postcode TEXT,
                    destination_postcode TEXT,
                    job_date TEXT
                );
                """
            )
            conn.executemany(
                """
                    INSERT INTO historical_jobs (
                    price_per_m3, revenue_total, volume_m3, final_cost, distance_km,
                    origin, destination, origin_postcode, destination_postcode, job_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (240.0, 2400.0, 10.0, 1800.0, 72.0, "Brisbane", "Gold Coast", "4000", "4217", "2026-03-20"),
                    (255.0, 2550.0, 10.0, 1900.0, 72.0, "Gold Coast", "Brisbane", "4217", "4000", "2026-03-21"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        mcp_response = profitability_summary(
            {"db_path": str(corkysoft_db), "start_date": "2026-03-01", "end_date": "2026-03-31"},
            repo_root=CORKYSOFT_ROOT,
            python_executable=str(CORKYSOFT_VENV_PYTHON),
        )
        assert mcp_response["ok"] is True
        assert mcp_response["result"]["jobCount"] == 2

        dashboard_db = runs_root / "dashboard.sqlite"
        persist_review_events(
            db_path=dashboard_db,
            records=[
                {
                    "event_id": "corkysoft:recon:2026-03-27",
                    "event_family": "reconciliation_exception",
                    "event_time": "2026-03-27T09:15:00Z",
                    "source_system": "corkysoft",
                    "actor_ref": "ops:reviewer",
                    "authority_class": "reviewed_summary",
                    "correlation_key": "recon:2026-03-27:job-77",
                    "summary": "Subcontractor bill mismatch remains unresolved for one move.",
                    "status": "open",
                    "object_refs": [{"job_id": "JOB-77"}, {"bill_review_id": "BILL-10"}],
                    "provenance_refs": [{"ref_kind": "ui_route", "ref_uri": "/operations-diary?job=JOB-77"}],
                    "evidence_refs": [{"event_id": "row-1", "source_id": "corkysoft-ui", "ref_kind": "bill_review"}],
                    "payload": {"exception_code": "supplier_bill_mismatch", "severity": "high"},
                }
            ],
        )

        payload = build_dashboard(
            date_text=date,
            repo_root=repo_root,
            runs_root=runs_root,
            context_root=context_root,
            convo_ids_path=context_root / "convo_ids.md",
            chat_db_path=tmp_path / "chat_archive.sqlite",
            chat_exports_dir=repo_root / "chat_exports",
            max_timeline_events=50,
        )

        assert payload["summary"]["itir_overlays_corkysoft_review_event_v1"] == 1
        assert payload["corkysoft_review_summary"]["by_family"]["reconciliation_exception"] == 1
        assert payload["corkysoft_review_events"][0]["object_refs"][0]["job_id"] == "JOB-77"

        dashboard_json = run_outputs / "dashboard.json"
        dashboard_json.write_text(json.dumps(payload), encoding="utf-8")
        feed = query.corkysoft_review_feed(dashboard_json)
        assert feed["summary"]["total"] == 1
        assert feed["items"][0]["event_family"] == "reconciliation_exception"
