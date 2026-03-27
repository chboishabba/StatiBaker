#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sb import corkysoft_mcp
from sb.corkysoft_ingest import persist_review_events


def _load_json_payload(*, inline_json: str | None, payload_file: str | None) -> dict[str, Any]:
    if inline_json:
        loaded = json.loads(inline_json)
    elif payload_file:
        loaded = json.loads(Path(payload_file).read_text(encoding="utf-8"))
    else:
        loaded = {}
    if not isinstance(loaded, dict):
        raise SystemExit("tool payload must resolve to a JSON object")
    return loaded


def _load_review_events(path: str) -> list[dict[str, Any]]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        loaded = [loaded]
    if not isinstance(loaded, list):
        raise SystemExit("review-event input must be a JSON object or list")
    records = [item for item in loaded if isinstance(item, dict)]
    if len(records) != len(loaded):
        raise SystemExit("all review-event entries must be objects")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume Corkysoft from the SB/ITIR side.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    mcp_tool = sub.add_parser("mcp-tool", help="Call a read-only Corkysoft MCP tool")
    mcp_tool.add_argument("--tool", required=True)
    mcp_tool.add_argument("--payload-json")
    mcp_tool.add_argument("--payload-file")
    mcp_tool.add_argument("--corkysoft-db", help="Inject db_path into the payload")
    mcp_tool.add_argument("--repo-root", help="Path to Corkysoft repo root")
    mcp_tool.add_argument("--python", dest="python_executable", help="Python executable to run Corkysoft bridge")

    ingest = sub.add_parser("ingest-review-events", help="Persist Corkysoft reviewed-event exports into SB dashboard DB")
    ingest.add_argument("--input", required=True, help="JSON file containing one event object or a list of events")
    ingest.add_argument("--dashboard-db", required=True, help="Path to SB dashboard.sqlite")

    args = parser.parse_args()

    if args.cmd == "mcp-tool":
        payload = _load_json_payload(inline_json=args.payload_json, payload_file=args.payload_file)
        if args.corkysoft_db:
            payload["db_path"] = str(Path(args.corkysoft_db).expanduser().resolve())
        response = corkysoft_mcp.call_tool(
            args.tool,
            payload,
            repo_root=args.repo_root,
            python_executable=args.python_executable,
        )
        print(json.dumps(response, indent=2, sort_keys=True))
        return

    records = _load_review_events(args.input)
    result = persist_review_events(
        db_path=Path(args.dashboard_db).expanduser().resolve(),
        records=records,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
