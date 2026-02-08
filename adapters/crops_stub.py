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


def _safe_stage(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    if not text:
        return "unknown"
    if len(text) > 64:
        return text[:64]
    return text


def _safe_bool_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    text = str(value or "").strip().lower()
    return 1 if text in {"1", "true", "yes", "on"} else 0


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = coerce_ts(record)
    normalized = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "crops",
        "event_type": str(record.get("event_type") or "state_observed").strip().lower(),
        "plot_id_hash": _hash_or_none(record.get("plot_id_hash") or record.get("plot_id")),
        "crop_id_hash": _hash_or_none(record.get("crop_id_hash") or record.get("crop_id")),
        "cultivar_id_hash": _hash_or_none(record.get("cultivar_id_hash") or record.get("cultivar_id")),
        "cycle_id_hash": _hash_or_none(record.get("cycle_id_hash") or record.get("cycle_id")),
        "stage_code": _safe_stage(record.get("stage_code") or record.get("growth_stage")),
        "canopy_pct": round(_safe_float(record.get("canopy_pct")), 3),
        "soil_moisture_pct": round(_safe_float(record.get("soil_moisture_pct")), 3),
        "irrigation_liters": round(_safe_float(record.get("irrigation_liters")), 3),
        "nutrient_ec_ms_cm": round(_safe_float(record.get("nutrient_ec_ms_cm")), 3),
        "brix": round(_safe_float(record.get("brix")), 3),
        "pest_flag": _safe_bool_int(record.get("pest_flag") or record.get("pest_detected")),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize crops telemetry snapshots (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="crops_stub", help="Provenance source label")
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
