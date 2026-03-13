from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "capture_notebooklm_activity.py"
SPEC = spec_from_file_location("capture_notebooklm_activity", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_conversation_records = MODULE.build_conversation_records
build_note_records = MODULE.build_note_records


def test_build_conversation_records_handles_nested_history_shape() -> None:
    history = [[["conv-1", "What changed?", "The note was updated.", 1700000000]]]
    rows = build_conversation_records(
        collected_at="2026-03-11T01:00:00Z",
        notebook_id="nb-123",
        notebook_title="Notebook",
        history=history,
        preview_chars=80,
        history_limit=10,
    )
    assert len(rows) == 1
    assert rows[0]["event_type"] == "conversation_observed"
    assert rows[0]["conversation_id"] == "conv-1"
    assert rows[0]["query_preview"] == "What changed?"
    assert rows[0]["conversation_turn_ts"].endswith("Z")


def test_build_note_records_bounds_preview_and_length() -> None:
    notes = [SimpleNamespace(id="note-1", title="Open items", content="x" * 120)]
    rows = build_note_records(
        collected_at="2026-03-11T01:00:00Z",
        notebook_id="nb-123",
        notebook_title="Notebook",
        notes=notes,
        preview_chars=20,
        note_limit=10,
    )
    assert len(rows) == 1
    assert rows[0]["event_type"] == "note_observed"
    assert rows[0]["note_id"] == "note-1"
    assert rows[0]["note_length"] == 120
    assert rows[0]["note_preview"].endswith("…")
