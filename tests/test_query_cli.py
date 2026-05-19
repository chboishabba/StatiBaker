import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sb import query


class TestQuerySurface(unittest.TestCase):
    def test_carryover_summary(self):
        state = {
            "carryover_threads": ["a"],
            "carryover_new_threads": ["b"],
            "carryover_resolved_threads": [],
            "carryover_age_days": {"a": 2},
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(state, handle)
            handle.flush()
            payload = query.carryover_summary(handle.name)
        self.assertEqual(["a"], payload["carryover_threads"])
        self.assertEqual(["b"], payload["carryover_new_threads"])

    def test_provenance(self):
        state = {"sources": [{"kind": "git", "uri": "x"}]}
        ledger = {"provenance": {"algorithm": "sb.sessionize.v0"}}
        drift = {"provenance": {"algorithm": "sb.drift.v1"}}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as state_f, \
            tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as ledger_f, \
            tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as drift_f:
            json.dump(state, state_f)
            json.dump(ledger, ledger_f)
            json.dump(drift, drift_f)
            state_f.flush()
            ledger_f.flush()
            drift_f.flush()
            payload = query.provenance(state_f.name, ledger_f.name, drift_f.name)
        self.assertEqual("sb.sessionize.v0", payload["activity_ledger"]["algorithm"])
        self.assertEqual("sb.drift.v1", payload["drift"]["algorithm"])

    def test_commitment_feed(self):
        dashboard = {
            "external_commitment_summary": {"items_total": 1},
            "external_commitments": [{"external_item_id": "task-1"}],
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(dashboard, handle)
            handle.flush()
            payload = query.commitment_feed(handle.name)
        self.assertEqual(1, payload["summary"]["items_total"])
        self.assertEqual("task-1", payload["items"][0]["external_item_id"])

    def test_completion_candidates(self):
        dashboard = {
            "task_completion_candidates": [{"candidate_id": "cand-1"}],
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(dashboard, handle)
            handle.flush()
            payload = query.completion_candidates(handle.name)
        self.assertEqual("cand-1", payload["candidates"][0]["candidate_id"])

    def test_runsheet_progress(self):
        dashboard = {
            "runsheet_progress_summary": {"runners_total": 1, "top_level_completed": 1, "top_level_total": 2},
            "runsheet_progress_rows": [{"runner_id": "runner-1", "progress": {"completed": 1, "total": 2}}],
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(dashboard, handle)
            handle.flush()
            payload = query.runsheet_progress(handle.name)
        self.assertEqual(1, payload["summary"]["runners_total"])
        self.assertEqual("runner-1", payload["rows"][0]["runner_id"])

    def test_codex_trace_dashboard(self):
        dashboard = {
            "timeline": [{"ts": "2026-03-24T10:00:00Z", "kind": "chat", "detail": "hello", "source_path": "/tmp/x"}],
            "tool_use_summary": {"exec_command_count": 1},
            "chat_threads": [{"thread_id": "thread-1"}],
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(dashboard, handle)
            handle.flush()
            payload = query.codex_trace_dashboard(handle.name)
        self.assertEqual("codex_trace_facts_v1", payload["contract_version"])
        self.assertEqual("sb_dashboard", payload["source_route"])

    def test_codex_trace_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "archive.sqlite"
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE messages (
                      message_id TEXT PRIMARY KEY,
                      canonical_thread_id TEXT NOT NULL,
                      platform TEXT NOT NULL,
                      account_id TEXT NOT NULL,
                      ts TEXT NOT NULL,
                      role TEXT NOT NULL,
                      text TEXT NOT NULL,
                      title TEXT,
                      source_id TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO messages(message_id, canonical_thread_id, platform, account_id, ts, role, text, title, source_id)
                    VALUES ('m1', 'thread-1', 'codex', 'local', '2026-03-24T10:00:00Z', 'tool', 'exec_command {"cmd":"pytest"}', NULL, 'codex_1')
                    """
                )
                conn.commit()
            payload = query.codex_trace_archive(db_path, canonical_thread_id="thread-1")
        self.assertEqual("chat_archive", payload["source_route"])
        self.assertEqual(1, payload["tool_use"]["exec_command_count"])

    def test_todo_graph_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "TODO.md").write_text("- [ ] Add `src/app.py`\n", encoding="utf-8")
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")

            graph = query.todo_graph(repo)
            obligations = query.todo_obligations(repo)
            candidates = query.todo_candidates(repo)
            alignment = query.todo_alignment(repo)
            obligation = query.todo_obligation(repo, obligations["obligations"][0]["obligation_id"])

        self.assertEqual("todo_graph_v1", graph["version"])
        self.assertEqual(1, len(obligations["obligations"]))
        self.assertEqual(1, len(candidates["candidates"]))
        self.assertEqual("todo_alignment_v1", alignment["project"]["version"])
        self.assertEqual("todo_obligation_v1", obligation["obligation"]["version"])

    def test_runsheet_projection_with_runsheet_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_path = base / "status.sample.json"
            tasks_path = base / "tasks.json"
            tasks_path.write_text(
                json.dumps(
                    [
                        {"id": "read", "title": "Read context", "status": "done"},
                        {"id": "patch", "title": "Patch bridge", "status": "in_progress"},
                    ]
                ),
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "runsheet_source": {"path": "tasks.json"},
                        "orchestrator_id": "runner-1",
                    }
                ),
                encoding="utf-8",
            )

            projection = query.runsheet_projection(state_path, base_dir=base)

        self.assertTrue(projection["valid"])
        self.assertEqual("tasks", projection["source_kind"])
        self.assertEqual(2, projection["progress"]["total"])
        self.assertEqual("Patch bridge", projection["progress"]["current_milestone"])

    def test_kanboard_sync_report_query(self):
        report = {
            "schema_version": "sb.kanboard_sync_report.v0_1",
            "generated_at": "2026-05-19T14:00:00Z",
            "mode": "dry_run",
            "summary": {"creates": 1, "updates": 0, "moves": 0, "metadata": 1, "errors": 0},
            "progress": {"completed": 1, "total": 2},
            "external_references": {"kanboard_task_references": [{"stable_id": "a", "kanboard_reference": "a"}]},
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(report, handle)
            handle.flush()
            payload = query.kanboard_sync_report(handle.name)
        self.assertEqual("sb.kanboard_sync_report.v0_1", payload["schema_version"])
        self.assertEqual(1, payload["summary"]["creates"])

    def test_latest_kanboard_sync_report_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp) / "runs"
            older = runs_root / "2026-05-18" / "outputs"
            newer = runs_root / "2026-05-19" / "outputs"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            (older / "kanboard_sync_report.latest.json").write_text(
                json.dumps({"schema_version": "sb.kanboard_sync_report.v0_1", "summary": {"creates": 1}}),
                encoding="utf-8",
            )
            (newer / "kanboard_sync_report.latest.json").write_text(
                json.dumps({"schema_version": "sb.kanboard_sync_report.v0_1", "summary": {"creates": 2}}),
                encoding="utf-8",
            )
            payload = query.latest_kanboard_sync_report(runs_root)
        self.assertTrue(payload["found"])
        self.assertTrue(str(payload["path"]).endswith("2026-05-19/outputs/kanboard_sync_report.latest.json"))
        self.assertEqual(2, payload["report"]["summary"]["creates"])

    def test_kanboard_manager_wave_status_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status.statibaker-kanboard-stabilization-manager.json").write_text(
                json.dumps({"milestones_remaining": 0}),
                encoding="utf-8",
            )
            (root / "status.statibaker-kanboard-live-sync-manager.json").write_text(
                json.dumps(
                    {
                        "phase": "implementation",
                        "milestones_remaining": 1,
                        "runsheet": {"items": [{"id": "validation", "status": "blocked"}]},
                    }
                ),
                encoding="utf-8",
            )
            (root / "heartbeat.statibaker-kanboard-live-sync-manager.json").write_text(
                json.dumps({"state": 0, "phase": "done", "exit_code": 0}),
                encoding="utf-8",
            )

            payload = query.kanboard_manager_wave_status(root)

        self.assertEqual("sb.kanboard_manager_wave_status.v0_1", payload["schema_version"])
        self.assertTrue(payload["stabilization_status"]["closed"])
        self.assertEqual(1, payload["summary"]["reconcile_candidates"])
        candidate = next(item for item in payload["managers"] if item["status_file"].endswith("live-sync-manager.json"))
        self.assertTrue(candidate["reconcile_candidate"])
        self.assertEqual(["validation"], candidate["pending_items"])


if __name__ == "__main__":
    unittest.main()
