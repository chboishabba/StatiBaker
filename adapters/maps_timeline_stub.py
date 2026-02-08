import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from .common import coerce_ts, normalize_provenance, sha256_text


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_or_none(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return sha256_text(text)


def _coarse_cell_key(lat: float, lon: float, grid_deg: float) -> str:
    # 0.01 degrees is ~1.1km at the equator. We store only the hash of this cell key.
    lat_q = round(lat / grid_deg) * grid_deg
    lon_q = round(lon / grid_deg) * grid_deg
    return f"grid:{grid_deg:.4f}:{lat_q:.4f}:{lon_q:.4f}"


def _location_cell_hash(record: Dict[str, Any], grid_deg: float) -> Optional[str]:
    # Prefer caller-supplied already-hashed cell.
    if record.get("location_cell_hash"):
        return str(record["location_cell_hash"])

    lat = record.get("lat") or record.get("latitude")
    lon = record.get("lon") or record.get("lng") or record.get("longitude")
    try:
        if lat is None or lon is None:
            return None
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return None

    return sha256_text(_coarse_cell_key(lat_f, lon_f, grid_deg))


def normalize_record(record: Dict[str, Any], source: str, provider: str, grid_deg: float) -> Dict[str, Any]:
    ts = coerce_ts(record)
    record_with_ts = dict(record)
    record_with_ts.setdefault("collected_at", record.get("collected_at") or ts or _now_utc_iso())

    event_type = (
        record.get("event_type")
        or record.get("type")
        or record.get("kind")
        or "location_observed"
    )

    normalized: Dict[str, Any] = {
        "ts": ts,
        "signal": "context_field",
        "context_type": "location_timeline",
        "event_type": str(event_type),
        "timeline_provider": provider,
        "provenance": normalize_provenance(source, record_with_ts),
    }

    # Hash-only identifiers.
    normalized["device_id_hash"] = _hash_or_none(record.get("device_id") or record.get("device"))
    normalized["timeline_id_hash"] = _hash_or_none(record.get("timeline_id") or record.get("session_id"))
    normalized["place_id_hash"] = _hash_or_none(record.get("place_id") or record.get("place_key"))
    normalized["visit_id_hash"] = _hash_or_none(record.get("visit_id"))
    normalized["segment_id_hash"] = _hash_or_none(record.get("segment_id"))

    cell_hash = _location_cell_hash(record, grid_deg)
    if cell_hash:
        normalized["location_cell_hash"] = cell_hash

    # Allowed numeric/categorical metadata only.
    if record.get("duration_minutes") is not None:
        try:
            normalized["duration_minutes"] = float(record["duration_minutes"])
        except Exception:
            pass
    if record.get("confidence_code"):
        normalized["confidence_code"] = str(record["confidence_code"])
    if record.get("travel_mode_code"):
        normalized["travel_mode_code"] = str(record["travel_mode_code"])

    # Optional time bounds (no location strings).
    if record.get("start_ts"):
        normalized["start_ts"] = str(record["start_ts"])
    if record.get("end_ts"):
        normalized["end_ts"] = str(record["end_ts"])

    # Strip nulls for compact JSONL.
    return {k: v for k, v in normalized.items() if v is not None}


def normalize_records(records: Iterable[Dict[str, Any]], source: str, provider: str, grid_deg: float):
    for record in records:
        yield normalize_record(record, source=source, provider=provider, grid_deg=grid_deg)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Google/Apple maps timeline exports into meta-only context_field overlays."
    )
    parser.add_argument("--input", required=True, help="Input JSONL file")
    parser.add_argument("--output", required=True, help="Output JSONL file")
    parser.add_argument("--source", default="maps_timeline_stub", help="Provenance source label")
    parser.add_argument(
        "--provider",
        default="google_maps",
        help="Label only (google_maps|apple_maps|other); does not change parsing",
    )
    parser.add_argument(
        "--grid-deg",
        type=float,
        default=0.01,
        help="Coarsening grid in degrees for lat/lon hashing (default ~1km at equator)",
    )

    args = parser.parse_args(argv)
    with open(args.input, "r", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]

    normalized = list(normalize_records(rows, source=args.source, provider=args.provider, grid_deg=args.grid_deg))
    with open(args.output, "w", encoding="utf-8") as out:
        for row in normalized:
            out.write(json.dumps(row, sort_keys=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

