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


def _safe_state(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"occupied", "unoccupied", "idle"}:
        return text
    return "unknown"


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = coerce_ts(record)
    normalized = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "living_environment",
        "event_type": str(record.get("event_type") or "snapshot_observed").strip().lower(),
        "simulator": str(record.get("simulator") or "unknown").strip().lower() or "unknown",
        "scenario_id_hash": _hash_or_none(record.get("scenario_id_hash") or record.get("scenario_id")),
        "zone_id_hash": _hash_or_none(record.get("zone_id_hash") or record.get("zone_id") or record.get("zone")),
        "occupancy_state": _safe_state(record.get("occupancy_state") or record.get("occupancy")),
        "temp_c": round(_safe_float(record.get("temp_c")), 3),
        "humidity_pct": round(_safe_float(record.get("humidity_pct")), 3),
        "co2_ppm": round(_safe_float(record.get("co2_ppm")), 3),
        "pm25_ug_m3": round(_safe_float(record.get("pm25_ug_m3")), 3),
        "voc_index": round(_safe_float(record.get("voc_index")), 3),
        "noise_db": round(_safe_float(record.get("noise_db")), 3),
        "light_lux": round(_safe_float(record.get("light_lux")), 3),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize living-environment simulator snapshots (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="living_environment_simulator_stub", help="Provenance source label")
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
