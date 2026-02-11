import argparse
import json
import sys
from typing import Any, Dict, Iterable

try:
    from adapters.common import normalize_provenance, sha256_text
except ModuleNotFoundError:
    # Supports direct execution: `python adapters/notebooklm_meta.py ...`
    from common import normalize_provenance, sha256_text


def _hash_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("sha256:"):
        return text
    return sha256_text(text)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_str_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    out: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text:
            out.append(text)
    return out or None


def _normalize_event_name(record: Dict[str, Any]) -> str:
    event_name = str(record.get("event_type") or record.get("event") or "").strip()
    if event_name:
        return event_name
    if record.get("artifact_id") is not None:
        return "artifact_observed"
    if record.get("source_id") or record.get("source"):
        return "source_observed"
    if record.get("conversation_id") is not None:
        return "context_observed"
    return "notebook_observed"


def normalize_record(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    notebook_id = record.get("notebook_id")
    if notebook_id is None and isinstance(record.get("notebook"), dict):
        notebook_id = record["notebook"].get("id")

    source_id = record.get("source_id")
    if source_id is None and isinstance(record.get("source"), dict):
        source_id = record["source"].get("id")

    conversation_id = record.get("conversation_id")
    if conversation_id is None and isinstance(record.get("context"), dict):
        conversation_id = record["context"].get("conversation_id")

    artifact_id = record.get("artifact_id")

    normalized = {
        "ts": ts,
        "signal": "notes_meta",
        "app": "notebooklm",
        "note_id_hash": _hash_or_none(
            source_id or conversation_id or record.get("note_id") or artifact_id
        ),
        "vault_id_hash": _hash_or_none(record.get("account_id") or record.get("owner_id")),
        "notebook_id_hash": _hash_or_none(
            notebook_id or record.get("notebook_uuid") or record.get("notebook")
        ),
        "event": _normalize_event_name(record),
        "provenance": normalize_provenance(source, record),
    }

    notebook_title = _clean_text(record.get("notebook_title"))
    source_title = _clean_text(record.get("source_title"))
    source_type = _clean_text(record.get("source_type"))
    source_status = _clean_text(record.get("source_status"))
    source_created_at = _clean_text(record.get("source_created_at"))
    source_url = _clean_text(record.get("source_url"))
    source_summary = _clean_text(record.get("source_summary"))
    source_keywords = _clean_str_list(record.get("source_keywords"))
    artifact_title = _clean_text(record.get("artifact_title"))
    artifact_type = _clean_text(record.get("artifact_type"))
    artifact_status = _clean_text(record.get("artifact_status"))
    artifact_created_at = _clean_text(record.get("artifact_created_at"))

    if notebook_title:
        normalized["notebook_title"] = notebook_title
    if source_title:
        normalized["source_title"] = source_title
    if source_type:
        normalized["source_type"] = source_type
    if source_status:
        normalized["source_status"] = source_status
    if source_created_at:
        normalized["source_created_at"] = source_created_at
    if source_url:
        normalized["source_url"] = source_url
    if source_summary:
        normalized["source_summary"] = source_summary
    if source_keywords:
        normalized["source_keywords"] = source_keywords

    if artifact_id is not None:
        normalized["artifact_id_hash"] = _hash_or_none(artifact_id)
    if artifact_title:
        normalized["artifact_title"] = artifact_title
    if artifact_type:
        normalized["artifact_type"] = artifact_type
    if artifact_status:
        normalized["artifact_status"] = artifact_status
    if artifact_created_at:
        normalized["artifact_created_at"] = artifact_created_at

    has_context = record.get("has_context")
    if isinstance(has_context, bool):
        normalized["has_context"] = has_context

    return normalized


def _expand_records(record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    ts = record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    if isinstance(record.get("notebooks"), list):
        for notebook in record["notebooks"]:
            if not isinstance(notebook, dict):
                continue
            yield {
                "ts": ts,
                "collected_at": record.get("collected_at") or ts,
                "event_type": "notebook_observed",
                "notebook_id": notebook.get("id"),
                "notebook_title": notebook.get("title"),
                "is_owner": notebook.get("is_owner"),
            }
        return

    if isinstance(record.get("sources"), list):
        notebook_id = record.get("notebook_id")
        notebook_title = record.get("notebook_title")
        for source in record["sources"]:
            if not isinstance(source, dict):
                continue
            yield {
                "ts": ts,
                "collected_at": record.get("collected_at") or ts,
                "event_type": "source_observed",
                "notebook_id": notebook_id,
                "notebook_title": notebook_title,
                "source_id": source.get("id"),
                "source_title": source.get("title"),
                "source_type": source.get("type"),
                "source_status": source.get("status"),
                "source_created_at": source.get("created_at"),
                "source_url": source.get("url"),
            }
        return

    if isinstance(record.get("artifacts"), list):
        notebook_id = record.get("notebook_id")
        notebook_title = record.get("notebook_title")
        for artifact in record["artifacts"]:
            if not isinstance(artifact, dict):
                continue
            yield {
                "ts": ts,
                "collected_at": record.get("collected_at") or ts,
                "event_type": "artifact_observed",
                "notebook_id": notebook_id,
                "notebook_title": notebook_title,
                "artifact_id": artifact.get("id"),
                "artifact_title": artifact.get("title"),
                "artifact_type": artifact.get("type"),
                "artifact_status": artifact.get("status"),
                "artifact_created_at": artifact.get("created_at"),
            }
        return

    yield record


def normalize_records(records: Iterable[Dict[str, Any]], source: str) -> Iterable[Dict[str, Any]]:
    for record in records:
        for expanded in _expand_records(record):
            yield normalize_record(expanded, source)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize NotebookLM metadata snapshots into notes_meta signals."
    )
    parser.add_argument("--input", required=True, help="Path to JSONL input")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--source", default="notebooklm_meta", help="Provenance source label")
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
