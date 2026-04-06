import sys
from unittest.mock import patch
from pathlib import Path
import pytest

# Ensure StatiBaker is in path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb.observed_ingest import iter_observed_events

def test_observed_ingest_with_sensiblaw_reducer(tmp_path):
    """
    Verify that observed_ingest correctly uses the SensibLaw shared reducer
    when HAS_REDUCER is True.
    """
    # Setup mock log
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test.jsonl"
    # Note: _safe_summary uses signal, event, event_type, platform, browser
    log_file.write_text('{"ts":"2026-03-19T20:00:00Z","signal":"test_signal","event":"click"}\n')
    
    # Mock the SensibLaw reducer output
    mock_ref = {
        "occurrence_id": "occ_1",
        "kind": "case_ref",
        "span_start": 0,
        "span_end": 11,
    }
    
    # Patch the state in sb.observed_ingest
    with patch("sb.observed_ingest.HAS_REDUCER", True), \
         patch("sb.observed_ingest.collect_canonical_lexeme_refs", return_value=[mock_ref]), \
         patch("sb.observed_ingest.get_canonical_tokenizer_profile_receipt", return_value={"profile_id": "test"}):
        
        events = list(iter_observed_events(log_dir))
        
        assert len(events) == 1
        event = events[0]
        assert event["source"] == "observed"
        assert "canonical_lexeme_refs" in event
        assert event["canonical_lexeme_refs"] == [mock_ref]
        assert event["tokenizer_profile_receipt"] == {"profile_id": "test"}

def test_observed_ingest_without_sensiblaw_reducer(tmp_path):
    """
    Verify that observed_ingest skips SensibLaw fields when HAS_REDUCER is False.
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test.jsonl"
    log_file.write_text('{"ts":"2026-03-19T20:00:00Z","signal":"test_signal"}\n')
    
    with patch("sb.observed_ingest.HAS_REDUCER", False):
        events = list(iter_observed_events(log_dir))
        
        assert len(events) == 1
        event = events[0]
        assert "canonical_lexeme_refs" not in event
        assert "tokenizer_profile_receipt" not in event
