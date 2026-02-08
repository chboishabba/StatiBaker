import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text

ALLOWED_EVENTS = {
    "pr_received",
    "pr_opened",
    "pr_review_requested",
    "pr_reviewed",
    "pr_commented",
    "pr_merged",
    "pr_closed",
}


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_type(record: Dict[str, Any]) -> str:
    raw = (
        record.get("event_type")
        or record.get("event")
        or record.get("action")
        or record.get("type")
    )
    event = str(raw or "").strip().lower()
    if event in ALLOWED_EVENTS:
        return event
    if event in {"comment", "commented"}:
        return "pr_commented"
    if event in {"merge", "merged"}:
        return "pr_merged"
    if event in {"open", "opened"}:
        return "pr_opened"
    if event in {"close", "closed"}:
        return "pr_closed"
    if event in {"receive", "received"}:
        return "pr_received"
    raise ValueError(f"unsupported pr event type: {event or 'missing'}")


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    event_type = _event_type(record)
    repo = str(record.get("repo") or record.get("repository") or "")
    if not repo:
        raise ValueError("missing repo")

    number = _as_int(record.get("pr_number") or record.get("number"))
    if number is None or number < 0:
        raise ValueError("missing pr_number")

    actor = record.get("actor") or record.get("author") or record.get("sender")
    actor_hash = sha256_text(str(actor)) if actor else None
    pr_key = f"{repo}#{number}"

    normalized = {
        "ts": ts,
        "signal": "pr_event",
        "event_type": event_type,
        "repo": repo,
        "pr_number": number,
        "pr_key_hash": sha256_text(pr_key),
        "state": record.get("state"),
        "provenance": normalize_provenance(source, record),
    }
    if actor_hash:
        normalized["actor_hash"] = actor_hash
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize PR event records for SB dashboarding.")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="pr_events", help="Provenance source label")
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

