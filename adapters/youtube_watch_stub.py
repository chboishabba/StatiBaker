import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters import media_consumption


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    shaped = dict(record)
    shaped["platform"] = "youtube"
    shaped["event_type"] = shaped.get("event_type") or "playback_observed"
    shaped["item_id"] = shaped.get("item_id") or shaped.get("video_id") or shaped.get("video_url")
    shaped["item_title"] = shaped.get("item_title") or shaped.get("title")
    shaped["channel"] = shaped.get("channel") or shaped.get("channel_title")
    return media_consumption.normalize_record(shaped, source)


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize YouTube watch records into media_consumption.")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="youtube_watch_stub", help="Provenance source label")
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
