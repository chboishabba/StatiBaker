#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb.kanboard_runsheet import build_dry_run_plan, build_sync_report, load_local_rows


def _read_existing(path: str | None) -> dict[str, dict]:
    if not path:
        return {}
    target = Path(path).expanduser().resolve()
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("existing snapshot must be a JSON object keyed by stable_id")
    return {str(key): dict(value) for key, value in payload.items() if isinstance(value, dict)}


def _read_column_map(path: str | None) -> dict[str, object]:
    if not path:
        return {}
    target = Path(path).expanduser().resolve()
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("column map must be a JSON object keyed by status")
    wrapped = payload.get("column_map")
    if isinstance(wrapped, dict):
        return wrapped
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Kanboard JSON-RPC dry-run plan from local runsheet JSON.")
    parser.add_argument("--input", required=True, help="Status/runsheet JSON path")
    parser.add_argument("--project-id", required=True, type=int, help="Kanboard project id")
    parser.add_argument("--existing", help="Optional JSON mapping stable_id -> existing Kanboard task fields")
    parser.add_argument("--column-map", help="Optional JSON mapping status -> column config/id")
    parser.add_argument("--now", help="Override sync timestamp (ISO-8601)")
    parser.add_argument("--output", help="Write plan JSON to path (stdout if omitted)")
    parser.add_argument("--report-output", help="Optional path to write a Kanboard sync report JSON artifact")
    args = parser.parse_args()

    payload = load_local_rows(args.input)
    now_iso = args.now or datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    plan = build_dry_run_plan(
        payload["rows"],
        project_id=args.project_id,
        now_iso=now_iso,
        existing_by_reference=_read_existing(args.existing),
        column_by_status=_read_column_map(args.column_map),
    )
    plan["input_source"] = {
        "path": payload["source_path"],
    }

    rendered = json.dumps(plan, indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")

    if args.report_output:
        report_target = Path(args.report_output).expanduser().resolve()
        report_target.parent.mkdir(parents=True, exist_ok=True)
        report = build_sync_report(
            plan=plan,
            input_source_path=payload["source_path"],
            report_path=str(report_target),
            now_iso=now_iso,
        )
        report_target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not args.output:
        print(rendered)


if __name__ == "__main__":
    main()
