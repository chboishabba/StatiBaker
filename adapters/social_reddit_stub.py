import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    post_id = record.get("post_id") or record.get("full_id")
    post_hash = record.get("post_id_hash") or (sha256_text(post_id) if post_id else None)

    author = record.get("author")
    author_hash = record.get("author_hash") or (sha256_text(author) if author else None)

    normalized = {
        "ts": ts,
        "signal": "social_feed",
        "platform": "reddit",
        "event_type": record.get("event_type") or record.get("action"),
        "post_id_hash": post_hash,
        "author_hash": author_hash,
        "thread_id_hash": record.get("thread_id_hash"),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Reddit feed records (meta-only stub).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="reddit_stub", help="Provenance source label")
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
