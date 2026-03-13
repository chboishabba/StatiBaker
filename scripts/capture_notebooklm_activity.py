#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKLM_SRC = REPO_ROOT / "notebooklm-py" / "src"
if NOTEBOOKLM_SRC.exists():
    sys.path.insert(0, str(NOTEBOOKLM_SRC))

from notebooklm import NotebookLMClient  # type: ignore  # noqa: E402


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _truncate_text(value: Any, max_chars: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    limit = max(1, max_chars)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _conversation_items(history: Any) -> list[list[Any]]:
    if not isinstance(history, list):
        return []
    if history and all(isinstance(item, list) for item in history):
        if history and history[0] and all(isinstance(item, list) for item in history[0]):
            return [item for item in history[0] if isinstance(item, list)]
        return [item for item in history if isinstance(item, list)]
    return []


def build_conversation_records(
    *,
    collected_at: str,
    notebook_id: str,
    notebook_title: str | None,
    history: Any,
    preview_chars: int,
    history_limit: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _conversation_items(history)[: max(0, history_limit)]:
        if not item:
            continue
        conversation_id = str(item[0]).strip() if item[0] is not None else ""
        if not conversation_id:
            continue
        records.append(
            {
                "ts": collected_at,
                "collected_at": collected_at,
                "event_type": "conversation_observed",
                "notebook_id": notebook_id,
                "notebook_title": notebook_title,
                "conversation_id": conversation_id,
                "query_preview": _truncate_text(item[1] if len(item) > 1 else None, preview_chars),
                "answer_preview": _truncate_text(item[2] if len(item) > 2 else None, preview_chars),
                "conversation_turn_ts": _iso_or_none(item[3] if len(item) > 3 else None),
            }
        )
    return records


def build_note_records(
    *,
    collected_at: str,
    notebook_id: str,
    notebook_title: str | None,
    notes: list[Any],
    preview_chars: int,
    note_limit: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for note in notes[: max(0, note_limit)]:
        note_id = str(getattr(note, "id", "") or "").strip()
        if not note_id:
            continue
        content_text = str(getattr(note, "content", "") or "")
        records.append(
            {
                "ts": collected_at,
                "collected_at": collected_at,
                "event_type": "note_observed",
                "notebook_id": notebook_id,
                "notebook_title": notebook_title,
                "note_id": note_id,
                "note_title": _truncate_text(getattr(note, "title", None), preview_chars),
                "note_preview": _truncate_text(content_text, preview_chars),
                "note_length": len(content_text),
            }
        )
    return records


async def capture_activity(
    *,
    storage_path: str | None = None,
    notebook_limit: int = 0,
    history_limit: int = 10,
    note_limit: int = 20,
    preview_chars: int = 280,
) -> list[dict[str, Any]]:
    collected_at = _now_utc()
    records: list[dict[str, Any]] = []
    async with await NotebookLMClient.from_storage(storage_path) as client:
        notebooks = await client.notebooks.list()
        if notebook_limit > 0:
            notebooks = notebooks[:notebook_limit]
        for notebook in notebooks:
            notebook_id = str(getattr(notebook, "id", "") or "").strip()
            if not notebook_id:
                continue
            notebook_title = _truncate_text(getattr(notebook, "title", None), preview_chars)
            try:
                history = await client.chat.get_history(notebook_id, limit=max(1, history_limit))
            except Exception:
                history = []
            records.extend(
                build_conversation_records(
                    collected_at=collected_at,
                    notebook_id=notebook_id,
                    notebook_title=notebook_title,
                    history=history,
                    preview_chars=preview_chars,
                    history_limit=history_limit,
                )
            )
            try:
                notes = await client.notes.list(notebook_id)
            except Exception:
                notes = []
            records.extend(
                build_note_records(
                    collected_at=collected_at,
                    notebook_id=notebook_id,
                    notebook_title=notebook_title,
                    notes=notes,
                    preview_chars=preview_chars,
                    note_limit=note_limit,
                )
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture NotebookLM interaction observations (conversation history + notes) as JSONL."
    )
    parser.add_argument("--output", required=True, help="Write JSONL output path")
    parser.add_argument("--storage", default=None, help="Optional NotebookLM storage_state.json path")
    parser.add_argument("--notebook-limit", type=int, default=0, help="Optional cap on notebooks queried (0 = all)")
    parser.add_argument("--history-limit", type=int, default=10, help="Max history rows per notebook (default: 10)")
    parser.add_argument("--note-limit", type=int, default=20, help="Max notes per notebook (default: 20)")
    parser.add_argument("--preview-chars", type=int, default=280, help="Max chars for previews (default: 280)")
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = asyncio.run(
        capture_activity(
            storage_path=args.storage,
            notebook_limit=max(0, args.notebook_limit),
            history_limit=max(1, args.history_limit),
            note_limit=max(1, args.note_limit),
            preview_chars=max(1, args.preview_chars),
        )
    )
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(output_path)
    print(f"records={len(records)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
