from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sb.itir_ingest import validate_overlay


def test_itir_overlay_accepts_observed_annotation():
    record = {
        "activity_event_id": "signal-abc123",
        "annotation_id": "obs:browser_usage",
        "provenance": {"source": "itir", "collected_at": "2026-02-06T10:00:00Z"},
        "state_date": "2026-02-06",
    }
    assert validate_overlay(record) == []
