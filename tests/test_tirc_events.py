import json
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.tirc_events import normalize_record, normalize_records


def test_open_closed_are_explicit_replay_safe_events():
    opened = {"trajectory_id": "trip:7", "timestamp": "2026-10-28T00:00:00Z", "event_type": "trajectory_open"}
    closed = {**opened, "timestamp": "2026-10-28T00:03:00Z", "event_type": "trajectory_closed"}
    events = list(normalize_records([opened, closed]))
    assert [event["event_type"] for event in events] == ["trajectory_open", "trajectory_closed"]
    assert [event["state"] for event in events] == ["open", "closed"]
    assert events[0]["trajectory_key_hash"] == events[1]["trajectory_key_hash"]
    assert events[0]["event_id"] != events[1]["event_id"]
    assert normalize_record(opened) == events[0]
    assert events[0]["provenance"] == {"source": "tircorder", "collected_at": opened["timestamp"]}
    assert "trajectory_id" not in events[0]


def test_alias_and_upstream_id_are_supported():
    r = {"trajectory_id": "t", "ts": "2026-10-28T01:00:00Z", "signal": "trajectory", "state": "closed"}
    assert normalize_record(r)["event_type"] == "trajectory_closed"
    a = normalize_record({**r, "event_id": "a"})
    b = normalize_record({**r, "event_id": "b"})
    assert a["event_id"] != b["event_id"]


@pytest.mark.parametrize("invalid", [
    {},
    {"trajectory_id": "t", "ts": "x", "event_type": "trajectory_missing"},
    {"trajectory_id": "t", "ts": "x", "event_type": "trajectory_open", "state": "closed"},
    {"trajectory_id": "t", "ts": "x", "event_type": "trajectory"},
    {"trajectory_id": " ", "ts": "x", "event_type": "trajectory_open"},
])
def test_fail_closed(invalid):
    with pytest.raises(ValueError):
        normalize_record(invalid)


def test_cli_deterministic_jsonl_and_no_partial_output(tmp_path):
    src, dest = tmp_path / "events.jsonl", tmp_path / "out" / "events.jsonl"
    src.write_text(
        json.dumps({"trajectory_id": "t", "ts": "2026-10-28T01:00:00Z", "event_type": "trajectory_open"}) + "\n"
        + json.dumps({"trajectory_id": "t", "ts": "2026-10-28T02:00:00Z", "event_type": "trajectory_close"}) + "\n",
        encoding="utf-8",
    )
    cmd = [sys.executable, "-m", "adapters.tirc_events", "--input", str(src), "--output", str(dest)]
    root = Path(__file__).resolve().parents[1]
    assert subprocess.run(cmd, cwd=root, check=False).returncode == 0
    before = dest.read_bytes()
    assert subprocess.run(cmd, cwd=root, check=False).returncode == 0
    assert dest.read_bytes() == before
    assert len(before.splitlines()) == 2
    src.write_text('{"trajectory_id": "t", "ts": "x", "event_type": "bad"}\n', encoding="utf-8")
    assert subprocess.run(cmd, cwd=root, check=False).returncode == 2
    assert dest.read_bytes() == before
