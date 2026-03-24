from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _event_id(execution_id: str) -> str:
    return hashlib.sha256(f"whisperx_webui:{execution_id}".encode("utf-8")).hexdigest()[:16]


def _resolve_timestamp(
    completed_at: str | None,
    execution_envelope: Mapping[str, Any],
) -> str:
    return (
        completed_at
        or execution_envelope.get("created_at")
        or datetime.now(timezone.utc).isoformat()
    )


def build_transcription_activity_event(
    execution_envelope: Mapping[str, Any],
    *,
    transcript_artifact_path: str | Path | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    execution_id = str(execution_envelope["id"])
    event_id = _event_id(execution_id)
    ts = _resolve_timestamp(completed_at, execution_envelope)
    artifacts: list[str] = []
    if transcript_artifact_path:
        artifacts.append(str(Path(transcript_artifact_path)))

    return {
        "id": event_id,
        "ts": ts,
        "source": "tircorder",
        "type": "activity",
        "text": (
            f"whisperx_webui transcription completed "
            f"({execution_envelope.get('segment_count', 0)} segments)"
        ),
        "meta": {
            "tool": "whisperx_webui",
            "execution_id": execution_id,
            "format": execution_envelope.get("format"),
            "audio_hash": execution_envelope.get("audio_hash"),
            "segment_count": execution_envelope.get("segment_count"),
            "transcript_artifact_path": (
                str(transcript_artifact_path) if transcript_artifact_path else None
            ),
        },
        "activity_event": {
            "kind": "tool_execution",
            "tool": "whisperx_webui",
            "execution_envelope": dict(execution_envelope),
            "artifacts": artifacts,
        },
    }


def append_transcription_activity_log(
    *,
    log_root: str | Path,
    execution_envelope: Mapping[str, Any],
    transcript_artifact_path: str | Path | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    event = build_transcription_activity_event(
        execution_envelope,
        transcript_artifact_path=transcript_artifact_path,
        completed_at=completed_at,
    )
    date_text = str(event["ts"])[:10]
    target = (
        Path(log_root)
        / date_text
        / "logs"
        / "transcription"
        / f"{date_text}.jsonl"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if existing.get("id") == event["id"]:
                return {
                    "status": "duplicate",
                    "path": str(target),
                    "event_id": event["id"],
                }

    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    return {
        "status": "appended",
        "path": str(target),
        "event_id": event["id"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append a WhisperX-WebUI execution envelope into a StatiBaker transcription log."
    )
    parser.add_argument("--envelope", required=True, help="path to execution envelope JSON payload")
    parser.add_argument("--log-root", required=True, help="StatiBaker runs root")
    parser.add_argument("--transcript-artifact", help="optional transcript artifact path")
    parser.add_argument("--completed-at", help="override completion timestamp")
    args = parser.parse_args()

    payload = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
    execution_envelope = payload.get("execution_envelope", payload)
    result = append_transcription_activity_log(
        log_root=args.log_root,
        execution_envelope=execution_envelope,
        transcript_artifact_path=args.transcript_artifact,
        completed_at=args.completed_at,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
