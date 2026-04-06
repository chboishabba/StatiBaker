#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

_THIS_DIR = Path(__file__).resolve().parent
_SB_ROOT = _THIS_DIR.parent
_SUITE_ROOT = _SB_ROOT.parent
_SENSIBLAW_ROOT = _SUITE_ROOT / "SensibLaw"
_SENSIBLAW_SRC = _SENSIBLAW_ROOT / "src"

for path in (_SB_ROOT, _SUITE_ROOT, _SENSIBLAW_ROOT, _SENSIBLAW_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters.worldmonitor_capture import normalize_record


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _build_where(import_run_id: str | None, date: str | None) -> tuple[str, list[object]]:
    where: list[str] = []
    params: list[object] = []
    if import_run_id is not None:
        where.append("s.import_run_id = ?")
        params.append(import_run_id)
    if date is not None:
        where.append("s.captured_date = ?")
        params.append(date)
    return (f"WHERE {' AND '.join(where)}" if where else "", params)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export WorldMonitor captures from itir.sqlite as SB observed-signal JSONL."
    )
    parser.add_argument("--itir-db-path", type=Path, required=True, help="Path to the ITIR SQLite DB")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL path")
    parser.add_argument("--import-run-id", default=None, help="Optional import_run_id filter")
    parser.add_argument("--date", default=None, help="Optional captured_date filter (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=None, help="Optional max row count")
    parser.add_argument("--source", default="worldmonitor_capture_bridge", help="Provenance source label")
    args = parser.parse_args(argv)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with _connect(args.itir_db_path) as conn:
        where_sql, params = _build_where(args.import_run_id, args.date)
        sql = f"""
            SELECT
              s.capture_id,
              s.import_run_id,
              s.captured_at,
              s.captured_date,
              s.source_file,
              s.source_row_id,
              s.source_kind,
              s.row_label
            FROM worldmonitor_capture_sources s
            {where_sql}
            ORDER BY s.source_timestamp ASC, s.capture_id ASC
        """
        if args.limit is not None:
            sql += " LIMIT ?"
            params.append(int(args.limit))
        rows = conn.execute(sql, tuple(params)).fetchall()

    with args.output.open("w", encoding="utf-8") as handle:
        export_count = 0
        for row in rows:
            normalized = normalize_record(
                {
                    "ts": row["captured_at"],
                    "capturedAt": row["captured_at"],
                    "captured_date": row["captured_date"],
                    "importRunId": row["import_run_id"],
                    "captureId": row["capture_id"],
                    "sourceFile": row["source_file"],
                    "sourceRowId": row["source_row_id"],
                    "sourceKind": row["source_kind"],
                    "rowLabel": row["row_label"],
                    "event_type": "source_observed",
                    "status": "imported",
                },
                args.source,
            )
            handle.write(json.dumps(normalized, sort_keys=True) + "\n")
            export_count += 1

    payload = {
        "ok": True,
        "itirDbPath": str(args.itir_db_path.resolve()),
        "outputPath": str(args.output.resolve()),
        "exportCount": export_count,
        "importRunId": args.import_run_id,
        "date": args.date,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
