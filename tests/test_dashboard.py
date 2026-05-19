import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sb.dashboard import (
    build_lifetime_costing_payload,
    build_dashboard,
    build_lifetime_dashboard,
    build_weekly_dashboard,
    write_costing_outputs,
    write_dashboard_outputs,
    write_lifetime_outputs,
    write_weekly_outputs,
)

# Use a per-test sqlite DB under a temp dir to avoid cross-test collisions.
# Default placeholder. Individual tests should pass an isolated sqlite path.
CHAT_ARCHIVE_PATH = None


def _chat_db_path(tmp: str | None, repo_root: Path | None) -> Path:
    # Prefer per-test temp dir when available, else fall back to repo_root.
    if tmp:
        return Path(tmp) / "chat_archive.sqlite"
    if repo_root is not None:
        return repo_root / "chat_archive.sqlite"
    # Should never happen in these tests.
    return Path("chat_archive.sqlite")


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
            (run_logs / "media").mkdir(parents=True, exist_ok=True)
            (run_logs / "openrecall").mkdir(parents=True, exist_ok=True)
            (run_logs / "commitments").mkdir(parents=True, exist_ok=True)
            (run_logs / "context").mkdir(parents=True, exist_ok=True)
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
            (run_logs / "media" / f"{date}.jsonl").write_text(
                (
                    '{"ts":"2026-02-08T06:05:00Z","signal":"media_consumption","platform":"youtube","event_type":"playback_observed","item_id_hash":"sha256:item1","consumed_seconds":20,"content_duration_seconds":120,"completion_ratio":0.167}\n'
                    '{"ts":"2026-02-08T06:10:00Z","signal":"media_consumption","platform":"spotify","event_type":"playback_observed","item_id_hash":"sha256:item2","consumed_seconds":120,"content_duration_seconds":120,"completion_ratio":1.0}\n'
                ),
                encoding="utf-8",
            )
            (run_logs / "openrecall" / f"{date}.jsonl").write_text(
                (
                    '{"ts":"2026-02-08T06:06:00Z","signal":"openrecall_activity","captured_date":"2026-02-08","timestamp":1770530760,"entry_id":7,"app":"firefox","window_title":"GitHub pull request","ocr_preview":"Reviewing OpenRecall adapter wiring","activity_kind":"research_activity","screenshot_present":true,"capture_count":1,"source_ref":"openrecall.entry:7","deep_link":"http://127.0.0.1:8082/entry/7","device_id":"workstation-a","session_id":"session-1","provenance":{"source":"openrecall_activity","collected_at":"2026-02-08T06:06:00Z"}}\n'
                ),
                encoding="utf-8",
            )
            (run_logs / "commitments" / f"{date}.jsonl").write_text(
                (
                    '{"ts":"2026-02-08T06:06:00Z","signal":"external_commitment","version":"external_commitment_event_v1","source_system":"google","source_kind":"google_tasks_task","external_account_id":"acct","external_list_id":"tasks","external_item_id":"task-1","title":"Write dashboard docs","status":"open","voice_origin":"tasks_command","provenance":{"source":"test","collected_at":"2026-02-08T06:06:01Z"}}\n'
                    '{"ts":"2026-02-08T06:07:00Z","signal":"external_commitment","version":"external_commitment_event_v1","source_system":"google","source_kind":"google_keep_list_item","external_account_id":"acct","external_list_id":"keep","external_item_id":"keep-1","title":"Buy milk","status":"completed","voice_origin":"keep_list","provenance":{"source":"test","collected_at":"2026-02-08T06:07:01Z"}}\n'
                ),
                encoding="utf-8",
            )
            (run_logs / "context" / f"{date}.jsonl").write_text(
                (
                    '{"ts":"2026-02-08T05:10:00Z","signal":"context_field","context_type":"mood","event_type":"report_logged","mood_code":"stressed","stress_score":8,"provenance":{"source":"test","collected_at":"2026-02-08T05:10:01Z"}}\n'
                    '{"ts":"2026-02-08T05:20:00Z","signal":"context_field","context_type":"inaturalist","event_type":"observation_observed","taxon_id_hash":"sha256:taxon1","iconic_taxon_code":"insecta","insect_flag":1,"obs_count":2,"provenance":{"source":"test","collected_at":"2026-02-08T05:20:01Z"}}\n'
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
                                "title": "Write dashboard docs",
                                "key_text": ["Write dashboard docs", "finish docs"],
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
            (repo_root / "status.statibaker-test-manager.json").write_text(
                json.dumps(
                    {
                        "orchestrator_id": "statibaker-test-manager",
                        "phase": "implementation",
                        "active_checklist": "Finish test lane",
                        "runsheet": {
                            "items": [
                                {"id": "inspect", "title": "Inspect lane", "status": "done"},
                                {"id": "implement", "title": "Implement lane", "status": "in_progress"},
                                {"id": "report", "title": "Report lane", "status": "todo"},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / "heartbeat.statibaker-test-manager.json").write_text(
                json.dumps(
                    {
                        "last_heartbeat": "2026-02-08T06:11:00Z",
                        "phase": "implementing",
                        "current_step": "running tests",
                        "state": 2,
                    }
                ),
                encoding="utf-8",
            )

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
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=50,
            )

            self.assertEqual("resolver", payload["chat_source"])
            self.assertEqual(2, payload["summary"]["chat_messages"])
            self.assertEqual(1, payload["summary"]["chat_threads"])
            self.assertEqual(1, payload["summary"]["chat_active_hours"])
            self.assertAlmostEqual(2.0, payload["summary"]["messages_per_hour_active"], places=2)
            self.assertAlmostEqual(2.0, payload["summary"]["messages_per_chat"], places=2)
            self.assertEqual(0, payload["summary"]["chat_switches"])
            self.assertAlmostEqual(0.0, payload["summary"]["context_switch_rate"], places=3)
            self.assertAlmostEqual(0.0, payload["summary"]["switches_per_active_hour"], places=2)
            self.assertAlmostEqual(1.0, payload["summary"]["top_thread_share"], places=3)
            self.assertEqual(1, payload["summary"]["shell_commands"])
            self.assertEqual(2, payload["summary"]["media_events"])
            self.assertEqual(2, payload["summary"]["media_items_observed"])
            self.assertEqual(140, payload["summary"]["media_consumed_seconds"])
            self.assertEqual(240, payload["summary"]["media_content_seconds"])
            self.assertAlmostEqual(0.583, payload["summary"]["media_completion_ratio"], places=3)
            self.assertEqual(1, payload["summary"]["media_churn_events"])
            self.assertAlmostEqual(0.5, payload["summary"]["media_churn_rate"], places=3)
            self.assertGreater(payload["summary"]["chat_tokens_est"], 0)
            self.assertGreater(payload["summary"]["chat_input_tokens_est"], 0)
            self.assertGreater(payload["summary"]["chat_output_tokens_est"], 0)
            self.assertEqual(128000, payload["summary"]["chat_context_default_window_tokens"])
            self.assertEqual(0, payload["summary"]["chat_context_overflow_threads"])
            self.assertEqual(300, payload["summary"]["concurrency_window_seconds"])
            self.assertEqual(2, payload["summary"]["inaturalist_insect_observations"])
            self.assertEqual(1, payload["summary"]["mood_reports"])
            self.assertEqual(1, payload["summary"]["chat_media_overlap_hours"])
            self.assertAlmostEqual(1.0, payload["summary"]["chat_media_overlap_rate"], places=3)
            self.assertEqual(1, payload["summary"]["chat_input_overlap_hours"])
            self.assertAlmostEqual(1.0, payload["summary"]["chat_input_overlap_rate"], places=3)
            self.assertEqual(1, payload["summary"]["chat_activity_overlap_hours"])
            self.assertAlmostEqual(1.0, payload["summary"]["chat_activity_overlap_rate"], places=3)
            self.assertEqual(2, payload["summary"]["chat_messages_with_media_nearby"])
            self.assertAlmostEqual(1.0, payload["summary"]["chat_messages_with_media_nearby_rate"], places=3)
            self.assertEqual(0, payload["summary"]["voice_activity_events"])
            self.assertEqual(0, payload["summary"]["chat_messages_with_voice_activity_nearby"])
            self.assertAlmostEqual(0.0, payload["summary"]["chat_messages_with_voice_activity_nearby_rate"], places=3)
            self.assertEqual(1, payload["summary"]["input_events"])
            self.assertEqual(10, payload["summary"]["input_keys_total"])
            self.assertEqual(5, payload["summary"]["input_mouse_total"])
            self.assertEqual(1, payload["summary"]["window_focus_events"])
            self.assertEqual(1, payload["summary"]["activity_events"])
            self.assertEqual(1, payload["summary"]["openrecall_events"])
            self.assertEqual(1, payload["summary"]["openrecall_devices"])
            self.assertEqual(1, payload["summary"]["git_commits"])
            self.assertEqual(1, payload["summary"]["git_branch_events"])
            self.assertEqual(3, payload["summary"]["pr_events"])
            self.assertEqual(1, payload["summary"]["pr_received"])
            self.assertEqual(1, payload["summary"]["pr_commented"])
            self.assertEqual(1, payload["summary"]["pr_merged"])
            self.assertEqual(2, payload["summary"]["external_commitments_total"])
            self.assertEqual(1, payload["summary"]["external_commitments_open"])
            self.assertEqual(1, payload["summary"]["external_commitments_completed"])
            self.assertEqual(1, payload["summary"]["task_completion_candidates_proposed"])
            self.assertEqual(1, payload["summary"]["runsheet_runners_total"])
            self.assertEqual(1, payload["summary"]["runsheet_items_done"])
            self.assertEqual(1, payload["summary"]["runsheet_items_in_progress"])
            self.assertEqual(1, payload["summary"]["runsheet_items_todo"])
            self.assertEqual(1, payload["summary"]["runsheet_top_level_completed"])
            self.assertEqual(3, payload["summary"]["runsheet_top_level_total"])
            self.assertEqual(2, payload["frequency_by_hour"]["chat"][6])
            self.assertEqual(1, payload["frequency_by_hour"]["git"][6])
            self.assertEqual(1, payload["frequency_by_hour"]["activity"][6])
            self.assertEqual(1, payload["frequency_by_hour"]["git_branch"][6])
            self.assertEqual(3, payload["frequency_by_hour"]["pr"][6])
            self.assertEqual(2, payload["frequency_by_hour"]["media"][6])
            self.assertEqual(1, payload["frequency_by_hour"]["openrecall"][6])
            self.assertEqual(2, payload["chat_flow"]["message_count"])
            self.assertEqual(1, payload["chat_flow"]["thread_count"])
            self.assertEqual(0, payload["chat_flow"]["switch_count"])
            self.assertEqual(2, len(payload["chat_flow"]["waterfall"]))
            self.assertEqual(2, len(payload["external_commitments"]))
            self.assertEqual(1, len(payload["task_completion_candidates"]))
            open_commitment = next(
                item for item in payload["external_commitments"] if item["external_item_id"] == "task-1"
            )
            self.assertEqual("candidate_complete", open_commitment["projection_lane"])
            self.assertEqual(0, payload["chat_context_trailing"]["available_days"])
            self.assertFalse(payload["chat_context_trailing"]["has_baseline"])

            link_paths = [item["path"] for item in payload["artifact_links"]]
            self.assertIn(str(run_outputs / "daily_brief.md"), link_paths)
            self.assertTrue(any(path.endswith("_resolver_69882636-4404-839a-80cb-a2c770e25ae3.json") for path in link_paths))

            json_out = run_outputs / "dashboard.json"
            html_out = run_outputs / "dashboard.html"
            write_dashboard_outputs(payload, json_path=json_out, html_path=html_out)
            self.assertTrue(json_out.exists())
            self.assertTrue(html_out.exists())
            html_text = html_out.read_text(encoding="utf-8")
            self.assertIn("http://127.0.0.1:8082/entry/7", html_text)
            self.assertIn("research_activity", html_text)
            self.assertIn("Commitment Feed", html_text)
            self.assertIn("Task Completion Candidates", html_text)
            self.assertIn("Local Runsheet Progress", html_text)
            self.assertIn("1/3", html_text)

            loaded = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(date, loaded["date"])
            html_text = html_out.read_text(encoding="utf-8")
            self.assertIn("SB Activity Dashboard", html_text)
            self.assertIn("Messages/chat", html_text)
            self.assertIn("Observer Overlays", html_text)
            self.assertIn("StatiBaker", html_text)
            self.assertIn("SensibLaw", html_text)
            self.assertIn("casey-git-clone", html_text)
            self.assertIn("TiRC (transcript and recording)", html_text)
            self.assertIn("Fuzzymodo", html_text)
            self.assertIn("Chat Flow Visualizations", html_text)
            self.assertIn("table-scroll", html_text)
            self.assertIn("--wf-gap:", html_text)
            self.assertIn("data-gap-sec=", html_text)
            self.assertIn("wf-view-mode", html_text)
            self.assertIn("Legacy / Linear", html_text)
            self.assertIn("Actual Waterfall", html_text)
            self.assertIn("wf-palette", html_text)
            self.assertIn("wf-color-algo", html_text)
            self.assertIn("Turbo (Rainbow)", html_text)
            self.assertIn("Time of Day", html_text)
            self.assertIn("% of chat messages", html_text)
            self.assertIn("Chat Context Usage (Estimated)", html_text)
            self.assertIn("Context overflow (est)", html_text)
            self.assertIn("Media/hour", html_text)
            self.assertIn("Commits/hour", html_text)
            self.assertIn("Activity/hour", html_text)
            self.assertIn("Media completion/churn", html_text)
            self.assertIn("iNaturalist insects", html_text)
            self.assertIn("Mood reports", html_text)
            self.assertIn("Chat-media overlap", html_text)
            self.assertIn("Voice/transcribe overlap", html_text)
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
                chat_db_path=_chat_db_path(tmp, repo_root),
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
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=50,
                include_all_chat=True,
            )
            self.assertEqual("all", debug_payload["chat_scope_mode"])
            self.assertEqual(2, debug_payload["summary"]["chat_messages"])
            self.assertEqual(0, debug_payload["summary"]["chat_switches"])
            self.assertAlmostEqual(0.0, debug_payload["summary"]["context_switch_rate"], places=3)
            self.assertEqual("resolver", debug_payload["chat_source"])
            self.assertEqual(2, debug_payload["frequency_by_hour"]["chat"][6])
            self.assertIn(
                "Debug mode enabled: chat scope filter disabled (all chat threads scanned for this date).",
                debug_payload["warnings"],
            )
            link_paths = [item["path"] for item in debug_payload["artifact_links"]]
            self.assertIn(str(resolver_path), link_paths)

    def test_build_dashboard_parses_agent_edit_activity(self):
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
                    f"| {thread_id} | Agent Edit Thread | 100 | test |\n"
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

            db_path = _chat_db_path(tmp, repo_root)
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
            assistant_text = (
                "• Edited docs/planning/assumption_stress_test_20260208.md (+9 -1)\n"
                "    25  | prior line\n"
                "    26 +| new line\n"
                "• Edited TODO.md (+5 -0)\n"
                "    28  - existing\n"
                "    29 +  - new\n"
            )
            rows = [
                ("m1", thread_id, "chatgpt", "main", f"{date}T10:00:00+00:00", "user", "please patch docs", "Agent Edit Thread", "src"),
                ("m2", thread_id, "chatgpt", "main", f"{date}T10:01:00+00:00", "assistant", assistant_text, "Agent Edit Thread", "src"),
            ]
            cur.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
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

            self.assertEqual(2, payload["summary"]["agent_edit_blocks"])
            self.assertEqual(2, payload["summary"]["agent_edit_files"])
            self.assertEqual(14, payload["summary"]["agent_edit_lines_added"])
            self.assertEqual(1, payload["summary"]["agent_edit_lines_removed"])
            self.assertAlmostEqual(0.667, payload["summary"]["agent_edit_top_file_share"], places=3)
            agent_summary = payload.get("agent_edit_summary") or {}
            self.assertEqual("sqlite", agent_summary.get("source"))
            self.assertEqual(1, agent_summary.get("messages_with_edits"))
            files = agent_summary.get("files") or []
            self.assertEqual("docs/planning/assumption_stress_test_20260208.md", files[0].get("path"))
            self.assertIn(25, files[0].get("line_numbers"))
            self.assertIn(26, files[0].get("line_numbers"))

            out_json = runs_root / date / "outputs" / "dashboard.json"
            out_html = runs_root / date / "outputs" / "dashboard.html"
            write_dashboard_outputs(payload, json_path=out_json, html_path=out_html)
            html_text = out_html.read_text(encoding="utf-8")
            self.assertIn("Agent Edit Activity", html_text)
            self.assertIn("docs/planning/assumption_stress_test_20260208.md", html_text)
            self.assertIn("25, 26", html_text)

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
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
            )

            self.assertEqual(day_one, payload["period_start"])
            self.assertEqual(day_two, payload["period_end"])
            self.assertEqual(2, payload["days"])
            self.assertEqual(3, payload["totals"]["git_commits"])
            self.assertEqual(1, payload["totals"]["shell_commands"])
            self.assertEqual(2, payload["totals"]["activity_events"])
            self.assertIn("weekday_hour_heatmaps", payload)
            self.assertIn("series", payload["weekday_hour_heatmaps"])
            self.assertIn("chat_context_averages", payload)
            self.assertIn("context_switch_rate", payload["chat_context_averages"])
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
            self.assertIn(
                "When You Work (Weekday x Hour)",
                weekly_html.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "By weekday (avg/day)",
                weekly_html.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Switch Rate",
                weekly_html.read_text(encoding="utf-8"),
            )

    def test_weekly_and_lifetime_media_rollups(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            (context_root / "convo_ids.md").write_text(
                "| id | title | tail_lines | notes |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )

            day_one = "2026-02-07"
            day_two = "2026-02-08"
            media_rows = {
                day_one: [
                    {
                        "ts": f"{day_one}T06:00:00Z",
                        "signal": "media_consumption",
                        "platform": "youtube",
                        "event_type": "playback_observed",
                        "item_id_hash": "sha256:item-a",
                        "consumed_seconds": 50,
                        "content_duration_seconds": 200,
                        "completion_ratio": 0.25,
                    },
                    {
                        "ts": f"{day_one}T06:05:00Z",
                        "signal": "media_consumption",
                        "platform": "spotify",
                        "event_type": "playback_observed",
                        "item_id_hash": "sha256:item-b",
                        "consumed_seconds": 100,
                        "content_duration_seconds": 100,
                        "completion_ratio": 1.0,
                    },
                ],
                day_two: [
                    {
                        "ts": f"{day_two}T07:00:00Z",
                        "signal": "media_consumption",
                        "platform": "vlc",
                        "event_type": "playback_observed",
                        "item_id_hash": "sha256:item-c",
                        "consumed_seconds": 120,
                        "content_duration_seconds": 240,
                        "completion_ratio": 0.5,
                    },
                ],
            }
            for date in (day_one, day_two):
                logs_dir = runs_root / date / "logs" / "media"
                out_dir = runs_root / date / "outputs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                out_dir.mkdir(parents=True, exist_ok=True)
                (logs_dir / f"{date}.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in media_rows[date]),
                    encoding="utf-8",
                )
                (out_dir / "activity_ledger.json").write_text(
                    json.dumps({"activity_events": [], "provenance": {}}),
                    encoding="utf-8",
                )

            weekly_payload = build_weekly_dashboard(
                end_date_text=day_two,
                days=2,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
            )
            self.assertEqual(3, weekly_payload["totals"]["media_events"])
            self.assertEqual(3, weekly_payload["totals"]["media_items_observed"])
            self.assertEqual(270, weekly_payload["totals"]["media_consumed_seconds"])
            self.assertEqual(540, weekly_payload["totals"]["media_content_seconds"])
            self.assertEqual(1, weekly_payload["totals"]["media_churn_events"])
            self.assertAlmostEqual(0.5, weekly_payload["media_averages"]["completion_ratio"], places=3)
            self.assertAlmostEqual(0.25, weekly_payload["media_averages"]["churn_rate"], places=3)

            weekly_json = runs_root / day_two / "outputs" / "dashboard_weekly_2d.json"
            weekly_html = runs_root / day_two / "outputs" / "dashboard_weekly_2d.html"
            write_weekly_outputs(weekly_payload, json_path=weekly_json, html_path=weekly_html)
            self.assertIn("Media events", weekly_html.read_text(encoding="utf-8"))

            lifetime_payload = build_lifetime_dashboard(
                end_date_text=day_two,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
            )
            self.assertEqual(3, lifetime_payload["totals"]["media_events"])
            self.assertEqual(3, lifetime_payload["totals"]["media_items_observed"])
            self.assertEqual(270, lifetime_payload["totals"]["media_consumed_seconds"])
            self.assertEqual(1, lifetime_payload["totals"]["media_churn_events"])
            self.assertAlmostEqual(0.5, lifetime_payload["media_averages"]["completion_ratio"], places=3)
            self.assertAlmostEqual(0.25, lifetime_payload["media_averages"]["churn_rate"], places=3)

            lifetime_json = runs_root / day_two / "outputs" / "dashboard_lifetime.json"
            lifetime_html = runs_root / day_two / "outputs" / "dashboard_lifetime.html"
            write_lifetime_outputs(lifetime_payload, json_path=lifetime_json, html_path=lifetime_html)
            self.assertIn("Media events", lifetime_html.read_text(encoding="utf-8"))

    def test_build_weekly_dashboard_debug_writes_and_links_daily_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            scoped_thread = "11111111-1111-4111-8111-111111111111"
            (context_root / "convo_ids.md").write_text(
                (
                    "| id | title | tail_lines | notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| {scoped_thread} | Scoped Thread | 100 | test |\n"
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

            db_path = _chat_db_path(tmp, repo_root)
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
            unscoped_thread = "22222222-2222-4222-8222-222222222222"
            cur.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "m1",
                    unscoped_thread,
                    "chatgpt",
                    "main",
                    f"{date}T10:00:00+00:00",
                    "user",
                    "hello",
                    "Unscoped Thread",
                    "src",
                ),
            )
            con.commit()
            con.close()

            payload = build_weekly_dashboard(
                end_date_text=date,
                days=1,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=db_path,
                chat_exports_dir=repo_root / "chat_exports",
                include_all_chat=True,
            )

            self.assertEqual("all", payload["chat_scope_mode"])
            self.assertEqual(1, payload["totals"]["chat_messages"])
            self.assertEqual(1, payload["daily"][0]["summary"]["chat_messages"])
            self.assertTrue(payload["daily"][0]["daily_html_path"].endswith("dashboard_all.html"))
            self.assertTrue(payload["daily"][0]["daily_json_path"].endswith("dashboard_all.json"))
            # Weekly build uses DB-first caching and does not implicitly write legacy JSON/HTML outputs.
            self.assertFalse((out_dir / "dashboard_all.html").exists())
            self.assertFalse((out_dir / "dashboard_all.json").exists())

    def test_build_lifetime_dashboard_includes_state_volume_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            (context_root / "convo_ids.md").write_text(
                "| id | title | tail_lines | notes |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )

            day_one = "2026-02-07"
            day_two = "2026-02-08"
            for date in (day_one, day_two):
                out_dir = runs_root / date / "outputs"
                out_dir.mkdir(parents=True, exist_ok=True)
                summary_payload = {
                    "date": date,
                    "chat_source": "sqlite",
                    "chat_scope_mode": "scoped",
                    "summary": {
                        "chat_messages": 2 if date == day_one else 1,
                        "chat_threads": 1,
                        "chat_switches": 0,
                        "shell_commands": 0,
                        "shell_commands_host": 0,
                        "shell_commands_agent_exec": 0,
                        "input_events": 0,
                        "input_keys_total": 0,
                        "input_mouse_total": 0,
                        "window_focus_events": 0,
                        "activity_events": 0,
                        "git_commits": 0,
                        "git_branch_events": 0,
                        "pr_events": 0,
                        "pr_received": 0,
                        "pr_commented": 0,
                        "pr_merged": 0,
                        "timeline_events": 0,
                        "context_switch_rate": 0.0,
                        "switches_per_active_hour": 0.0,
                        "messages_per_chat": 2.0 if date == day_one else 1.0,
                        "top_thread_share": 1.0,
                    },
                    "warnings": [],
                }
                (out_dir / "dashboard.json").write_text(
                    json.dumps(summary_payload),
                    encoding="utf-8",
                )
                (out_dir / "dashboard.html").write_text("<html></html>", encoding="utf-8")

            (runs_root / day_one / "outputs" / "state.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "id": "e1",
                                "low_signal": True,
                                "collapsed_count": 2,
                                "collapsed_ids": ["a", "b"],
                            },
                            {
                                "id": "e2",
                                "low_signal": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (runs_root / day_two / "outputs" / "state.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "id": "e3",
                                "low_signal": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = build_lifetime_dashboard(
                end_date_text=day_two,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
            )

            self.assertEqual(day_one, payload["period_start"])
            self.assertEqual(day_two, payload["period_end"])
            self.assertEqual(2, payload["days"])
            self.assertEqual(2, payload["state_days"])
            self.assertEqual(4, payload["state_totals"]["raw_events"])
            self.assertEqual(3, payload["state_totals"]["compressed_events"])
            self.assertEqual(2, payload["state_totals"]["junk_events_raw"])
            self.assertEqual(1, payload["state_totals"]["junk_events_compressed"])
            self.assertAlmostEqual(0.75, payload["state_ratios"]["compression_ratio"], places=3)

            lifetime_json = runs_root / day_two / "outputs" / "dashboard_lifetime.json"
            lifetime_html = runs_root / day_two / "outputs" / "dashboard_lifetime.html"
            write_lifetime_outputs(payload, json_path=lifetime_json, html_path=lifetime_html)
            self.assertTrue(lifetime_json.exists())
            self.assertTrue(lifetime_html.exists())
            html_text = lifetime_html.read_text(encoding="utf-8")
            self.assertIn("SB Lifetime Dashboard", html_text)
            self.assertIn("Compression ratio", html_text)
            self.assertIn("Junk events (raw est)", html_text)

    def test_build_lifetime_costing_payload_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            (context_root / "convo_ids.md").write_text(
                "| id | title | tail_lines | notes |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )

            day_one = "2026-02-07"
            day_two = "2026-02-08"
            for date, tokens, in_tokens, out_tokens, overflow_threads, overflow_tokens in (
                (day_one, 12000, 4000, 8000, 0, 0),
                (day_two, 260000, 90000, 170000, 1, 132000),
            ):
                out_dir = runs_root / date / "outputs"
                out_dir.mkdir(parents=True, exist_ok=True)
                summary_payload = {
                    "date": date,
                    "chat_source": "sqlite",
                    "chat_scope_mode": "scoped",
                    "summary": {
                        "chat_messages": 20 if date == day_one else 55,
                        "chat_threads": 2,
                        "chat_switches": 3,
                        "chat_chars_est": tokens * 4,
                        "chat_tokens_est": tokens,
                        "chat_input_tokens_est": in_tokens,
                        "chat_output_tokens_est": out_tokens,
                        "chat_other_tokens_est": 0,
                        "chat_context_overflow_threads": overflow_threads,
                        "chat_context_overflow_tokens": overflow_tokens,
                        "shell_commands": 0,
                        "shell_commands_host": 0,
                        "shell_commands_agent_exec": 0,
                        "input_events": 0,
                        "input_keys_total": 0,
                        "input_mouse_total": 0,
                        "window_focus_events": 0,
                        "activity_events": 0,
                        "git_commits": 0,
                        "git_branch_events": 0,
                        "pr_events": 0,
                        "pr_received": 0,
                        "pr_commented": 0,
                        "pr_merged": 0,
                        "timeline_events": 0,
                        "context_switch_rate": 0.0,
                        "switches_per_active_hour": 0.0,
                        "messages_per_chat": 10.0,
                        "top_thread_share": 0.8,
                        "agent_edit_blocks": 0,
                        "agent_edit_files": 0,
                        "agent_edit_lines_added": 0,
                        "agent_edit_lines_removed": 0,
                        "agent_edit_top_file_share": 0.0,
                        "media_events": 0,
                        "media_items_observed": 0,
                        "media_consumed_seconds": 0,
                        "media_content_seconds": 0,
                        "media_completion_ratio": 0.0,
                        "media_churn_events": 0,
                        "media_churn_rate": 0.0,
                    },
                    "warnings": [],
                }
                (out_dir / "dashboard.json").write_text(
                    json.dumps(summary_payload),
                    encoding="utf-8",
                )
                (out_dir / "dashboard.html").write_text("<html></html>", encoding="utf-8")

            lifetime_payload = build_lifetime_dashboard(
                end_date_text=day_two,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
            )
            costing_payload = build_lifetime_costing_payload(lifetime_payload=lifetime_payload)
            self.assertEqual(2, costing_payload["days"])
            self.assertEqual(272000, costing_payload["totals"]["chat_tokens_est"])
            self.assertEqual(94000, costing_payload["totals"]["chat_input_tokens_est"])
            self.assertEqual(178000, costing_payload["totals"]["chat_output_tokens_est"])
            self.assertEqual(1, costing_payload["totals"]["chat_context_overflow_threads"])
            self.assertEqual(132000, costing_payload["totals"]["chat_context_overflow_tokens"])
            self.assertTrue(any(item["id"] == "standard" for item in costing_payload["profiles"]))

            costing_json = runs_root / day_two / "outputs" / "dashboard_costing.json"
            costing_html = runs_root / day_two / "outputs" / "dashboard_costing.html"
            write_costing_outputs(costing_payload, json_path=costing_json, html_path=costing_html)
            self.assertTrue(costing_json.exists())
            self.assertTrue(costing_html.exists())
            html_text = costing_html.read_text(encoding="utf-8")
            self.assertIn("SB Indicative API Costing", html_text)
            self.assertIn("Scenario Cost Totals", html_text)
            self.assertIn("Claude", html_text)

    def test_build_dashboard_tracks_notebooklm_lifecycle_metrics(self):
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
            logs_dir = runs_root / date / "logs" / "notes"
            out_dir = runs_root / date / "outputs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "activity_ledger.json").write_text(
                json.dumps({"activity_events": [], "provenance": {}}),
                encoding="utf-8",
            )
            notes_rows = [
                {
                    "ts": f"{date}T06:00:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "notebook_created",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": None,
                },
                {
                    "ts": f"{date}T06:01:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "notebook_modified",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": None,
                },
                {
                    "ts": f"{date}T06:02:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "notebook_renamed",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": None,
                },
                {
                    "ts": f"{date}T06:03:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "notebook_deleted",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": None,
                },
                {
                    "ts": f"{date}T06:04:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "notebook_observed",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": None,
                },
                {
                    "ts": f"{date}T06:05:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "source_created",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": "sha256:file1",
                },
                {
                    "ts": f"{date}T06:06:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "source_updated",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": "sha256:file1",
                },
                {
                    "ts": f"{date}T06:07:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "source_moved",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": "sha256:file1",
                },
                {
                    "ts": f"{date}T06:08:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "source_deleted",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": "sha256:file1",
                },
                {
                    "ts": f"{date}T06:09:00Z",
                    "signal": "notes_meta",
                    "app": "notebooklm",
                    "event": "source_observed",
                    "notebook_id_hash": "sha256:nb1",
                    "note_id_hash": "sha256:file1",
                },
                {
                    "ts": f"{date}T06:10:00Z",
                    "signal": "notes_meta",
                    "app": "obsidian",
                    "event": "note_modified",
                    "vault_id_hash": "sha256:v1",
                    "note_id_hash": "sha256:n1",
                },
            ]
            (logs_dir / f"{date}.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in notes_rows),
                encoding="utf-8",
            )

            payload = build_dashboard(
                date_text=date,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
                max_timeline_events=100,
                include_all_chat=False,
            )

            self.assertEqual(11, payload["summary"]["notes_meta_events"])
            self.assertEqual(10, payload["summary"]["notebooklm_events"])
            notes_meta = payload.get("notes_meta_summary") or {}
            self.assertEqual(11, notes_meta.get("total_events"))
            self.assertEqual(10, notes_meta.get("notebooklm_events"))
            self.assertEqual(10, (notes_meta.get("notebooklm_hour_bins") or [0] * 24)[6])
            self.assertEqual(1, (notes_meta.get("notebooklm_event_counts") or {}).get("notebook_created"))
            lifecycle = notes_meta.get("lifecycle") or {}
            notebook = lifecycle.get("notebook") or {}
            file_counts = lifecycle.get("file") or {}
            self.assertEqual(1, notebook.get("created"))
            self.assertEqual(1, notebook.get("modified"))
            self.assertEqual(1, notebook.get("moved"))
            self.assertEqual(1, notebook.get("deleted"))
            self.assertEqual(1, notebook.get("seen"))
            self.assertEqual(1, file_counts.get("created"))
            self.assertEqual(1, file_counts.get("modified"))
            self.assertEqual(1, file_counts.get("moved"))
            self.assertEqual(1, file_counts.get("deleted"))
            self.assertEqual(1, file_counts.get("seen"))
            tool_use_summary = payload.get("tool_use_summary") or {}
            self.assertEqual(10, tool_use_summary.get("notebooklm_meta_event_count"))
            self.assertEqual(10, (tool_use_summary.get("notebooklm_meta_hour_bins") or [0] * 24)[6])
            families = {item.get("family"): item for item in (tool_use_summary.get("families") or [])}
            self.assertIn("notebooklm_meta_event", families)
            self.assertEqual(10, (families["notebooklm_meta_event"] or {}).get("count"))

            out_json = runs_root / date / "outputs" / "dashboard.json"
            out_html = runs_root / date / "outputs" / "dashboard.html"
            write_dashboard_outputs(payload, json_path=out_json, html_path=out_html)
            html_text = out_html.read_text(encoding="utf-8")
            self.assertIn("NotebookLM Lifecycle (Metadata)", html_text)
            self.assertIn("Notebooks created", html_text)
            self.assertIn("Files created", html_text)

    def test_build_lifetime_dashboard_aggregates_notebooklm_lifecycle_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            (context_root / "convo_ids.md").write_text(
                "| id | title | tail_lines | notes |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )

            day_one = "2026-02-07"
            day_two = "2026-02-08"
            for date in (day_one, day_two):
                out_dir = runs_root / date / "outputs"
                notes_dir = runs_root / date / "logs" / "notes"
                out_dir.mkdir(parents=True, exist_ok=True)
                notes_dir.mkdir(parents=True, exist_ok=True)
                summary_payload = {
                    "date": date,
                    "chat_source": "sqlite",
                    "chat_scope_mode": "scoped",
                    "summary": {
                        "chat_messages": 0,
                        "chat_threads": 0,
                        "chat_switches": 0,
                        "shell_commands": 0,
                        "shell_commands_host": 0,
                        "shell_commands_agent_exec": 0,
                    },
                    "warnings": [],
                }
                (out_dir / "dashboard.json").write_text(
                    json.dumps(summary_payload),
                    encoding="utf-8",
                )
                (out_dir / "dashboard.html").write_text("<html></html>", encoding="utf-8")

            (runs_root / day_one / "logs" / "notes" / f"{day_one}.jsonl").write_text(
                (
                    json.dumps(
                        {
                            "ts": f"{day_one}T06:00:00Z",
                            "signal": "notes_meta",
                            "app": "notebooklm",
                            "event": "notebook_created",
                            "notebook_id_hash": "sha256:nb1",
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "ts": f"{day_one}T06:01:00Z",
                            "signal": "notes_meta",
                            "app": "notebooklm",
                            "event": "source_created",
                            "notebook_id_hash": "sha256:nb1",
                            "note_id_hash": "sha256:file1",
                        }
                    )
                    + "\n"
                ),
                encoding="utf-8",
            )
            (runs_root / day_two / "logs" / "notes" / f"{day_two}.jsonl").write_text(
                (
                    json.dumps(
                        {
                            "ts": f"{day_two}T06:00:00Z",
                            "signal": "notes_meta",
                            "app": "notebooklm",
                            "event": "source_updated",
                            "notebook_id_hash": "sha256:nb1",
                            "note_id_hash": "sha256:file1",
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "ts": f"{day_two}T06:01:00Z",
                            "signal": "notes_meta",
                            "app": "notebooklm",
                            "event": "notebook_renamed",
                            "notebook_id_hash": "sha256:nb1",
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "ts": f"{day_two}T06:02:00Z",
                            "signal": "notes_meta",
                            "app": "notebooklm",
                            "event": "notebook_observed",
                            "notebook_id_hash": "sha256:nb1",
                        }
                    )
                    + "\n"
                ),
                encoding="utf-8",
            )

            payload = build_lifetime_dashboard(
                end_date_text=day_two,
                repo_root=repo_root,
                runs_root=runs_root,
                context_root=context_root,
                convo_ids_path=context_root / "convo_ids.md",
                chat_db_path=_chat_db_path(tmp, repo_root),
                chat_exports_dir=repo_root / "chat_exports",
            )

            notes_totals = payload.get("notes_meta_totals") or {}
            lifecycle_totals = payload.get("notebooklm_lifecycle_totals") or {}
            self.assertEqual(5, notes_totals.get("total_events"))
            self.assertEqual(5, notes_totals.get("notebooklm_events"))
            self.assertEqual(1, lifecycle_totals.get("notebook", {}).get("created"))
            self.assertEqual(1, lifecycle_totals.get("notebook", {}).get("moved"))
            self.assertEqual(1, lifecycle_totals.get("notebook", {}).get("seen"))
            self.assertEqual(1, lifecycle_totals.get("file", {}).get("created"))
            self.assertEqual(1, lifecycle_totals.get("file", {}).get("modified"))

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

            db_path = _chat_db_path(tmp, repo_root)
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
            self.assertEqual(3, summary.get("exec_with_workdir_count"))
            self.assertEqual(0, summary.get("exec_without_workdir_count"))
            self.assertEqual(3, summary.get("unique_commands"))
            self.assertEqual(3, (summary.get("exec_command_hour_bins") or [0] * 24)[10])
            self.assertEqual(3, payload["summary"]["shell_commands"])
            self.assertEqual(0, payload["summary"]["shell_commands_host"])
            self.assertEqual(3, payload["summary"]["shell_commands_agent_exec"])
            self.assertEqual(3, payload["frequency_by_hour"]["shell"][10])

            families = {item["family"]: item for item in summary.get("families") or []}
            self.assertIn("python build_dashboard.py", families)
            self.assertEqual(2, families["python build_dashboard.py"]["count"])
            self.assertIn("git status", families)

    def test_tool_use_summary_hydrates_input_hour_from_request_user_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            thread_id = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
            (context_root / "convo_ids.md").write_text(
                (
                    "| id | title | tail_lines | notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| {thread_id} | Input Hydration Thread | 100 | test |\n"
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

            db_path = _chat_db_path(tmp, repo_root)
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
                    "2026-02-08T13:00:00+00:00",
                    "tool",
                    'request_user_input {"questions":[{"header":"Scope","id":"scope","question":"Pick one","options":[{"label":"A","description":"opt"}]}]}',
                    "",
                    "src",
                ),
                (
                    "m2",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T13:15:00+00:00",
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
            self.assertEqual(1, summary.get("request_user_input_count"))
            self.assertEqual(1, (summary.get("request_user_input_hour_bins") or [0] * 24)[13])
            self.assertEqual(1, payload["summary"]["input_events"])
            self.assertEqual(0, payload["summary"]["input_events_host"])
            self.assertEqual(1, payload["summary"]["input_events_agent_request_user_input"])
            self.assertEqual(1, payload["frequency_by_hour"]["input"][13])

    def test_tool_use_summary_skips_env_assignments_for_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            thread_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            (context_root / "convo_ids.md").write_text(
                (
                    "| id | title | tail_lines | notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| {thread_id} | Env Prefix Thread | 100 | test |\n"
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

            db_path = _chat_db_path(tmp, repo_root)
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
                    'exec_command {"cmd":"PYTHONPATH=/repo/.deps:/repo/src python /repo/src/ingest.py --in sample.json","workdir":"/repo"}',
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
                    'exec_command {"cmd":"env PYTHONPATH=/repo/.deps:/repo/src python -m unittest discover -s tests","workdir":"/repo"}',
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
            families = {item["family"]: item for item in summary.get("families") or []}
            self.assertIn("python ingest.py", families)
            self.assertIn("python -m unittest", families)
            self.assertNotIn(".deps", families)
            self.assertNotIn("src", families)

    def test_tool_use_summary_groups_non_rg_variants_by_env_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "StatiBaker" / "runs"
            context_root = repo_root / "__CONTEXT"
            context_root.mkdir(parents=True, exist_ok=True)
            thread_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
            (context_root / "convo_ids.md").write_text(
                (
                    "| id | title | tail_lines | notes |\n"
                    "| --- | --- | --- | --- |\n"
                    f"| {thread_id} | Prefix Group Thread | 100 | test |\n"
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

            db_path = _chat_db_path(tmp, repo_root)
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
                    "2026-02-08T11:00:00+00:00",
                    "tool",
                    'exec_command {"cmd":"PYTHONPATH=/repo/.deps:/repo/src python /repo/src/ingest.py --in a.json","workdir":"/repo"}',
                    "",
                    "src",
                ),
                (
                    "m2",
                    thread_id,
                    "chatgpt",
                    "main",
                    "2026-02-08T11:01:00+00:00",
                    "tool",
                    'exec_command {"cmd":"PYTHONPATH=/repo/.deps:/repo/src python /repo/src/ingest.py --in b.json","workdir":"/repo"}',
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
            families = {item["family"]: item for item in summary.get("families") or []}
            self.assertIn("python ingest.py", families)
            ingest_family = families["python ingest.py"]
            groups = ingest_family.get("variant_groups") or []
            prefix_group = next(
                (item for item in groups if str(item.get("group", "")).startswith("PYTHONPATH=")),
                None,
            )
            self.assertIsNotNone(prefix_group)
            self.assertEqual(2, int(prefix_group.get("count") or 0))
            variant_details = " ".join(
                str(item.get("detail") or "") for item in (prefix_group.get("variants") or [])
            )
            self.assertIn("--in a.json", variant_details)
            self.assertIn("--in b.json", variant_details)

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

            db_path = _chat_db_path(tmp, repo_root)
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

            db_path = _chat_db_path(tmp, repo_root)
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

    def test_chat_flow_waterfall_marks_thread_switches(self):
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

            db_path = _chat_db_path(tmp, repo_root)
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
            thread_a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            thread_b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            rows = [
                ("m1", thread_a, "chatgpt", "main", "2026-02-08T10:00:00+00:00", "user", "a1", "Thread A", "src"),
                ("m2", thread_a, "chatgpt", "main", "2026-02-08T10:01:00+00:00", "assistant", "a2", "Thread A", "src"),
                ("m3", thread_b, "chatgpt", "main", "2026-02-08T10:02:00+00:00", "user", "b1", "Thread B", "src"),
                ("m4", thread_a, "chatgpt", "main", "2026-02-08T10:03:00+00:00", "assistant", "a3", "Thread A", "src"),
            ]
            cur.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
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

            flow = payload["chat_flow"]
            self.assertEqual(4, flow["message_count"])
            self.assertEqual(2, flow["thread_count"])
            self.assertEqual(2, flow["switch_count"])
            self.assertAlmostEqual(0.667, flow["switch_rate"], places=3)
            self.assertAlmostEqual(2.0, flow["switches_per_active_hour"], places=2)
            self.assertAlmostEqual(2.0, payload["summary"]["messages_per_chat"], places=2)
            self.assertEqual(2, payload["summary"]["chat_switches"])
            self.assertAlmostEqual(0.667, payload["summary"]["context_switch_rate"], places=3)
            self.assertAlmostEqual(2.0, payload["summary"]["switches_per_active_hour"], places=2)
            self.assertAlmostEqual(0.75, payload["summary"]["top_thread_share"], places=3)
            self.assertEqual([60, 60, 60, 60], [item.get("gap_to_next_seconds") for item in flow["waterfall"]])
            self.assertEqual([10, 10, 10, 10], [item.get("thread_start_hour") for item in flow["waterfall"]])

            out_html = runs_root / date / "outputs" / "dashboard.html"
            out_json = runs_root / date / "outputs" / "dashboard.json"
            write_dashboard_outputs(payload, json_path=out_json, html_path=out_html)
            html_text = out_html.read_text(encoding="utf-8")
            self.assertIn("Chat Flow Visualizations", html_text)
            self.assertIn("wf-seg switch", html_text)
            self.assertIn("wf-lane-svg", html_text)
            self.assertIn("Width encodes elapsed time until the next message", html_text)

    def test_chat_context_trailing_comparison_uses_prior_daily_dashboards(self):
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
            prior_date = "2026-02-07"
            out_dir = runs_root / date / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "activity_ledger.json").write_text(
                json.dumps({"activity_events": [], "provenance": {}}),
                encoding="utf-8",
            )
            prior_out = runs_root / prior_date / "outputs"
            prior_out.mkdir(parents=True, exist_ok=True)
            (prior_out / "dashboard.json").write_text(
                json.dumps(
                    {
                        "date": prior_date,
                        "summary": {
                            "context_switch_rate": 0.2,
                            "switches_per_active_hour": 0.5,
                            "messages_per_chat": 3.0,
                            "top_thread_share": 0.9,
                        },
                    }
                ),
                encoding="utf-8",
            )

            db_path = _chat_db_path(tmp, repo_root)
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
            thread_a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            thread_b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            rows = [
                ("m1", thread_a, "chatgpt", "main", "2026-02-08T10:00:00+00:00", "user", "a1", "Thread A", "src"),
                ("m2", thread_b, "chatgpt", "main", "2026-02-08T10:01:00+00:00", "assistant", "b1", "Thread B", "src"),
            ]
            cur.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
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

            trailing = payload["chat_context_trailing"]
            self.assertTrue(trailing["has_baseline"])
            self.assertEqual(1, trailing["available_days"])
            self.assertAlmostEqual(1.0, trailing["current"]["context_switch_rate"], places=3)
            self.assertAlmostEqual(0.2, trailing["baseline_avg"]["context_switch_rate"], places=3)
            self.assertAlmostEqual(0.8, trailing["delta"]["context_switch_rate"], places=3)


if __name__ == "__main__":
    unittest.main()
