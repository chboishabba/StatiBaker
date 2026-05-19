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

from sb.kanboard_runsheet import (
    DEFAULT_KANBOARD_ENV_PATH,
    KanboardJsonRpcClient,
    apply_sync_plan,
    build_dry_run_plan,
    build_sync_report,
    fetch_existing_by_reference,
    load_kanboard_env,
    load_local_rows,
)


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
    parser = argparse.ArgumentParser(
        description="Sync local runsheet JSON to Kanboard with dry-run default and explicit --apply mutation."
    )
    parser.add_argument("--input", required=True, help="Status/runsheet JSON path")
    parser.add_argument("--project-id", type=int, help="Kanboard project id (defaults to env file value)")
    parser.add_argument("--existing", help="Optional JSON mapping stable_id -> existing Kanboard task fields")
    parser.add_argument("--column-map", help="Optional JSON mapping status -> column config/id")
    parser.add_argument("--env-file", default=DEFAULT_KANBOARD_ENV_PATH, help="Local private Kanboard env file path")
    parser.add_argument("--now", help="Override sync timestamp (ISO-8601)")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="JSON-RPC timeout for --apply")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Fetch existing Kanboard tasks by reference before planning updates/moves/tags",
    )
    parser.add_argument("--apply", action="store_true", help="Mutate Kanboard using JSON-RPC apply order")
    parser.add_argument("--report-out", help="Write sync report JSON to path")
    parser.add_argument("--output", help="Write final payload JSON to path (stdout if omitted)")
    args = parser.parse_args()

    loaded = load_local_rows(args.input)
    env_config = load_kanboard_env(args.env_file)
    project_id = args.project_id if args.project_id is not None else env_config.get("project_id")
    if project_id in (None, ""):
        raise ValueError("project id required via --project-id or KANBOARD_PROJECT_ID in env file")

    now_iso = args.now or datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    existing_by_reference = _read_existing(args.existing)
    client = None
    if args.refresh_existing:
        client = KanboardJsonRpcClient.from_env(env_config, timeout_seconds=args.timeout_seconds)
        existing_by_reference.update(
            fetch_existing_by_reference(
                loaded["rows"],
                project_id=int(project_id),
                rpc_call=client.call,
            )
        )

    plan = build_dry_run_plan(
        loaded["rows"],
        project_id=int(project_id),
        now_iso=now_iso,
        existing_by_reference=existing_by_reference,
        column_by_status=_read_column_map(args.column_map),
    )
    plan["input_source"] = {"path": loaded["source_path"]}

    apply_report = None
    if args.apply:
        if client is None:
            client = KanboardJsonRpcClient.from_env(env_config, timeout_seconds=args.timeout_seconds)
        apply_report = apply_sync_plan(plan, client.call)
        plan["mode"] = "apply"
        plan["authority_boundary"] = {
            "mutates_kanboard": True,
            "kanboard_is_not_source_of_truth": True,
        }

    report = build_sync_report(
        plan=plan,
        input_source_path=loaded["source_path"],
        report_path=str(Path(args.report_out).expanduser().resolve()) if args.report_out else "",
        now_iso=now_iso,
        errors=apply_report["errors"] if apply_report else None,
        apply_report=apply_report,
    )
    if args.report_out:
        target = Path(args.report_out).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload = {
        "schema_version": "sb.kanboard_sync_result.v0_1",
        "mode": plan["mode"],
        "plan": plan,
        "apply_report": apply_report,
        "sync_report": report,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
        return
    print(rendered)


if __name__ == "__main__":
    main()
