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
    return 1 if text in {"1", "true", "yes", "on"} else 0


def _safe_code(value: Any, allowed: set[str], fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    if text in allowed:
        return text
    return fallback


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = coerce_ts(record)
    normalized = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "medication",
        "event_type": str(record.get("event_type") or record.get("action") or "dose_observed").strip().lower(),
        "tracker_id_hash": _hash_or_none(record.get("tracker_id_hash") or record.get("tracker_id") or record.get("app_id")),
        "medication_id_hash": _hash_or_none(
            record.get("medication_id_hash")
            or record.get("medication_id")
            or record.get("medication_code")
            or record.get("medication_name")
        ),
        "schedule_id_hash": _hash_or_none(record.get("schedule_id_hash") or record.get("schedule_id")),
        "intake_id_hash": _hash_or_none(record.get("intake_id_hash") or record.get("intake_id") or record.get("dose_id")),
        "route_code": _safe_code(
            record.get("route_code") or record.get("route"),
            {
                "oral",
                "topical",
                "inhaled",
                "injection",
                "transdermal",
                "ophthalmic",
                "otic",
                "nasal",
                "sublingual",
                "buccal",
                "rectal",
                "vaginal",
            },
        ),
        "dose_amount": round(_safe_float(record.get("dose_amount") or record.get("dose_value") or record.get("dose_mg")), 3),
        "dose_unit": _safe_code(
            record.get("dose_unit") or ("mg" if record.get("dose_mg") is not None else None),
            {"mg", "mcg", "g", "ml", "iu", "tablet", "capsule", "puff", "drop", "patch"},
        ),
        "adherence_flag": _safe_bool_int(record.get("adherence_flag") or record.get("taken_flag") or record.get("taken")),
        "missed_flag": _safe_bool_int(record.get("missed_flag")),
        "prn_flag": _safe_bool_int(record.get("prn_flag") or record.get("is_prn")),
        "delay_minutes": round(_safe_float(record.get("delay_minutes")), 3),
        "symptom_score": round(_safe_float(record.get("symptom_score")), 3),
        "side_effect_flag": _safe_bool_int(record.get("side_effect_flag")),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize medication tracker snapshots (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="medication_tracker_stub", help="Provenance source label")
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
