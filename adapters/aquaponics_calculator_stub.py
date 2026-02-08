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


def _safe_bool_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    text = str(value or "").strip().lower()
    return 1 if text in {"1", "true", "yes", "on", "running"} else 0


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = coerce_ts(record)
    normalized = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "aquaponics",
        "event_type": str(record.get("event_type") or "snapshot_observed").strip().lower(),
        "system_id_hash": _hash_or_none(record.get("system_id_hash") or record.get("system_id")),
        "tank_id_hash": _hash_or_none(record.get("tank_id_hash") or record.get("tank_id")),
        "bed_id_hash": _hash_or_none(record.get("bed_id_hash") or record.get("bed_id")),
        "water_temp_c": round(_safe_float(record.get("water_temp_c")), 3),
        "ph": round(_safe_float(record.get("ph")), 3),
        "ec_ms_cm": round(_safe_float(record.get("ec_ms_cm") or record.get("ec")), 3),
        "dissolved_o2_mg_l": round(_safe_float(record.get("dissolved_o2_mg_l")), 3),
        "ammonia_mg_l": round(_safe_float(record.get("ammonia_mg_l")), 3),
        "nitrite_mg_l": round(_safe_float(record.get("nitrite_mg_l")), 3),
        "nitrate_mg_l": round(_safe_float(record.get("nitrate_mg_l")), 3),
        "flow_l_min": round(_safe_float(record.get("flow_l_min")), 3),
        "feed_grams": round(_safe_float(record.get("feed_grams")), 3),
        "pump_on": _safe_bool_int(record.get("pump_on") or record.get("pump_state")),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize aquaponics calculator snapshots (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="aquaponics_calculator_stub", help="Provenance source label")
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
