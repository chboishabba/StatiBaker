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


if __name__ == "__main__":
    unittest.main()
