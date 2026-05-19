import json
import unittest
from pathlib import Path

from sb.runsheet_bridge import build_runsheet_projection


class TestRunsheetBridge(unittest.TestCase):
    def test_runsheet_items_projection_and_progress(self):
        payload = {
            "orchestrator_id": "runner-1",
            "lane": "bridge-lane",
            "runsheet": {
                "items": [
                    {"id": "read", "title": "Read context", "status": "done"},
                    {
                        "id": "contract",
                        "title": "Patch bridge contract",
                        "status": "in_progress",
                        "subtasks": [
                            {"id": "contract-validate", "title": "Run validation", "status": "todo"}
                        ],
                    },
                    {"id": "report", "title": "Report", "status": "skipped"},
                ]
            },
        }

        projection = build_runsheet_projection(payload)
        self.assertTrue(projection["valid"])
        self.assertEqual("runsheet.items", projection["source_kind"])
        self.assertEqual(4, len(projection["rows"]))
        self.assertEqual(1, projection["progress"]["completed"])
        self.assertEqual(2, projection["progress"]["total"])
        self.assertEqual("Patch bridge contract", projection["progress"]["current_milestone"])

    def test_duplicate_id_is_rejected(self):
        payload = {
            "runsheet": {
                "items": [
                    {"id": "same", "title": "Row A", "status": "todo"},
                    {"id": "same", "title": "Row B", "status": "done"},
                ]
            }
        }

        projection = build_runsheet_projection(payload)
        self.assertFalse(projection["valid"])
        self.assertTrue(any(err["code"] == "duplicate_id" for err in projection["errors"]))

    def test_nested_subtasks_are_rejected(self):
        payload = {
            "runsheet": {
                "items": [
                    {
                        "id": "root",
                        "title": "Root task",
                        "status": "in_progress",
                        "subtasks": [
                            {
                                "id": "child",
                                "title": "Child task",
                                "status": "todo",
                                "subtasks": [
                                    {"id": "grandchild", "title": "Grandchild", "status": "todo"}
                                ],
                            }
                        ],
                    }
                ]
            }
        }
        projection = build_runsheet_projection(payload)
        self.assertFalse(projection["valid"])
        self.assertTrue(any(err["code"] == "nested_subtask" for err in projection["errors"]))

    def test_malformed_status_is_rejected(self):
        payload = {
            "tasks": [
                {"id": "a", "title": "Task A", "status": "doing"},
            ]
        }
        projection = build_runsheet_projection(payload)
        self.assertFalse(projection["valid"])
        self.assertTrue(any(err["code"] == "malformed_status" for err in projection["errors"]))

    def test_timeline_cases_fixture_projection(self):
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "runsheet_timeline_cases_sample.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))

        projection = build_runsheet_projection(payload)
        self.assertTrue(projection["valid"])
        self.assertEqual("timeline_cases", projection["source_kind"])
        self.assertEqual(3, len(projection["rows"]))
        self.assertEqual("timeline-002", projection["rows"][1]["stable_id"])


if __name__ == "__main__":
    unittest.main()
