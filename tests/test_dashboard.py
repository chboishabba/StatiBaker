import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sb.dashboard import (
    build_dashboard,
    build_weekly_dashboard,
    write_dashboard_outputs,
    write_weekly_outputs,
)


class TestDashboardBuild(unittest.TestCase):
    def test_build_dashboard_with_mixed_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            sb_root = repo_root / "StatiBaker"
            runs_root = sb_root / "runs"
            context_root = repo_root / "__CONTEXT"
            date = "2026-02-08"

            run_logs = runs_root / date / "logs"
            run_outputs = runs_root / date / "outputs"
            run_logs.mkdir(parents=True, exist_ok=True)
            run_outputs.mkdir(parents=True, exist_ok=True)
            (run_logs / "cli").mkdir(parents=True, exist_ok=True)
            (run_logs / "input").mkdir(parents=True, exist_ok=True)
            (run_logs / "windows").mkdir(parents=True, exist_ok=True)
            (run_logs / "git").mkdir(parents=True, exist_ok=True)
            (run_logs / "git_branch").mkdir(parents=True, exist_ok=True)
            (run_logs / "pr").mkdir(parents=True, exist_ok=True)
            (context_root / "last_sync").mkdir(parents=True, exist_ok=True)

            convo_id = "69882636-4404-839a-80cb-a2c770e25ae3"
            (context_root / "convo_ids.md").write_text(
                (
                    "| id | title | tail_lines | notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| {convo_id} | SB Context Pipeline | 100 | test |\n"
                ),
                encoding="utf-8",
            )

            (run_logs / "cli" / f"{date}.jsonl").write_text(
                '{"ts":"2026-02-08T06:02:00Z","cmd_hash":"abc","cwd_hash":"def","exit":0,"duration_ms":200}\n',
                encoding="utf-8",
            )
            (run_logs / "input" / f"{date}.jsonl").write_text(
                '{"ts":"2026-02-08T06:03:00Z","focus_app":"terminal","keys":{"text":10},"mouse":{"moves":5}}\n',
                encoding="utf-8",
            )
            (run_logs / "windows" / f"{date}.jsonl").write_text(
                '{"ts":"2026-02-08T06:04:00Z","app_id":"terminal","window_title_hash":"h1","duration_ms":120000}\n',
                encoding="utf-8",
            )
            (run_logs / "git" / f"{date}.jsonl").write_text(
                '{"ts":"2026-02-08T06:01:00Z","repo":"ITIR-suite","hash":"abcdef012345"}\n',
                encoding="utf-8",
            )
            (run_logs / "git_branch" / f"{date}.jsonl").write_text(
                '{"ts":"2026-02-08T06:01:30Z","signal":"git_branch","event_type":"branch_checkout","repo":"ITIR-suite","ref":"HEAD"}\n',
                encoding="utf-8",
            )
            (run_logs / "pr" / f"{date}.jsonl").write_text(
                (
                    '{"ts":"2026-02-08T06:02:30Z","signal":"pr_event","event_type":"pr_received","repo":"ITIR-suite","pr_number":7}\n'
                    '{"ts":"2026-02-08T06:03:30Z","signal":"pr_event","event_type":"pr_commented","repo":"ITIR-suite","pr_number":7}\n'
                    '{"ts":"2026-02-08T06:04:30Z","signal":"pr_event","event_type":"pr_merged","repo":"ITIR-suite","pr_number":7}\n'
                ),
                encoding="utf-8",
            )

            (run_outputs / "activity_ledger.json").write_text(
                json.dumps(
                    {
                        "activity_events": [
                            {
                                "id": "act-1",
                                "primary_app": "terminal",
                                "t_start": "2026-02-08T06:00:00Z",
                                "t_end": "2026-02-08T06:10:00Z",
                            }
                        ],
                        "provenance": {},
                    }
                ),
                encoding="utf-8",
            )
            (run_outputs / "daily_brief.md").write_text("# brief\n", encoding="utf-8")
            (run_outputs / "retrospective.md").write_text("# retro\n", encoding="utf-8")
            (run_outputs / "state.json").write_text("{}", encoding="utf-8")
            (run_outputs / "drift.json").write_text("{}", encoding="utf-8")
            (sb_root / "COMPACTIFIED_CONTEXT.md").parent.mkdir(parents=True, exist_ok=True)
            (sb_root / "COMPACTIFIED_CONTEXT.md").write_text("# compact\n", encoding="utf-8")
            (context_root / "CONTEXT.md").write_text("# ctx\n", encoding="utf-8")
            (context_root / "COMPACTIFIED_CONTEXT.md").write_text("# ctx compact\n", encoding="utf-8")

            resolver_payload = {
                "web_recent_turns_meta": {
                    "conversation_id": convo_id,
                    "title": "SB Context Pipeline",
                },
                "web_recent_turns": [
                    {
                        "position": 1,
                        "ts_utc": "2026-02-08T06:00:54.432000Z",
                        "role": "user",
                        "text": "Disambiguate temporal state",
                    },
                    {
                        "position": 2,
                        "ts_utc": "2026-02-08T06:00:55.680212Z",
                        "role": "assistant",
                        "text": "Definition of temporal state compilation",
                    },
                ],
            }
            (context_root / "last_sync" / "20260208T060100Z_resolver_69882636-4404-839a-80cb-a2c770e25ae3.json").write_text(
                json.dumps(resolver_payload),
                encoding="utf-8",
            )

            payload = build_dashboard(
                date_text=date,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=repo_root / "chat-export-structurer" / "my_archive.sqlite",
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=50,
            )

            self.assertEqual("resolver", payload["chat_source"])
            self.assertEqual(2, payload["summary"]["chat_messages"])
            self.assertEqual(1, payload["summary"]["chat_threads"])
            self.assertEqual(1, payload["summary"]["shell_commands"])
            self.assertEqual(1, payload["summary"]["input_events"])
            self.assertEqual(10, payload["summary"]["input_keys_total"])
            self.assertEqual(5, payload["summary"]["input_mouse_total"])
            self.assertEqual(1, payload["summary"]["window_focus_events"])
            self.assertEqual(1, payload["summary"]["activity_events"])
            self.assertEqual(1, payload["summary"]["git_commits"])
            self.assertEqual(1, payload["summary"]["git_branch_events"])
            self.assertEqual(3, payload["summary"]["pr_events"])
            self.assertEqual(1, payload["summary"]["pr_received"])
            self.assertEqual(1, payload["summary"]["pr_commented"])
            self.assertEqual(1, payload["summary"]["pr_merged"])
            self.assertEqual(2, payload["frequency_by_hour"]["chat"][6])
            self.assertEqual(1, payload["frequency_by_hour"]["git_branch"][6])
            self.assertEqual(3, payload["frequency_by_hour"]["pr"][6])

            link_paths = [item["path"] for item in payload["artifact_links"]]
            self.assertIn(str(run_outputs / "daily_brief.md"), link_paths)
            self.assertTrue(any(path.endswith("_resolver_69882636-4404-839a-80cb-a2c770e25ae3.json") for path in link_paths))

            json_out = run_outputs / "dashboard.json"
            html_out = run_outputs / "dashboard.html"
            write_dashboard_outputs(payload, json_path=json_out, html_path=html_out)
            self.assertTrue(json_out.exists())
            self.assertTrue(html_out.exists())

            loaded = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(date, loaded["date"])
            html_text = html_out.read_text(encoding="utf-8")
            self.assertIn("SB Activity Dashboard", html_text)
            self.assertIn("timeline-search", html_text)
            self.assertIn("Timeline</h2>", html_text)

    def test_build_dashboard_debug_includes_unscoped_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            sb_root = repo_root / "StatiBaker"
            runs_root = sb_root / "runs"
            context_root = repo_root / "__CONTEXT"
            date = "2026-02-08"

            run_logs = runs_root / date / "logs"
            run_outputs = runs_root / date / "outputs"
            run_logs.mkdir(parents=True, exist_ok=True)
            run_outputs.mkdir(parents=True, exist_ok=True)
            (context_root / "last_sync").mkdir(parents=True, exist_ok=True)

            scoped_convo_id = "11111111-1111-4111-8111-111111111111"
            resolver_convo_id = "22222222-2222-4222-8222-222222222222"
            (context_root / "convo_ids.md").write_text(
                (
                    "| id | title | tail_lines | notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| {scoped_convo_id} | Scoped Thread | 100 | test |\n"
                ),
                encoding="utf-8",
            )

            (run_outputs / "activity_ledger.json").write_text(
                json.dumps({"activity_events": [], "provenance": {}}),
                encoding="utf-8",
            )

            resolver_payload = {
                "web_recent_turns_meta": {
                    "conversation_id": resolver_convo_id,
                    "title": "Unscoped Thread",
                },
                "web_recent_turns": [
                    {
                        "position": 1,
                        "ts_utc": "2026-02-08T06:20:00Z",
                        "role": "user",
                        "text": "hello",
                    },
                    {
                        "position": 2,
                        "ts_utc": "2026-02-08T06:21:00Z",
                        "role": "assistant",
                        "text": "world",
                    },
                ],
            }
            resolver_path = (
                context_root
                / "last_sync"
                / "20260208T062100Z_resolver_22222222-2222-4222-8222-222222222222.json"
            )
            resolver_path.write_text(json.dumps(resolver_payload), encoding="utf-8")

            scoped_payload = build_dashboard(
                date_text=date,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=repo_root / "chat-export-structurer" / "my_archive.sqlite",
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=50,
                include_all_chat=False,
            )
            self.assertEqual("scoped", scoped_payload["chat_scope_mode"])
            self.assertEqual(0, scoped_payload["summary"]["chat_messages"])
            self.assertIn(
                "No chat events found for this date in sqlite, chat exports, or resolver files.",
                scoped_payload["warnings"],
            )

            debug_payload = build_dashboard(
                date_text=date,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=repo_root / "chat-export-structurer" / "my_archive.sqlite",
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=50,
                include_all_chat=True,
            )
            self.assertEqual("all", debug_payload["chat_scope_mode"])
            self.assertEqual(2, debug_payload["summary"]["chat_messages"])
            self.assertEqual("resolver", debug_payload["chat_source"])
            self.assertEqual(2, debug_payload["frequency_by_hour"]["chat"][6])
            self.assertIn(
                "Debug mode enabled: chat scope filter disabled (all chat threads scanned for this date).",
                debug_payload["warnings"],
            )
            link_paths = [item["path"] for item in debug_payload["artifact_links"]]
            self.assertIn(str(resolver_path), link_paths)

    def test_build_weekly_dashboard_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            sb_root = repo_root / "StatiBaker"
            runs_root = sb_root / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            (context_root / "convo_ids.md").write_text(
                "| id | title | tail_lines | notes |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )

            day_one = "2026-02-07"
            day_two = "2026-02-08"
            for date, commit_count, shell_count in ((day_one, 1, 1), (day_two, 2, 0)):
                logs_dir = runs_root / date / "logs"
                out_dir = runs_root / date / "outputs"
                (logs_dir / "git").mkdir(parents=True, exist_ok=True)
                (logs_dir / "cli").mkdir(parents=True, exist_ok=True)
                out_dir.mkdir(parents=True, exist_ok=True)

                git_lines = []
                for idx in range(commit_count):
                    git_lines.append(
                        json.dumps(
                            {
                                "ts": f"{date}T06:0{idx}:00Z",
                                "repo": "ITIR-suite",
                                "hash": f"abcdef012345{idx}",
                            }
                        )
                    )
                (logs_dir / "git" / f"{date}.jsonl").write_text(
                    "\n".join(git_lines) + ("\n" if git_lines else ""),
                    encoding="utf-8",
                )

                cli_lines = []
                for idx in range(shell_count):
                    cli_lines.append(
                        json.dumps(
                            {
                                "ts": f"{date}T06:1{idx}:00Z",
                                "cmd_hash": f"cmd{idx}",
                                "exit": 0,
                                "duration_ms": 100,
                            }
                        )
                    )
                (logs_dir / "cli" / f"{date}.jsonl").write_text(
                    "\n".join(cli_lines) + ("\n" if cli_lines else ""),
                    encoding="utf-8",
                )

                (out_dir / "activity_ledger.json").write_text(
                    json.dumps(
                        {
                            "activity_events": [
                                {
                                    "id": f"act-{date}",
                                    "primary_app": "terminal",
                                    "t_start": f"{date}T08:00:00Z",
                                    "t_end": f"{date}T08:05:00Z",
                                }
                            ],
                            "provenance": {},
                        }
                    ),
                    encoding="utf-8",
                )
                (out_dir / "daily_brief.md").write_text("# brief\n", encoding="utf-8")
                (out_dir / "retrospective.md").write_text("# retro\n", encoding="utf-8")
                (out_dir / "state.json").write_text("{}", encoding="utf-8")
                (out_dir / "drift.json").write_text("{}", encoding="utf-8")

            payload = build_weekly_dashboard(
                end_date_text=day_two,
                days=2,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=repo_root / "chat-export-structurer" / "my_archive.sqlite",
                chat_exports_dir=repo_root / "chat_exports",
            )

            self.assertEqual(day_one, payload["period_start"])
            self.assertEqual(day_two, payload["period_end"])
            self.assertEqual(2, payload["days"])
            self.assertEqual(3, payload["totals"]["git_commits"])
            self.assertEqual(1, payload["totals"]["shell_commands"])
            self.assertEqual(2, payload["totals"]["activity_events"])
            self.assertEqual(2, len(payload["daily"]))

            weekly_json = runs_root / day_two / "outputs" / "dashboard_weekly_2d.json"
            weekly_html = runs_root / day_two / "outputs" / "dashboard_weekly_2d.html"
            write_weekly_outputs(payload, json_path=weekly_json, html_path=weekly_html)
            self.assertTrue(weekly_json.exists())
            self.assertTrue(weekly_html.exists())
            self.assertIn(
                "SB Weekly Dashboard",
                weekly_html.read_text(encoding="utf-8"),
            )

    def test_tool_use_summary_groups_commands_and_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            thread_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            (context_root / "convo_ids.md").write_text(
                (
                    "| id | title | tail_lines | notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| {thread_id} | Tool Thread | 100 | test |\n"
                ),
                encoding="utf-8",
            )
            date = "2026-02-08"
            out_dir = runs_root / date / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "activity_ledger.json").write_text(
                json.dumps({"activity_events": [], "provenance": {}}),
                encoding="utf-8",
            )

            db_path = repo_root / "chat-export-structurer" / "my_archive.sqlite"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE messages (
                  message_id TEXT PRIMARY KEY,
                  canonical_thread_id TEXT,
                  platform TEXT,
                  account_id TEXT,
                  ts TEXT,
                  role TEXT,
                  text TEXT,
                  title TEXT,
                  source_id TEXT
                )
                """
            )
            rows = [
                (
                    "m1",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T10:00:00+00:00",
                    "tool",
                    'exec_command {"cmd":"python scripts/build_dashboard.py --date 2026-02-08","workdir":"/repo/StatiBaker"}',
                    "",
                    "src",
                ),
                (
                    "m2",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T10:01:00+00:00",
                    "tool",
                    'exec_command {"cmd":"python scripts/build_dashboard.py --date 2026-02-07","workdir":"/repo/StatiBaker"}',
                    "",
                    "src",
                ),
                (
                    "m3",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T10:02:00+00:00",
                    "tool",
                    'exec_command {"cmd":"git status","workdir":"/repo/StatiBaker"}',
                    "",
                    "src",
                ),
            ]
            cur.executemany(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            con.commit()
            con.close()

            payload = build_dashboard(
                date_text=date,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=db_path,
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=100,
                include_all_chat=False,
            )

            summary = payload.get("tool_use_summary") or {}
            self.assertEqual("sqlite", summary.get("source"))
            self.assertEqual(3, summary.get("total_tool_messages"))
            self.assertEqual(3, summary.get("exec_command_count"))
            self.assertEqual(3, summary.get("unique_commands"))

            families = {item["family"]: item for item in summary.get("families") or []}
            self.assertIn("python build_dashboard.py", families)
            self.assertEqual(2, families["python build_dashboard.py"]["count"])
            self.assertIn("git status", families)

    def test_untitled_sqlite_thread_uses_first_user_preview_and_codex_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            (context_root / "convo_ids.md").write_text(
                "| id | title | tail_lines | notes |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
            date = "2026-02-08"
            out_dir = runs_root / date / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "activity_ledger.json").write_text(
                json.dumps({"activity_events": [], "provenance": {}}),
                encoding="utf-8",
            )

            db_path = repo_root / "chat-export-structurer" / "my_archive.sqlite"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE messages (
                  message_id TEXT PRIMARY KEY,
                  canonical_thread_id TEXT,
                  platform TEXT,
                  account_id TEXT,
                  ts TEXT,
                  role TEXT,
                  text TEXT,
                  title TEXT,
                  source_id TEXT
                )
                """
            )
            thread_id = "dff2e608e358fe5ed5cf1d0376a36ff8a87a6f2d"
            rows = [
                (
                    "m1",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T09:00:00+00:00",
                    "user",
                    "this should become fallback title for untitled thread",
                    "",
                    "codex_0001",
                ),
                (
                    "m2",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T09:01:00+00:00",
                    "tool",
                    'exec_command {"cmd":"git status"}',
                    "",
                    "codex_0001",
                ),
            ]
            cur.executemany(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            con.commit()
            con.close()

            payload = build_dashboard(
                date_text=date,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=db_path,
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=100,
                include_all_chat=True,
            )

            self.assertEqual("sqlite", payload["chat_source"])
            self.assertEqual(2, payload["summary"]["chat_messages"])
            self.assertEqual(1, payload["summary"]["chat_threads"])
            thread = payload["chat_threads"][0]
            self.assertEqual("codex-ingest", thread["origin"])
            self.assertTrue(str(thread["title_resolved"]).startswith("(untitled) this should become fallback title"))

            out_html = runs_root / date / "outputs" / "dashboard.html"
            out_json = runs_root / date / "outputs" / "dashboard.json"
            write_dashboard_outputs(payload, json_path=out_json, html_path=out_html)
            html_text = out_html.read_text(encoding="utf-8")
            self.assertIn("codex-ingest", html_text)
            self.assertIn("timeline-reset", html_text)

    def test_tool_use_summary_groups_rg_by_mode_and_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            (context_root / "convo_ids.md").write_text(
                "| id | title | tail_lines | notes |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
            date = "2026-02-08"
            out_dir = runs_root / date / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "activity_ledger.json").write_text(
                json.dumps({"activity_events": [], "provenance": {}}),
                encoding="utf-8",
            )

            db_path = repo_root / "chat-export-structurer" / "my_archive.sqlite"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE messages (
                  message_id TEXT PRIMARY KEY,
                  canonical_thread_id TEXT,
                  platform TEXT,
                  account_id TEXT,
                  ts TEXT,
                  role TEXT,
                  text TEXT,
                  title TEXT,
                  source_id TEXT
                )
                """
            )
            thread_id = "0123456789abcdef0123456789abcdef01234567"
            rows = [
                (
                    "m1",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T10:00:00+00:00",
                    "tool",
                    'exec_command {"cmd":"rg --files -g \'*CONTEXT.md\'","workdir":"/repo"}',
                    "",
                    "codex_0001",
                ),
                (
                    "m2",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T10:01:00+00:00",
                    "tool",
                    'exec_command {"cmd":"rg --files -g \'context-sources.md\'","workdir":"/repo"}',
                    "",
                    "codex_0001",
                ),
                (
                    "m3",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T10:02:00+00:00",
                    "tool",
                    'exec_command {"cmd":"rg -n \\"crossdoc.v1\\" SensibLaw","workdir":"/repo"}',
                    "",
                    "codex_0001",
                ),
            ]
            cur.executemany(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            con.commit()
            con.close()

            payload = build_dashboard(
                date_text=date,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=db_path,
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=100,
                include_all_chat=True,
            )

            summary = payload.get("tool_use_summary") or {}
            families = {item["family"]: item for item in summary.get("families") or []}
            self.assertIn("rg", families)
            rg_family = families["rg"]
            groups = {item["group"]: item for item in rg_family.get("variant_groups") or []}
            self.assertIn("--files", groups)
            self.assertIn("-n", groups)
            files_variants = " ".join(
                str(item.get("detail") or "")
                for item in groups["--files"].get("variants") or []
            )
            self.assertIn("*CONTEXT.md", files_variants)
            self.assertIn("context-sources.md", files_variants)


if __name__ == "__main__":
    unittest.main()
