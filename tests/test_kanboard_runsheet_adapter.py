from __future__ import annotations

import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from sb.kanboard_runsheet import (
    KanboardJsonRpcClient,
    apply_sync_plan,
    build_dry_run_plan,
    build_sync_report,
    fetch_existing_by_reference,
    load_kanboard_env,
    load_local_rows,
)


class TestKanboardRunsheetAdapter(unittest.TestCase):
    def test_load_rows_from_status_runsheet(self) -> None:
        payload = {
            "orchestrator_id": "statibaker-kanboard-adapter-manager",
            "lane": "statibaker-kanboard-jsonrpc-adapter",
            "runsheet": {
                "items": [
                    {"id": "surface", "title": "Inspect existing patterns", "status": "done"},
                    {
                        "id": "client",
                        "title": "Implement planner",
                        "status": "in_progress",
                        "subtasks": [{"title": "Dry-run only", "status": "done"}],
                    },
                ]
            },
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(payload, handle)
            handle.flush()
            loaded = load_local_rows(handle.name)
        rows = loaded["rows"]
        self.assertEqual(2, len(rows))
        self.assertEqual("surface", rows[0]["stable_id"])
        self.assertEqual("statibaker-kanboard-adapter-manager", rows[0]["runner_id"])
        self.assertEqual("statibaker-kanboard-jsonrpc-adapter", rows[0]["lane"])

    def test_duplicate_ids_fail_fast(self) -> None:
        payload = {
            "runsheet": {
                "items": [
                    {"id": "x", "title": "A", "status": "todo"},
                    {"id": "x", "title": "B", "status": "done"},
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(payload, handle)
            handle.flush()
            with self.assertRaises(ValueError):
                load_local_rows(handle.name)

    def test_build_dry_run_plan_with_create_update_move_and_metadata(self) -> None:
        rows = [
            {
                "stable_id": "surface",
                "title": "Inspect patterns",
                "status": "done",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "done when reviewed",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "exact",
                "task_identity_residual": "exact",
            },
            {
                "stable_id": "client",
                "title": "Implement planner",
                "status": "in_progress",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [{"title": "Dry-run only", "status": "done"}],
                "canonical_thread_id": "thread-1",
                "source_message_id": "msg-1",
                "lifecycle_residual": "partial",
                "task_identity_residual": "exact",
            },
        ]
        existing = {
            "surface": {
                "id": 10,
                "title": "Old title",
                "description": "",
                "reference": "surface",
                "column_id": 2,
            }
        }
        column_map = {
            "todo": {"column_id": 1, "column_name": "Backlog"},
            "in_progress": {"column_id": 2, "column_name": "Doing"},
            "blocked": {"column_id": 3, "column_name": "Blocked"},
            "done": {"column_id": 4, "column_name": "Done"},
            "skipped": {"column_id": 5, "column_name": "Skipped"},
        }
        plan = build_dry_run_plan(
            rows,
            project_id=7,
            now_iso="2026-05-19T13:30:00Z",
            existing_by_reference=existing,
            column_by_status=column_map,
        )
        self.assertEqual("sb.kanboard_dry_run.v0_1", plan["schema_version"])
        self.assertEqual(2, plan["task_count"])
        self.assertEqual({"completed": 1, "total": 2}, plan["progress"])
        self.assertEqual(2, plan["summary"]["lookups"])
        self.assertEqual(1, plan["summary"]["creates"])
        self.assertEqual(1, plan["summary"]["updates"])
        self.assertEqual(1, plan["summary"]["moves"])
        self.assertEqual(2, plan["summary"]["metadata"])
        self.assertIn("saveTaskMetadata", plan["required_rpc_shape"])
        self.assertTrue(all(op["rpc"]["method"] != "apply" for op in plan["operations"]))
        metadata_ops = [op for op in plan["operations"] if op["op"] == "metadata"]
        self.assertEqual(2, len(metadata_ops))
        metadata_keys = set(metadata_ops[0]["rpc"]["params"]["values"].keys())
        self.assertIn("statibaker.stable_id", metadata_keys)
        self.assertIn("statibaker.last_sync_at", metadata_keys)
        client_create = [op for op in plan["operations"] if op["op"] == "create" and op["stable_id"] == "client"]
        self.assertEqual(1, len(client_create))
        self.assertEqual(2, client_create[0]["rpc"]["params"]["column_id"])

    def test_runsheet_source_path_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "rows.json"
            parent = root / "status.json"
            child.write_text(
                json.dumps({"runsheet": {"items": [{"id": "x", "title": "Task", "status": "todo"}]}}),
                encoding="utf-8",
            )
            parent.write_text(json.dumps({"runsheet_source": {"path": "rows.json"}}), encoding="utf-8")
            loaded = load_local_rows(parent)
        self.assertEqual(["x"], [row["stable_id"] for row in loaded["rows"]])

    def test_build_sync_report_from_dry_run_plan(self) -> None:
        rows = [
            {
                "stable_id": "task-1",
                "title": "Task one",
                "status": "done",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "",
                "task_identity_residual": "",
            }
        ]
        plan = build_dry_run_plan(rows, project_id=3, now_iso="2026-05-19T14:00:00Z")
        report = build_sync_report(
            plan=plan,
            input_source_path="/tmp/status.runner.json",
            report_path="/tmp/kanboard_sync_report.latest.json",
            now_iso="2026-05-19T14:00:00Z",
        )
        self.assertEqual("sb.kanboard_sync_report.v0_1", report["schema_version"])
        self.assertEqual(1, report["summary"]["creates"])
        self.assertEqual(0, report["summary"]["errors"])
        refs = report["external_references"]["kanboard_task_references"]
        self.assertEqual("task-1", refs[0]["stable_id"])
        self.assertEqual("task-1", refs[0]["kanboard_reference"])

    def test_second_sync_over_unchanged_input_has_zero_creates_updates_and_moves(self) -> None:
        rows = [
            {
                "stable_id": "surface",
                "title": "Inspect patterns",
                "status": "done",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "",
                "task_identity_residual": "",
            },
            {
                "stable_id": "client",
                "title": "Implement planner",
                "status": "in_progress",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [{"title": "Dry-run only", "status": "done"}],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "",
                "task_identity_residual": "",
            },
        ]
        existing = {
            "surface": {
                "id": 10,
                "title": "Inspect patterns",
                "description": "",
                "reference": "surface",
                "column_id": 4,
            },
            "client": {
                "id": 11,
                "title": "Implement planner",
                "description": "Subtasks:\n- [x] Dry-run only",
                "reference": "client",
                "column_id": 2,
            },
        }
        column_map = {
            "todo": {"column_id": 1, "column_name": "Backlog"},
            "in_progress": {"column_id": 2, "column_name": "Doing"},
            "blocked": {"column_id": 3, "column_name": "Blocked"},
            "done": {"column_id": 4, "column_name": "Done"},
            "skipped": {"column_id": 5, "column_name": "Skipped"},
        }
        plan = build_dry_run_plan(
            rows,
            project_id=7,
            now_iso="2026-05-19T14:00:00Z",
            existing_by_reference=existing,
            column_by_status=column_map,
        )
        self.assertEqual(0, plan["summary"]["creates"])
        self.assertEqual(0, plan["summary"]["updates"])
        self.assertEqual(0, plan["summary"]["moves"])
        self.assertEqual(2, plan["summary"]["metadata"])

    def test_build_dry_run_plan_accepts_bootstrap_column_map_wrapper(self) -> None:
        rows = [
            {
                "stable_id": "task-1",
                "title": "Task one",
                "status": "blocked",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "",
                "task_identity_residual": "",
            }
        ]
        wrapped_column_map = {
            "schema_version": "sb.kanboard_column_map.v0_1",
            "column_map": {
                "blocked": {"column_id": 9, "column_name": "Blocked"},
            },
        }
        plan = build_dry_run_plan(
            rows,
            project_id=7,
            now_iso="2026-05-20T01:00:00Z",
            column_by_status=wrapped_column_map,
        )
        create_ops = [op for op in plan["operations"] if op["op"] == "create"]
        self.assertEqual(1, len(create_ops))
        self.assertEqual(9, create_ops[0]["rpc"]["params"]["column_id"])

    def test_build_dry_run_plan_projects_labels_as_real_tags_and_metadata(self) -> None:
        rows = [
            {
                "stable_id": "ao-control:manager",
                "title": "AO manager",
                "status": "needs_retry",
                "runner_id": "manager",
                "lane": "lane",
                "parent_id": "",
                "depth": 0,
                "source": "ao_control_surface",
                "provenance": {},
                "acceptance_criteria": "",
                "description": "Phase: failed",
                "labels": ["ao", "ao:manager-rejected"],
                "subtasks": [],
                "metadata": {"statibaker.ao.phase": "failed"},
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "",
                "task_identity_residual": "",
            }
        ]
        plan = build_dry_run_plan(
            rows,
            project_id=7,
            now_iso="2026-05-20T01:00:00Z",
            column_by_status={"needs_retry": {"column_id": 8, "column_name": "Needs Retry"}},
        )
        create_ops = [op for op in plan["operations"] if op["op"] == "create"]
        tag_ops = [op for op in plan["operations"] if op["op"] == "tags"]
        metadata_ops = [op for op in plan["operations"] if op["op"] == "metadata"]
        self.assertEqual(["ao", "ao:manager-rejected"], create_ops[0]["rpc"]["params"]["tags"])
        self.assertEqual("setTaskTags", tag_ops[0]["rpc"]["method"])
        self.assertEqual(["ao", "ao:manager-rejected"], tag_ops[0]["rpc"]["params"]["tags"])
        metadata = metadata_ops[0]["rpc"]["params"]["values"]
        self.assertEqual("ao,ao:manager-rejected", metadata["statibaker.labels"])
        self.assertEqual("failed", metadata["statibaker.ao.phase"])
        self.assertEqual(1, plan["summary"]["tags"])

    def test_missing_column_id_mapping_fails_without_mutating_local_rows(self) -> None:
        rows = [
            {
                "stable_id": "x",
                "title": "Blocked task",
                "status": "blocked",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "",
                "task_identity_residual": "",
            }
        ]
        before = deepcopy(rows)
        with self.assertRaises(ValueError):
            build_dry_run_plan(
                rows,
                project_id=7,
                now_iso="2026-05-19T14:00:00Z",
                column_by_status={"blocked": {"column_name": "Blocked"}},
            )
        self.assertEqual(before, rows)

    def test_apply_sync_plan_enforces_phase_order(self) -> None:
        rows = [
            {
                "stable_id": "surface",
                "title": "Inspect patterns",
                "status": "done",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "done when reviewed",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "exact",
                "task_identity_residual": "exact",
            },
            {
                "stable_id": "client",
                "title": "Implement planner",
                "status": "in_progress",
                "runner_id": "runner-1",
                "lane": "lane-1",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "partial",
                "task_identity_residual": "exact",
            },
        ]
        existing = {
            "surface": {
                "id": 10,
                "title": "Old title",
                "description": "",
                "reference": "surface",
                "column_id": 2,
            }
        }
        column_map = {
            "todo": {"column_id": 1, "column_name": "Backlog"},
            "in_progress": {"column_id": 2, "column_name": "Doing"},
            "blocked": {"column_id": 3, "column_name": "Blocked"},
            "done": {"column_id": 4, "column_name": "Done"},
            "skipped": {"column_id": 5, "column_name": "Skipped"},
        }
        plan = build_dry_run_plan(
            rows,
            project_id=7,
            now_iso="2026-05-20T01:00:00Z",
            existing_by_reference=existing,
            column_by_status=column_map,
        )
        calls: list[tuple[str, dict]] = []

        def rpc_call(method: str, params: dict) -> object:
            calls.append((method, params))
            if method == "getTaskByReference":
                if params["reference"] == "surface":
                    return {"id": 10}
                return None
            if method == "createTask":
                return 21
            return True

        report = apply_sync_plan(plan, rpc_call)
        self.assertFalse(report["aborted"])
        self.assertEqual(
            [
                "getTaskByReference",
                "getTaskByReference",
                "createTask",
                "updateTask",
                "moveTaskPosition",
                "saveTaskMetadata",
                "saveTaskMetadata",
            ],
            [method for method, _ in calls],
        )
        metadata_call = [entry for entry in calls if entry[0] == "saveTaskMetadata" and entry[1]["task_id"] == 21]
        self.assertEqual(1, len(metadata_call))

    def test_apply_sync_plan_skips_create_when_lookup_finds_existing(self) -> None:
        rows = [
            {
                "stable_id": "task-a",
                "title": "Task A",
                "status": "todo",
                "runner_id": "runner",
                "lane": "lane",
                "parent_id": "",
                "depth": 0,
                "source": "status",
                "provenance": {},
                "acceptance_criteria": "",
                "labels": [],
                "subtasks": [],
                "canonical_thread_id": "",
                "source_message_id": "",
                "lifecycle_residual": "",
                "task_identity_residual": "",
            }
        ]
        plan = build_dry_run_plan(rows, project_id=7, now_iso="2026-05-20T01:00:00Z")
        calls: list[tuple[str, dict]] = []

        def rpc_call(method: str, params: dict) -> object:
            calls.append((method, params))
            if method == "getTaskByReference":
                return {"id": 99}
            return True

        report = apply_sync_plan(plan, rpc_call)
        self.assertFalse(report["aborted"])
        self.assertEqual(1, report["skipped"]["create"])
        self.assertEqual(0, report["executed"]["create"])
        metadata_calls = [entry for entry in calls if entry[0] == "saveTaskMetadata"]
        self.assertEqual(1, len(metadata_calls))
        self.assertEqual(99, metadata_calls[0][1]["task_id"])
        sync_report = build_sync_report(
            plan={**plan, "mode": "apply"},
            input_source_path="/tmp/status.json",
            report_path="/tmp/kanboard_sync_report.latest.json",
            now_iso="2026-05-20T01:00:00Z",
            errors=report["errors"],
            apply_report=report,
        )
        self.assertEqual(0, sync_report["summary"]["creates"])
        self.assertEqual(1, sync_report["summary"]["lookups"])
        self.assertEqual(1, sync_report["summary"]["metadata"])

    def test_fetch_existing_by_reference_uses_top_level_stable_ids(self) -> None:
        rows = [
            {"stable_id": "a", "depth": 0},
            {"stable_id": "a-child", "depth": 1},
            {"stable_id": "b", "depth": 0},
        ]
        calls: list[tuple[str, dict]] = []

        def rpc_call(method: str, params: dict) -> object:
            calls.append((method, params))
            if params["reference"] == "a":
                return {"id": 10, "reference": "a"}
            return None

        existing = fetch_existing_by_reference(rows, project_id=3, rpc_call=rpc_call)
        self.assertEqual({"a": {"id": 10, "reference": "a"}}, existing)
        self.assertEqual(["a", "b"], [params["reference"] for _, params in calls])

    def test_load_kanboard_env_from_file(self) -> None:
        old_env = dict(os.environ)
        try:
            for key in list(os.environ):
                if key.startswith("KANBOARD_"):
                    os.environ.pop(key, None)
            with tempfile.TemporaryDirectory() as tmp:
                env_path = Path(tmp) / "kanboard.env"
                env_path.write_text(
                    "\n".join(
                        [
                            "# comment",
                            "KANBOARD_JSONRPC_ENDPOINT=http://127.0.0.1/kanboard/jsonrpc.php",
                            "KANBOARD_PROJECT_ID=3",
                            "KANBOARD_API_USER=api",
                            "KANBOARD_API_TOKEN=secret-token",
                        ]
                    ),
                    encoding="utf-8",
                )
                config = load_kanboard_env(env_path)
            self.assertEqual("http://127.0.0.1/kanboard/jsonrpc.php", config["jsonrpc_endpoint"])
            self.assertEqual(3, config["project_id"])
            self.assertEqual("api", config["api_user"])
            self.assertEqual("secret-token", config["api_token"])
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_jsonrpc_client_retries_transient_database_lock(self) -> None:
        class _Response:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def __enter__(self) -> "_Response":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(self._payload).encode("utf-8")

        client = KanboardJsonRpcClient(
            endpoint="http://127.0.0.1/jsonrpc.php",
            api_user="api",
            api_token="token",
            transient_lock_retries=1,
            transient_lock_retry_delay_seconds=0.0,
        )
        attempts = {"count": 0}
        responses = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"message": "SQLSTATE[HY000]: General error: 5 database is locked"},
            },
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": True,
            },
        ]

        def _fake_urlopen(_request, timeout=0):
            _ = timeout
            payload = responses[attempts["count"]]
            attempts["count"] += 1
            return _Response(payload)

        with patch("sb.kanboard_runsheet.urllib_request.urlopen", side_effect=_fake_urlopen):
            result = client.call("saveTaskMetadata", {"task_id": 1, "values": {"k": "v"}})
        self.assertTrue(result)
        self.assertEqual(2, attempts["count"])


if __name__ == "__main__":
    unittest.main()
