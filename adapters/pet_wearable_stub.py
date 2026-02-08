import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import coerce_ts, normalize_provenance, sha256_text


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


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = coerce_ts(record)
    normalized = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "pet_wearable",
        "event_type": str(record.get("event_type") or "telemetry_observed").strip().lower(),
        "device_id_hash": _hash_or_none(record.get("device_id_hash") or record.get("device_id")),
        "pet_id_hash": _hash_or_none(record.get("pet_id_hash") or record.get("pet_id")),
        "activity_index": round(_safe_float(record.get("activity_index")), 3),
        "steps_count": _safe_int(record.get("steps_count") or record.get("steps")),
        "rest_minutes": _safe_int(record.get("rest_minutes") or record.get("rest_mins")),
        "sleep_minutes": _safe_int(record.get("sleep_minutes") or record.get("sleep_mins")),
        "hr_bpm": _safe_int(record.get("hr_bpm") or record.get("heart_rate_bpm")),
        "location_cell_hash": _hash_or_none(record.get("location_cell_hash") or record.get("cell_id")),
        "battery_pct": round(_safe_float(record.get("battery_pct")), 3),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize pet wearable / smart collar telemetry (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="pet_wearable_stub", help="Provenance source label")
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

