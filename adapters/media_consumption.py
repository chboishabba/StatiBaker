import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text


def _hash_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("sha256:"):
        return text
    return sha256_text(text)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _seconds_from_fields(record: Dict[str, Any], second_keys: tuple[str, ...], ms_keys: tuple[str, ...]) -> int:
    for key in second_keys:
        if key in record and record.get(key) is not None:
            return max(0, int(round(_safe_float(record.get(key)))))
    for key in ms_keys:
        if key in record and record.get(key) is not None:
            return max(0, int(round(_safe_float(record.get(key)) / 1000.0)))
    return 0


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    platform = str(record.get("platform") or "unknown").strip().lower() or "unknown"
    event_type = str(record.get("event_type") or "playback_observed").strip().lower() or "playback_observed"

    item_id = (
        record.get("item_id")
        or record.get("video_id")
        or record.get("track_id")
        or record.get("uri")
        or record.get("media_id")
        or record.get("source_id")
    )
    item_title = record.get("item_title") or record.get("title") or record.get("name") or record.get("track")
    artist = record.get("artist") or record.get("artist_name")
    channel = record.get("channel") or record.get("channel_id")
    session = record.get("session_id") or record.get("session_key") or record.get("history_session")

    consumed_seconds = _seconds_from_fields(
        record,
        second_keys=("consumed_seconds", "played_seconds", "listened_seconds", "watch_seconds", "position_seconds"),
        ms_keys=("consumed_ms", "played_ms", "listened_ms", "watch_ms", "ms_played", "position_ms"),
    )
    content_duration_seconds = _seconds_from_fields(
        record,
        second_keys=(
            "content_duration_seconds",
            "duration_seconds",
            "track_duration_seconds",
            "video_duration_seconds",
            "length_seconds",
        ),
        ms_keys=("content_duration_ms", "duration_ms", "track_duration_ms", "video_duration_ms", "length_ms"),
    )

    completion_ratio = record.get("completion_ratio")
    completion_value = _safe_float(completion_ratio)
    if completion_ratio is None and content_duration_seconds > 0:
        completion_value = float(consumed_seconds) / float(content_duration_seconds)
    completion_value = round(max(0.0, completion_value), 3)

    normalized = {
        "ts": ts,
        "signal": "media_consumption",
        "platform": platform,
        "event_type": event_type,
        "app": record.get("app") or record.get("player"),
        "item_id_hash": _hash_or_none(record.get("item_id_hash") or item_id),
        "item_title_hash": _hash_or_none(record.get("item_title_hash") or item_title),
        "artist_hash": _hash_or_none(record.get("artist_hash") or artist),
        "channel_hash": _hash_or_none(record.get("channel_hash") or channel),
        "session_id_hash": _hash_or_none(record.get("session_id_hash") or session),
        "consumed_seconds": consumed_seconds,
        "content_duration_seconds": content_duration_seconds,
        "completion_ratio": completion_value,
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize media consumption records (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="media_consumption", help="Provenance source label")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        raw = [json.loads(line) for line in handle if line.strip()]

    normalized = list(normalize_records(raw, args.source))

    with open(args.output, "w", encoding="utf-8") as handle:
        for entry in normalized:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
