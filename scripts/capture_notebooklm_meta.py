#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or f"exit={result.returncode}"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{' '.join(command)} returned invalid JSON: {exc}") from exc


def capture_snapshot(
    binary: str = "notebooklm",
    include_sources: bool = True,
    notebook_limit: int = 0,
) -> list[dict[str, Any]]:
    collected_at = _now_utc()
    records: list[dict[str, Any]] = []

    status = _run_json([binary, "status", "--json"])
    records.append(
        {
            "ts": collected_at,
            "collected_at": collected_at,
            "event_type": "context_observed",
            "has_context": bool(status.get("has_context")),
            "notebook_id": (status.get("notebook") or {}).get("id")
            if isinstance(status.get("notebook"), dict)
            else None,
            "conversation_id": status.get("conversation_id"),
        }
    )

    listing = _run_json([binary, "list", "--json"])
    notebooks = listing.get("notebooks") or []
    if notebook_limit > 0:
        notebooks = notebooks[:notebook_limit]

    for notebook in notebooks:
        if not isinstance(notebook, dict):
            continue
        notebook_id = notebook.get("id")
        records.append(
            {
                "ts": collected_at,
                "collected_at": collected_at,
                "event_type": "notebook_observed",
                "notebook_id": notebook_id,
                "notebook_title": notebook.get("title"),
                "is_owner": notebook.get("is_owner"),
                "created_at": notebook.get("created_at"),
            }
        )

        if not include_sources or not notebook_id:
            continue

        source_listing = _run_json([binary, "source", "list", "-n", str(notebook_id), "--json"])
        for source in source_listing.get("sources") or []:
            if not isinstance(source, dict):
                continue
            records.append(
                {
                    "ts": collected_at,
                    "collected_at": collected_at,
                    "event_type": "source_observed",
                    "notebook_id": notebook_id,
                    "source_id": source.get("id"),
                    "source_title": source.get("title"),
                    "source_type": source.get("type"),
                    "source_status": source.get("status"),
                    "source_created_at": source.get("created_at"),
                }
            )

    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture NotebookLM metadata snapshot as JSONL for StatiBaker adapters."
    )
    parser.add_argument("--output", required=True, help="Write JSONL output path")
    parser.add_argument(
        "--binary",
        default="notebooklm",
        help="NotebookLM CLI binary name/path (default: notebooklm)",
    )
    parser.add_argument(
        "--no-sources",
        action="store_true",
        help="Capture only status + notebooks (skip per-notebook source listing).",
    )
    parser.add_argument(
        "--notebook-limit",
        type=int,
        default=0,
        help="Optional cap on notebooks queried for source metadata (0 = all).",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = capture_snapshot(
        binary=args.binary,
        include_sources=not args.no_sources,
        notebook_limit=max(0, args.notebook_limit),
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
