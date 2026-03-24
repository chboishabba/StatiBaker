import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import google_keep_lists, google_tasks  # noqa: E402


def test_google_tasks_normalizes_external_commitment() -> None:
    record = {
        "ts": "2026-03-24T08:10:00Z",
        "id": "task-123",
        "list_id": "list-1",
        "title": "Call Mum",
        "notes": "from assistant",
        "status": "completed",
        "origin": "google_home",
    }
    normalized = google_tasks.normalize_record(record, "google_tasks")
    assert normalized["signal"] == "external_commitment"
    assert normalized["source_kind"] == "google_tasks_task"
    assert normalized["external_item_id"] == "task-123"
    assert normalized["status"] == "completed"
    assert normalized["voice_origin"] == "tasks_command"


def test_google_keep_lists_normalizes_external_commitment() -> None:
    record = {
        "ts": "2026-03-24T08:11:00Z",
        "item_id": "keep-123",
        "list_name": "To Do",
        "text": "Buy milk",
        "checked": False,
    }
    normalized = google_keep_lists.normalize_record(record, "google_keep_lists")
    assert normalized["signal"] == "external_commitment"
    assert normalized["source_kind"] == "google_keep_list_item"
    assert normalized["external_item_id"] == "keep-123"
    assert normalized["external_list_id"] == "To Do"
    assert normalized["status"] == "open"
    assert normalized["voice_origin"] == "keep_list"
