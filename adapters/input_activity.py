import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance


ALLOWED_KEYS = {"text", "nav", "control", "function", "other"}
ALLOWED_MOUSE = {"moves", "clicks", "scroll"}


def _sanitize_counts(payload: Dict[str, Any], allowed: set[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for key in allowed:
        value = payload.get(key)
        if value is None:
            continue
        try:
            iv = int(value)
        except (TypeError, ValueError):
            continue
        if iv < 0:
            continue
        out[key] = iv
    return out


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    keys = record.get("keys") or {}
    mouse = record.get("mouse") or {}

    normalized = {
        "ts": ts,
        "signal": "input",
        "focus_app": record.get("focus_app"),
        "keys": _sanitize_counts(keys, ALLOWED_KEYS),
        "mouse": _sanitize_counts(mouse, ALLOWED_MOUSE),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize input activity records (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="input_activity", help="Provenance source label")
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
