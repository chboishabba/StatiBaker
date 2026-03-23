import json
import pytest
from pathlib import Path
from sb.observed_ingest import load_observed_events

def test_malformed_json_failure_is_not_silent(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    sample = log_dir / "bad.jsonl"
    # One good, one bad, one good
    sample.write_text(
        '{"ts":"2026-02-06T10:00:00Z","signal":"input","focus_app":"x"}\n'
        '{"ts":"2026-02-06T10:01:00Z", malformed!!}\n'
        '{"ts":"2026-02-06T10:02:00Z","signal":"input","focus_app":"y"}\n'
    )

    events = load_observed_events(log_dir)
    # Current behavior is to silently skip the malformed line.
    # We want it to be surfaced.
    signals = [e["type"] for e in events]
    assert "error" in signals or "error_surface" in [e.get("meta", {}).get("signal") for e in events], "Malformed JSON was silently ignored!"

def test_missing_ts_is_not_silent(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    sample = log_dir / "missing_ts.jsonl"
    sample.write_text('{"signal":"input","focus_app":"x"}\n')

    events = load_observed_events(log_dir)
    assert events, "Record with missing ts was silently ignored!"
    assert any(e.get("type") == "error" for e in events) or any(e.get("meta", {}).get("signal") == "error_surface" for e in events)
