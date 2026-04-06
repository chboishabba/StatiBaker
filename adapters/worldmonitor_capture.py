import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _hash_or_none(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if text.startswith("sha256:"):
        return text
    return sha256_text(text)


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = _text(record.get("ts") or record.get("capturedAt") or record.get("captured_at") or record.get("timestamp"))
    if not ts:
        raise ValueError("missing ts")

    captured_at = _text(record.get("collected_at") or record.get("capturedAt") or record.get("captured_at") or ts)
    event_type = _text(record.get("event_type") or record.get("event") or "source_observed") or "source_observed"
    source_kind = _text(record.get("source_kind") or record.get("sourceKind") or "unknown") or "unknown"
    capture_id = _text(record.get("capture_id") or record.get("captureId"))
    source_file = _text(record.get("source_file") or record.get("sourceFile"))
    source_row_id = _text(record.get("source_row_id") or record.get("sourceRowId"))
    import_run_id = _text(record.get("import_run_id") or record.get("importRunId"))
    row_label = _text(record.get("row_label") or record.get("rowLabel"))

    provenance_record = dict(record)
    provenance_record["collected_at"] = captured_at or ts

    normalized = {
        "ts": ts,
        "signal": "worldmonitor_capture",
        "event": event_type,
        "event_type": event_type,
        "platform": "worldmonitor",
        "source_kind": source_kind,
        "capture_id_hash": _hash_or_none(capture_id or f"{source_file or ''}|{source_row_id or ''}|{ts}"),
        "source_file_hash": _hash_or_none(source_file),
        "source_row_id_hash": _hash_or_none(source_row_id),
        "import_run_id_hash": _hash_or_none(import_run_id),
        "captured_date": _text(record.get("captured_date") or record.get("capturedDate")),
        "status": _text(record.get("status") or "imported") or "imported",
        "provenance": normalize_provenance(source, provenance_record),
    }
    if row_label:
        normalized["row_label_hash"] = _hash_or_none(row_label)
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize WorldMonitor captures into SB observed signals.")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="worldmonitor_capture_bridge", help="Provenance source label")
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
