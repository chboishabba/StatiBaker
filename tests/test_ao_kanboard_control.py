from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sb.ao_kanboard_control import build_ao_control_runsheet


class TestAoKanboardControl(unittest.TestCase):
    def test_builds_live_control_runsheet_from_status_and_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status.manager-a.json").write_text(
                json.dumps(
                    {
                        "orchestrator_id": "manager-a",
                        "phase": "active",
                        "lane": "lane-a",
                        "parent_orchestrator_id": "root",
                        "last_cycle_started_at": "2026-05-20T00:00:00Z",
                        "runsheet": {
                            "items": [
                                {"id": "read", "title": "Read context", "status": "done"},
                                {"id": "validate", "title": "Run validation", "status": "todo"},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "heartbeat.manager-a.json").write_text(
                json.dumps(
                    {
                        "phase": "running",
                        "child_pid": 123,
                        "last_heartbeat": "2026-05-20T00:04:00Z",
                        "current_step": "Running validation",
                    }
                ),
                encoding="utf-8",
            )
            (root / "status.manager-b.json").write_text(
                json.dumps(
                    {
                        "orchestrator_id": "manager-b",
                        "phase": "complete",
                        "lane_claim": "promotion is intentionally held until root validation",
                        "milestones_remaining": 0,
                        "runsheet": {"items": [{"id": "close", "title": "Close lane", "status": "done"}]},
                    }
                ),
                encoding="utf-8",
            )
            (root / "heartbeat.manager-b.json").write_text(
                json.dumps(
                    {
                        "phase": "done",
                        "state": 0,
                        "exit_code": 0,
                        "last_heartbeat": "2026-05-20T00:05:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (root / "status.manager-c.json").write_text(
                json.dumps(
                    {
                        "orchestrator_id": "manager-c",
                        "phase": "complete",
                        "runsheet": {"items": [{"id": "validation", "title": "Run validation", "status": "todo"}]},
                    }
                ),
                encoding="utf-8",
            )

            payload = build_ao_control_runsheet(
                root,
                now_iso="2026-05-20T00:06:00Z",
                stale_seconds=300,
            )

        self.assertEqual("sb.ao_kanboard_control_surface.v0_1", payload["schema_version"])
        rows = {item["runner_id"]: item for item in payload["runsheet"]["items"]}
        self.assertEqual("running", rows["manager-a"]["status"])
        self.assertEqual("1/2", rows["manager-a"]["metadata"]["statibaker.ao.milestones"])
        self.assertEqual("done", rows["manager-b"]["status"])
        self.assertIn("ao:manager-accepted", rows["manager-b"]["labels"])
        self.assertIn("ao:non-promotion", rows["manager-b"]["labels"])
        self.assertEqual("validation_needed", rows["manager-c"]["status"])
        self.assertIn("ao:validation-needed", rows["manager-c"]["labels"])
        self.assertTrue(payload["authority_boundary"]["ao_artifacts_are_source_of_truth"])

    def test_stale_done_heartbeat_is_recorded_as_completed_not_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status.manager.json").write_text(
                json.dumps({"orchestrator_id": "manager", "phase": "complete", "milestones_remaining": 0}),
                encoding="utf-8",
            )
            (root / "heartbeat.manager.json").write_text(
                json.dumps({"phase": "done", "last_heartbeat": "2026-05-20T00:00:00Z"}),
                encoding="utf-8",
            )
            payload = build_ao_control_runsheet(
                root,
                now_iso="2026-05-20T01:00:00Z",
                stale_seconds=60,
            )

        item = payload["runsheet"]["items"][0]
        self.assertEqual("done", item["status"])
        self.assertIn("ao:completed", item["labels"])
        self.assertNotIn("ao:stale", item["labels"])

    def test_stale_root_validation_gets_blocker_label_without_forcing_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status.supermanager.json").write_text(
                json.dumps(
                    {
                        "orchestrator_id": "supermanager",
                        "phase": "active",
                        "lane": "validation-root",
                    }
                ),
                encoding="utf-8",
            )
            (root / "heartbeat.supermanager.json").write_text(
                json.dumps({"phase": "running", "last_heartbeat": "2026-05-20T00:00:00Z"}),
                encoding="utf-8",
            )
            payload = build_ao_control_runsheet(
                root,
                now_iso="2026-05-20T01:00:00Z",
                stale_seconds=60,
            )

        item = payload["runsheet"]["items"][0]
        self.assertEqual("running", item["status"])
        self.assertIn("ao:stale", item["labels"])
        self.assertIn("ao:root-validation-stale", item["labels"])
        self.assertIn("ao:blocked-upstream", item["labels"])


if __name__ == "__main__":
    unittest.main()
