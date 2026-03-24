import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status_from_record(record: Dict[str, Any]) -> str:
    value = _text(record.get("status") or record.get("state")).lower()
    if value in {"completed", "complete", "done", "checked"}:
        return "completed"
    if value in {"archived", "deleted", "removed"}:
        return "archived"
    if isinstance(record.get("checked"), bool):
        return "completed" if bool(record.get("checked")) else "open"
    return "open" if value in {"", "open", "pending"} else "unknown"


def _voice_origin(record: Dict[str, Any]) -> str:
    value = _text(record.get("voice_origin") or record.get("origin") or record.get("capture_source")).lower()
    if value in {"", "keep_list", "assistant", "google_assistant", "google_home", "voice"}:
        return "keep_list"
    return "unknown"


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp") or record.get("updated_at") or record.get("created_at")
    if not ts:
        raise ValueError("missing ts")

    title = _text(record.get("title") or record.get("item_title") or record.get("text"))
    if not title:
        raise ValueError("missing title")

    external_item_id = _text(record.get("external_item_id") or record.get("item_id") or record.get("id"))
    if not external_item_id:
        external_item_id = f"generated:{sha256_text('|'.join([title, _text(record.get('list_id')), str(ts)]))}"

    external_list_id = _text(record.get("external_list_id") or record.get("list_id") or record.get("list_name"))
    if not external_list_id:
        external_list_id = "keep:list"

    external_account_id = _text(record.get("external_account_id") or record.get("account_id") or record.get("account"))
    if not external_account_id:
        external_account_id = "google:default"

    normalized = {
        "ts": ts,
        "signal": "external_commitment",
        "version": "external_commitment_event_v1",
        "source_system": "google",
        "source_kind": "google_keep_list_item",
        "external_account_id": external_account_id,
        "external_list_id": external_list_id,
        "external_item_id": external_item_id,
        "title": title,
        "notes_excerpt": _text(record.get("notes_excerpt") or record.get("note") or record.get("description")),
        "status": _status_from_record(record),
        "due_at": record.get("due_at") or record.get("due"),
        "voice_origin": _voice_origin(record),
        "source_created_at": record.get("source_created_at") or record.get("created_at"),
        "source_updated_at": record.get("source_updated_at") or record.get("updated_at"),
        "raw_locator": record.get("raw_locator") or record.get("self_link") or record.get("url"),
        "provenance": normalize_provenance(source, record),
    }
    return normalized


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(record, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Google Keep/list item records into external commitments.")
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="google_keep_lists", help="Provenance source label")
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
