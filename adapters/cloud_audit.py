import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    resource_id = record.get("resource_id")
    resource_hash = record.get("resource_id_hash") or (sha256_text(resource_id) if resource_id else None)

    actor = record.get("actor")
    actor_hash = record.get("actor_hash") or (sha256_text(actor) if actor else None)

    ip = record.get("ip")
    ip_hash = record.get("ip_hash") or (sha256_text(ip) if ip else None)

    normalized = {
        "ts": ts,
        "signal": "cloud_audit",
        "provider": record.get("provider"),
        "event_type": record.get("event_type"),
        "resource_id_hash": resource_hash,
        "actor_hash": actor_hash,
        "ip_hash": ip_hash,
        "device_hash": record.get("device_hash"),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize cloud audit records (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="cloud_audit", help="Provenance source label")
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
