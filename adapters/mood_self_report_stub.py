import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import coerce_ts, normalize_provenance, sha256_text


MOOD_CODES = {
    "calm",
    "neutral",
    "good",
    "joyful",
    "sad",
    "angry",
    "stressed",
    "anxious",
    "overwhelmed",
    "tired",
    "sick",
    "unknown",
}


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


def _safe_mood(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    if text in MOOD_CODES:
        return text
    return "unknown"


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = coerce_ts(record)
    normalized = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "mood",
        "event_type": str(record.get("event_type") or "report_logged").strip().lower(),
        "mood_code": _safe_mood(record.get("mood_code") or record.get("mood")),
        "valence_score": round(_safe_float(record.get("valence_score") or record.get("valence")), 3),
        "arousal_score": round(_safe_float(record.get("arousal_score") or record.get("arousal")), 3),
        "energy_score": round(_safe_float(record.get("energy_score") or record.get("energy")), 3),
        "stress_score": round(_safe_float(record.get("stress_score") or record.get("stress")), 3),
        "anxiety_score": round(_safe_float(record.get("anxiety_score") or record.get("anxiety")), 3),
        "note_id_hash": _hash_or_none(record.get("note_id_hash") or record.get("note_id")),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize mood self-report records (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="mood_self_report_stub", help="Provenance source label")
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

