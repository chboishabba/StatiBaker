from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.whisperx_webui_execution import (  # noqa: E402
    append_transcription_activity_log,
    build_transcription_activity_event,
)


def _sample_envelope() -> dict:
    return {
        "id": "env-123",
        "format": "sb_execution_envelope_v1",
        "source": "whisperx_webui",
        "audio_hash": "abc123",
        "segment_count": 2,
        "created_at": "2026-03-24T01:02:03Z",
        "toolchain": {"model": "large-v3", "language": "en"},
        "provenance": {"transcript_hash": "deadbeef", "adapter": "test"},
    }


def test_build_transcription_activity_event_embeds_execution_envelope(tmp_path):
    transcript_artifact = tmp_path / "sample.whisperx_transcript.json"
    transcript_artifact.write_text("{}", encoding="utf-8")

    event = build_transcription_activity_event(
        _sample_envelope(),
        transcript_artifact_path=transcript_artifact,
    )

    assert event["source"] == "tircorder"
    assert event["activity_event"]["kind"] == "tool_execution"
    assert event["activity_event"]["tool"] == "whisperx_webui"
    assert event["activity_event"]["execution_envelope"]["id"] == "env-123"
    assert event["activity_event"]["artifacts"] == [str(transcript_artifact)]


def test_append_transcription_activity_log_is_append_only_and_deduplicated(tmp_path):
    transcript_artifact = tmp_path / "sample.whisperx_transcript.json"
    transcript_artifact.write_text("{}", encoding="utf-8")

    first = append_transcription_activity_log(
        log_root=tmp_path,
        execution_envelope=_sample_envelope(),
        transcript_artifact_path=transcript_artifact,
    )
    second = append_transcription_activity_log(
        log_root=tmp_path,
        execution_envelope=_sample_envelope(),
        transcript_artifact_path=transcript_artifact,
    )

    assert first["status"] == "appended"
    assert second["status"] == "duplicate"

    log_path = Path(first["path"])
    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["id"] == first["event_id"]
    assert rows[0]["activity_event"]["execution_envelope"]["id"] == "env-123"
