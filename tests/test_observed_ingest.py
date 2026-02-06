from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb.observed_ingest import load_observed_events


def test_observed_ingest_reads_logs(tmp_path):
    log_dir = tmp_path / "logs" / "input"
    log_dir.mkdir(parents=True)
    sample = log_dir / "2026-02-06.jsonl"
    sample.write_text('{"ts":"2026-02-06T10:00:00Z","signal":"input","focus_app":"x"}\n')

    events = load_observed_events(tmp_path / "logs")
    assert events
    assert events[0]["source"] == "observed"
    assert events[0]["type"] == "signal"
    assert "text" in events[0]
