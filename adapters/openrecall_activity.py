import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator

try:
    from adapters.common import normalize_provenance
except ModuleNotFoundError:
    from common import normalize_provenance


DEFAULT_BASE_URL = "http://127.0.0.1:8082"

BROWSER_TOKENS = ("firefox", "chrome", "chromium", "brave", "edge", "safari", "browser")
COMMUNICATION_TOKENS = (
    "discord",
    "slack",
    "signal",
    "telegram",
    "whatsapp",
    "teams",
    "mail",
    "thunderbird",
    "outlook",
)
EDITOR_TOKENS = (
    "code",
    "codium",
    "cursor",
    "pycharm",
    "idea",
    "vim",
    "nvim",
    "emacs",
    "sublime",
    "kate",
    "gedit",
    "notepad++",
)
RESEARCH_TOKENS = (
    "github",
    "wikipedia",
    "stackoverflow",
    "docs",
    "readme",
    "notebooklm",
    "paper",
    "manual",
)


def _collapse_ws(value: Any) -> str:
    return " ".join(str(value or "").split())


def _truncate(text: str, max_chars: int) -> str:
    collapsed = _collapse_ws(text)
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 1].rstrip() + "…"


def _build_entry_url(base_url: str, entry_id: int) -> str:
    return f"{base_url.rstrip('/')}/entry/{int(entry_id)}"


def _classify_activity_kind(app: str, title: str, preview: str) -> str:
    haystack = " ".join(part.lower() for part in (app, title, preview) if part)
    if not haystack.strip():
        return "idle_or_background_capture"
    if any(token in haystack for token in COMMUNICATION_TOKENS):
        return "communication_activity"
    if any(token in haystack for token in EDITOR_TOKENS):
        return "editor_activity"
    if any(token in haystack for token in RESEARCH_TOKENS):
        return "research_activity"
    if any(token in haystack for token in BROWSER_TOKENS):
        return "browser_activity"
    return "screen_activity"


def _iter_rows_for_date(conn: sqlite3.Connection, captured_date: str) -> Iterator[sqlite3.Row]:
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()
    }
    captured_date_expr = (
        "captured_date"
        if "captured_date" in columns
        else "date(timestamp, 'unixepoch')"
    )
    normalized_text_expr = (
        "normalized_text" if "normalized_text" in columns else "NULL AS normalized_text"
    )
    query = f"""
        SELECT
            id,
            app,
            title,
            text,
            {captured_date_expr} AS captured_date,
            timestamp,
            {normalized_text_expr}
        FROM entries
        WHERE {captured_date_expr} = ?
        ORDER BY timestamp ASC, id ASC
    """
    for row in conn.execute(query, (captured_date,)).fetchall():
        yield row


def normalize_record(
    row: sqlite3.Row,
    *,
    source: str,
    screenshots_dir: Path,
    base_url: str,
    device_id: str | None,
    session_id: str | None,
    preview_chars: int,
) -> Dict[str, Any]:
    entry_id = int(row["id"])
    timestamp = int(row["timestamp"])
    app = _collapse_ws(row["app"])
    title = _collapse_ws(row["title"])
    raw_text = row["normalized_text"] or row["text"] or ""
    preview = _truncate(raw_text, preview_chars)
    capture_matches = sorted(screenshots_dir.glob(f"{timestamp}*"))
    activity_kind = _classify_activity_kind(app, title, preview)
    record: Dict[str, Any] = {
        "ts": timestamp,
        "signal": "openrecall_activity",
        "captured_date": str(row["captured_date"] or ""),
        "timestamp": timestamp,
        "entry_id": entry_id,
        "app": app or None,
        "window_title": title or None,
        "ocr_preview": preview or None,
        "activity_kind": activity_kind,
        "screenshot_present": bool(capture_matches),
        "capture_count": len(capture_matches),
        "source_ref": f"openrecall.entry:{entry_id}",
        "deep_link": _build_entry_url(base_url, entry_id),
        "provenance": normalize_provenance(
            source,
            {
                "timestamp": datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z"),
                "collected_at": datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z"),
            },
        ),
    }
    if device_id:
        record["device_id"] = device_id
    if session_id:
        record["session_id"] = session_id
    return record


def export_day(
    *,
    db_path: Path,
    captured_date: str,
    screenshots_dir: Path,
    base_url: str,
    device_id: str | None,
    session_id: str | None,
    source: str,
    preview_chars: int,
) -> list[Dict[str, Any]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return [
            normalize_record(
                row,
                source=source,
                screenshots_dir=screenshots_dir,
                base_url=base_url,
                device_id=device_id,
                session_id=session_id,
                preview_chars=preview_chars,
            )
            for row in _iter_rows_for_date(conn, captured_date)
        ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export bounded OpenRecall activity rows for StatiBaker daily-bake ingestion."
    )
    parser.add_argument("--db-path", required=True, help="Path to OpenRecall recall.db")
    parser.add_argument("--date", required=True, help="Captured date in YYYY-MM-DD")
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument(
        "--screenshots-dir",
        help="Optional screenshots directory (default: sibling screenshots/ next to recall.db)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OpenRecall base URL for entry deep links (default: http://127.0.0.1:8082)",
    )
    parser.add_argument("--device-id", default=None, help="Optional device identifier")
    parser.add_argument("--session-id", default=None, help="Optional session identifier")
    parser.add_argument("--preview-chars", type=int, default=160, help="Maximum OCR preview chars")
    parser.add_argument("--source", default="openrecall_activity", help="Provenance source label")
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    screenshots_dir = (
        Path(args.screenshots_dir).expanduser().resolve()
        if args.screenshots_dir
        else (db_path.parent / "screenshots").resolve()
    )
    rows = export_day(
        db_path=db_path,
        captured_date=args.date,
        screenshots_dir=screenshots_dir,
        base_url=args.base_url,
        device_id=args.device_id,
        session_id=args.session_id,
        source=args.source,
        preview_chars=max(32, int(args.preview_chars)),
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
