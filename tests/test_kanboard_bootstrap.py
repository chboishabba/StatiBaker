from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from sb.kanboard_bootstrap import (
    KanboardRpcClient,
    bootstrap_board,
    parse_env_file,
    resolve_runtime_config,
)


class _StubRequester:
    def __init__(self, scripted_results: list[tuple[str, Any]]) -> None:
        self.scripted_results = scripted_results
        self.calls: list[str] = []

    def __call__(self, request, _timeout_seconds: float) -> bytes:  # noqa: ANN001
        payload = json.loads(request.data.decode("utf-8"))
        method = payload["method"]
        self.calls.append(method)
        if not self.scripted_results:
            raise AssertionError(f"Unexpected call: {method}")
        expected_method, result = self.scripted_results.pop(0)
        if expected_method != method:
            raise AssertionError(f"Expected {expected_method}, got {method}")
        return json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result}).encode("utf-8")


class TestKanboardBootstrap(unittest.TestCase):
    def test_apply_adds_missing_columns_and_emits_ready_map(self) -> None:
        requester = _StubRequester(
            [
                ("getProjectById", {"id": "1", "name": "SB"}),
                (
                    "getColumns",
                    [
                        {"id": "11", "title": "Backlog"},
                        {"id": "12", "title": "Doing"},
                        {"id": "13", "title": "Done"},
                    ],
                ),
                ("addColumn", 14),
                ("addColumn", 15),
                (
                    "getColumns",
                    [
                        {"id": "11", "title": "Backlog"},
                        {"id": "12", "title": "Doing"},
                        {"id": "13", "title": "Done"},
                        {"id": "14", "title": "Blocked"},
                        {"id": "15", "title": "Skipped"},
                    ],
                ),
            ]
        )
        client = KanboardRpcClient(
            endpoint="http://127.0.0.1/kanboard/jsonrpc.php",
            api_user="jsonrpc",
            api_token="token",
            requester=requester,
        )

        report = bootstrap_board(client, project_id=1, project_name="SB", apply=True)

        self.assertTrue(report["ready_for_sync"])
        self.assertEqual([], report["unresolved_statuses"])
        self.assertEqual(14, report["column_map"]["blocked"]["column_id"])
        self.assertEqual(15, report["column_map"]["skipped"]["column_id"])
        add_ops = [op for op in report["operations"] if op["op"] == "add_column"]
        self.assertEqual(2, len(add_ops))
        self.assertTrue(all(op["status"] == "applied" for op in add_ops))

    def test_dry_run_plans_create_and_column_bootstrap(self) -> None:
        requester = _StubRequester(
            [
                ("getProjectById", None),
                ("getProjectByName", None),
                ("getColumns", []),
            ]
        )
        client = KanboardRpcClient(
            endpoint="http://127.0.0.1/kanboard/jsonrpc.php",
            api_user="jsonrpc",
            api_token="token",
            requester=requester,
        )

        report = bootstrap_board(client, project_id=9, project_name="Target Board", apply=False)

        self.assertFalse(report["ready_for_sync"])
        self.assertEqual(["todo", "in_progress", "blocked", "done", "skipped"], report["unresolved_statuses"])
        planned_project = [op for op in report["operations"] if op["op"] == "create_project"]
        self.assertEqual(1, len(planned_project))
        self.assertEqual("planned", planned_project[0]["status"])
        planned_columns = [op for op in report["operations"] if op["op"] == "add_column"]
        self.assertEqual(5, len(planned_columns))
        self.assertTrue(all(op["status"] == "planned" for op in planned_columns))

    def test_env_parse_and_runtime_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "kanboard.env"
            env_file.write_text(
                "\n".join(
                    [
                        "# sample",
                        "KANBOARD_BASE_URL=http://127.0.0.1/kanboard",
                        "KANBOARD_PROJECT_ID=7",
                        "export KANBOARD_API_USER=jsonrpc",
                        "KANBOARD_API_TOKEN=token-value",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            env = parse_env_file(env_file)

        config = resolve_runtime_config(env, {"KANBOARD_PROJECT_NAME": "Local Board"})

        self.assertEqual("http://127.0.0.1/kanboard/jsonrpc.php", config.endpoint)
        self.assertEqual(7, config.project_id)
        self.assertEqual("Local Board", config.project_name)
        self.assertEqual("jsonrpc", config.api_user)
        self.assertEqual("token-value", config.api_token)


if __name__ == "__main__":
    unittest.main()
