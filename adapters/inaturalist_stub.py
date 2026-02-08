import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text


def _hash_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("sha256:"):
        return text
    return sha256_text(text)


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_code(value: Any, allowed: set[str], fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    if text in allowed:
        return text
    return fallback


def _coerce_ts(record: Dict[str, Any]) -> str:
    for key in ("ts", "timestamp", "observed_at", "time_observed_at", "created_at"):
        value = record.get(key)
        if value:
            return str(value)
    raise ValueError("missing ts")


def _insect_flag(iconic_taxon: str) -> int:
    return 1 if iconic_taxon == "insecta" else 0


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = _coerce_ts(record)
    # normalize_provenance() expects collected_at or ts/timestamp; iNat exports often
    # use observed_at/created_at, so we inject ts before provenance normalization.
    record_with_ts = dict(record)
    record_with_ts["ts"] = ts

    taxon_id = record.get("taxon_id") or record.get("taxon") or record.get("taxon_name")
    taxon_id_hash = _hash_or_none(record.get("taxon_id_hash") or taxon_id)
    if not taxon_id_hash:
        raise ValueError("missing taxon_id")

    place_id = record.get("place_id") or record.get("place") or record.get("location_cell")
    project_id = record.get("project_id") or record.get("project")

    iconic_taxon_code = _safe_code(
        record.get("iconic_taxon_code")
        or record.get("iconic_taxon_name")
        or record.get("iconic_taxon"),
        {
            "insecta",
            "plantae",
            "aves",
            "mammalia",
            "amphibia",
            "reptilia",
            "actinopterygii",
            "arachnida",
            "mollusca",
            "fungi",
            "unknown",
        },
    )
    quality_grade_code = _safe_code(
        record.get("quality_grade_code") or record.get("quality_grade"),
        {"research", "needs_id", "casual", "unknown"},
    )

    obs_count = _safe_int(record.get("obs_count") or record.get("count") or 1)

    normalized = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "inaturalist",
        "event_type": str(record.get("event_type") or "observation_observed").strip().lower(),
        "taxon_id_hash": taxon_id_hash,
        "place_id_hash": _hash_or_none(record.get("place_id_hash") or place_id),
        "project_id_hash": _hash_or_none(record.get("project_id_hash") or project_id),
        "quality_grade_code": quality_grade_code,
        "iconic_taxon_code": iconic_taxon_code,
        "obs_count": obs_count,
        "insect_flag": _insect_flag(iconic_taxon_code),
        "provenance": normalize_provenance(source, record_with_ts),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize iNaturalist observations (meta-only).")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="inaturalist_stub", help="Provenance source label")
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

