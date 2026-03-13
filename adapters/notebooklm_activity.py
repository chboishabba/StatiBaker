import argparse
import json
import sys
from typing import Any, Dict, Iterable

try:
    from adapters.common import normalize_provenance, sha256_text
except ModuleNotFoundError:
    from common import normalize_provenance, sha256_text


def _hash_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("sha256:"):
        return text
    return sha256_text(text)


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")
    event = str(record.get("event_type") or record.get("event") or "").strip().lower()
    if not event:
        raise ValueError("missing event_type")
    normalized = {
        "ts": ts,
        "signal": "notebooklm_activity",
        "app": "notebooklm",
        "event": event,
        "notebook_id_hash": _hash_or_none(record.get("notebook_id")),
        "note_id_hash": _hash_or_none(record.get("note_id")),
        "conversation_id_hash": _hash_or_none(record.get("conversation_id")),
        "provenance": normalize_provenance(source, record),
    }
    notebook_title = _clean_text(record.get("notebook_title"))
    if notebook_title:
        normalized["notebook_title"] = notebook_title
    if event == "conversation_observed":
        query_preview = _clean_text(record.get("query_preview"))
        answer_preview = _clean_text(record.get("answer_preview"))
        conversation_turn_ts = _clean_text(record.get("conversation_turn_ts"))
        if query_preview:
            normalized["query_preview"] = query_preview
        if answer_preview:
            normalized["answer_preview"] = answer_preview
        if conversation_turn_ts:
            normalized["conversation_turn_ts"] = conversation_turn_ts
    if event == "note_observed":
        note_title = _clean_text(record.get("note_title"))
        note_preview = _clean_text(record.get("note_preview"))
        if note_title:
            normalized["note_title"] = note_title
        if note_preview:
            normalized["note_preview"] = note_preview
        note_length = record.get("note_length")
        if isinstance(note_length, int):
            normalized["note_length"] = note_length
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize NotebookLM interaction observations into notebooklm_activity signals."
    )
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="notebooklm_activity", help="Provenance source label")
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
