import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters import media_consumption


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    shaped = dict(record)
    shaped["platform"] = "spotify"
    shaped["event_type"] = shaped.get("event_type") or "playback_observed"
    shaped["item_id"] = shaped.get("item_id") or shaped.get("track_uri") or shaped.get("spotify_track_uri")
    shaped["item_title"] = shaped.get("item_title") or shaped.get("track_name")
    shaped["artist"] = shaped.get("artist") or shaped.get("artist_name")
    if "ms_played" in shaped and "consumed_ms" not in shaped:
        shaped["consumed_ms"] = shaped.get("ms_played")
    if "duration_ms" in shaped and "content_duration_ms" not in shaped:
        shaped["content_duration_ms"] = shaped.get("duration_ms")
    return media_consumption.normalize_record(shaped, source)


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Spotify play-history rows into media_consumption.")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="spotify_history_stub", help="Provenance source label")
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
