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


def _run_json_soft(command: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or f"exit={result.returncode}"
        return None, detail
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def _warn(message: str) -> None:
    print(f"warn: {message}", file=sys.stderr)


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


def capture_snapshot(
    binary: str = "notebooklm",
    include_sources: bool = True,
    include_artifacts: bool = True,
    include_source_guides: bool = False,
    source_snippet_chars: int = 600,
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
            pass
        else:
            source_listing, source_error = _run_json_soft(
                [binary, "source", "list", "-n", str(notebook_id), "--json"]
            )
            if source_error:
                _warn(f"source list failed for notebook {notebook_id}: {source_error}")
            else:
                for source in (source_listing or {}).get("sources") or []:
                    if not isinstance(source, dict):
                        continue

                    source_record: dict[str, Any] = {
                        "ts": collected_at,
                        "collected_at": collected_at,
                        "event_type": "source_observed",
                        "notebook_id": notebook_id,
                        "notebook_title": notebook.get("title"),
                        "source_id": source.get("id"),
                        "source_title": source.get("title"),
                        "source_type": source.get("type"),
                        "source_status": source.get("status"),
                        "source_created_at": source.get("created_at"),
                        "source_url": source.get("url"),
                    }

                    source_id = source.get("id")
                    if include_source_guides and source_id:
                        guide, guide_error = _run_json_soft(
                            [binary, "source", "guide", str(source_id), "-n", str(notebook_id), "--json"]
                        )
                        if guide_error:
                            _warn(f"source guide failed for source {source_id}: {guide_error}")
                        elif isinstance(guide, dict):
                            source_record["source_summary"] = _truncate_text(
                                guide.get("summary"), source_snippet_chars
                            )
                            keywords = guide.get("keywords")
                            if isinstance(keywords, list):
                                source_record["source_keywords"] = [
                                    str(k).strip() for k in keywords if str(k).strip()
                                ]

                    records.append(source_record)

        if include_artifacts and notebook_id:
            artifact_listing, artifact_error = _run_json_soft(
                [binary, "artifact", "list", "-n", str(notebook_id), "--json"]
            )
            if artifact_error:
                _warn(f"artifact list failed for notebook {notebook_id}: {artifact_error}")
            else:
                for artifact in (artifact_listing or {}).get("artifacts") or []:
                    if not isinstance(artifact, dict):
                        continue
                    records.append(
                        {
                            "ts": collected_at,
                            "collected_at": collected_at,
                            "event_type": "artifact_observed",
                            "notebook_id": notebook_id,
                            "notebook_title": notebook.get("title"),
                            "artifact_id": artifact.get("id"),
                            "artifact_title": artifact.get("title"),
                            "artifact_type": artifact.get("type"),
                            "artifact_type_id": artifact.get("type_id"),
                            "artifact_status": artifact.get("status"),
                            "artifact_status_id": artifact.get("status_id"),
                            "artifact_created_at": artifact.get("created_at"),
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
        "--no-artifacts",
        action="store_true",
        help="Skip per-notebook artifact listing.",
    )
    parser.add_argument(
        "--with-source-guides",
        action="store_true",
        help="Include source guide summary/keywords snippets (additional API calls).",
    )
    parser.add_argument(
        "--source-snippet-chars",
        type=int,
        default=600,
        help="Max chars for source guide summary snippets (default: 600).",
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
        include_artifacts=not args.no_artifacts,
        include_source_guides=bool(args.with_source_guides),
        source_snippet_chars=max(1, args.source_snippet_chars),
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
