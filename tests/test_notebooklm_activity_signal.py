import json
from pathlib import Path

from adapters import notebooklm_activity


def test_notebooklm_activity_normalizes_conversation_and_note_events() -> None:
    conversation = notebooklm_activity.normalize_record(
        {
            "ts": "2026-03-11T01:00:00Z",
            "collected_at": "2026-03-11T01:00:00Z",
            "event_type": "conversation_observed",
            "notebook_id": "nb-123",
            "notebook_title": "Research notebook",
            "conversation_id": "conv-456",
            "query_preview": "What happened?",
            "answer_preview": "A bounded summary.",
            "conversation_turn_ts": "2026-03-10T23:59:59Z",
        },
        "notebooklm_activity",
    )
    assert conversation["signal"] == "notebooklm_activity"
    assert conversation["event"] == "conversation_observed"
    assert conversation["conversation_id_hash"].startswith("sha256:")
    assert conversation["query_preview"] == "What happened?"

    note = notebooklm_activity.normalize_record(
        {
            "ts": "2026-03-11T01:05:00Z",
            "collected_at": "2026-03-11T01:05:00Z",
            "event_type": "note_observed",
            "notebook_id": "nb-123",
            "note_id": "note-789",
            "note_title": "Follow-up tasks",
            "note_preview": "Check the downstream contract.",
            "note_length": 29,
        },
        "notebooklm_activity",
    )
    assert note["note_id_hash"].startswith("sha256:")
    assert note["note_title"] == "Follow-up tasks"
    assert note["note_length"] == 29


def test_notebooklm_activity_normalized_rows_write_as_jsonl(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized.jsonl"
    rows = list(
        notebooklm_activity.normalize_records(
            [
                {
                    "ts": "2026-03-11T01:00:00Z",
                    "collected_at": "2026-03-11T01:00:00Z",
                    "event_type": "conversation_observed",
                    "notebook_id": "nb-123",
                    "conversation_id": "conv-456",
                    "query_preview": "Question",
                    "answer_preview": "Answer",
                }
            ],
            "test",
        )
    )
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    loaded = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert loaded[0]["signal"] == "notebooklm_activity"
