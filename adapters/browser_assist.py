import argparse
import json
import sys
from typing import Any, Dict, Iterable

from adapters.common import normalize_provenance, sha256_text

DEFAULT_PREVIEW_CHARS = 240


def _collapse_ws(value: Any) -> str:
    return " ".join(str(value or "").split())


def _truncate(value: Any, max_chars: int) -> str | None:
    text = _collapse_ws(value)
    if not text:
        return None
    limit = max(1, int(max_chars))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _hash_or_existing(value: Any, existing: Any = None) -> str | None:
    if existing:
        text = str(existing)
        return text if text.startswith("sha256:") else sha256_text(text)
    if value:
        return sha256_text(str(value))
    return None


def _structure_summary(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "heading_count",
        "heading_text_hash",
        "heading_preview",
        "link_count",
        "form_control_count",
        "image_count",
        "landmark_count",
        "landmark_roles",
    }
    summary = {key: value.get(key) for key in allowed if key in value}
    if isinstance(summary.get("heading_preview"), list):
        summary["heading_preview"] = [_truncate(item, 80) for item in summary["heading_preview"][:5]]
    if isinstance(summary.get("landmark_roles"), list):
        summary["landmark_roles"] = [str(item)[:48] for item in summary["landmark_roles"][:12]]
    return summary


def normalize_record(
    record: Dict[str, Any],
    source: str,
    *,
    metadata_only: bool = False,
    preview_chars: int = DEFAULT_PREVIEW_CHARS,
) -> Dict[str, Any]:
    ts = record.get("ts") or record.get("started_at") or record.get("timestamp")
    if not ts:
        raise ValueError("missing ts")

    storage_mode = str(record.get("storage_mode") or ("metadata_only" if metadata_only else "preview_plus_hashes"))
    suppress_preview = metadata_only or storage_mode == "metadata_only"
    preview = None if suppress_preview else _truncate(record.get("text_preview") or record.get("text"), preview_chars)
    text_hash = _hash_or_existing(record.get("text_preview") or record.get("text"), record.get("text_hash"))

    normalized: Dict[str, Any] = {
        "ts": ts,
        "signal": "browser_assist_activity",
        "version": "browser_assist_activity_v1",
        "session_id": record.get("session_id"),
        "task_label": _truncate(record.get("task_label"), 120),
        "mode": record.get("mode") or "observe",
        "browser": record.get("browser"),
        "started_at": record.get("started_at") or ts,
        "ended_at": record.get("ended_at"),
        "page_url_hash": _hash_or_existing(record.get("page_url") or record.get("url"), record.get("page_url_hash") or record.get("url_hash")),
        "page_title_hash": _hash_or_existing(record.get("page_title") or record.get("title"), record.get("page_title_hash") or record.get("title_hash")),
        "text_preview": preview,
        "text_hash": text_hash,
        "structure_summary": _structure_summary(record.get("structure_summary")),
        "openrecall_entry_refs": list(record.get("openrecall_entry_refs") or record.get("openrecall_refs") or []),
        "playwright_snapshot_refs": list(record.get("playwright_snapshot_refs") or []),
        "screenshot_refs": list(record.get("screenshot_refs") or ([] if not record.get("screenshot_ref") else [record.get("screenshot_ref")])),
        "transcript_refs": list(record.get("transcript_refs") or []),
        "pnf_candidates": [dict(item) for item in (record.get("pnf_candidates") or []) if isinstance(item, dict)],
        "task_identity_residual": record.get("task_identity_residual"),
        "lifecycle_residual": record.get("lifecycle_residual"),
        "kanban_projection_policy": record.get("kanban_projection_policy") or "observer_only",
        "storage_mode": "metadata_only" if suppress_preview else storage_mode,
        "non_authoritative": True,
        "provenance": normalize_provenance(source, {**record, "ts": ts, "collected_at": record.get("collected_at") or ts}),
    }
    return normalized


def normalize_records(
    records: Iterable[Dict[str, Any]],
    source: str,
    *,
    metadata_only: bool = False,
    preview_chars: int = DEFAULT_PREVIEW_CHARS,
) -> Iterable[Dict[str, Any]]:
    for record in records:
        yield normalize_record(
            record,
            source,
            metadata_only=metadata_only,
            preview_chars=preview_chars,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize read-only browser-assist observations.")
    parser.add_argument("--input", required=True, help="Path to raw JSONL input")
    parser.add_argument("--output", required=True, help="Write normalized JSONL output")
    parser.add_argument("--source", default="playwright_browser_assist", help="Provenance source label")
    parser.add_argument("--metadata-only", action="store_true", help="Suppress display previews")
    parser.add_argument("--preview-chars", type=int, default=DEFAULT_PREVIEW_CHARS, help="Maximum preview chars")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        raw = [json.loads(line) for line in handle if line.strip()]

    rows = list(
        normalize_records(
            raw,
            args.source,
            metadata_only=bool(args.metadata_only),
            preview_chars=max(1, args.preview_chars),
        )
    )

    with open(args.output, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
