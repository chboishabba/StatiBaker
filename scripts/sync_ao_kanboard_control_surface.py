#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb.ao_kanboard_control import AO_CONTROL_STATUS_COLUMNS, build_ao_control_runsheet
from sb.kanboard_bootstrap import (
    KanboardRpcClient,
    bootstrap_board,
    parse_env_file,
    resolve_runtime_config,
    write_json,
)
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

DEFAULT_OUTPUT_DIR = ROOT / "runs_local" / "kanboard"


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: str | Path, payload: dict) -> str:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(target)


def _bootstrap_control_columns(args: argparse.Namespace) -> dict:
    env = parse_env_file(args.env_file)
    config = resolve_runtime_config(
        env,
        {
            "KANBOARD_JSONRPC_ENDPOINT": args.endpoint,
            "KANBOARD_PROJECT_ID": args.project_id,
            "KANBOARD_PROJECT_NAME": args.project_name,
            "KANBOARD_API_USER": args.api_user,
            "KANBOARD_API_TOKEN": args.api_token,
            "KANBOARD_API_AUTH_HEADER": args.api_auth_header,
        },
    )
    if not config.endpoint:
        raise ValueError("missing Kanboard endpoint")
    if not config.api_token:
        raise ValueError("missing Kanboard API token")
    client = KanboardRpcClient(
        endpoint=config.endpoint,
        api_user=config.api_user,
        api_token=config.api_token,
        api_auth_header=config.api_auth_header,
        timeout_seconds=args.timeout_seconds,
    )
    report = bootstrap_board(
        client,
        project_id=config.project_id,
        project_name=config.project_name,
        apply=args.apply,
        required_columns=AO_CONTROL_STATUS_COLUMNS,
    )
    report["input"] = {
        "env_file": str(Path(args.env_file).expanduser()),
        "endpoint": config.endpoint,
        "project_id": config.project_id,
        "project_name": config.project_name,
    }
    write_json(args.bootstrap_report_out, report)
    column_map = {
        "schema_version": "sb.kanboard_column_map.v0_1",
        "project": report["project"],
        "column_map": report["column_map"],
        "ready_for_sync": report["ready_for_sync"],
        "unresolved_statuses": report["unresolved_statuses"],
    }
    write_json(args.column_map_out, column_map)
    return report


def _run_once(args: argparse.Namespace) -> dict:
    now_iso = args.now or _now_iso()
    bootstrap_report = _bootstrap_control_columns(args)
    runsheet = build_ao_control_runsheet(
        args.status_root,
        now_iso=now_iso,
        stale_seconds=args.stale_seconds,
        include_prefix=args.include_prefix,
    )
    runsheet_path = _write_json(args.runsheet_out, runsheet)

    loaded = load_local_rows(runsheet_path)
    env_config = load_kanboard_env(args.env_file)
    project_id = args.project_id if args.project_id is not None else env_config.get("project_id")
    if project_id in (None, ""):
        project_id = bootstrap_report.get("project", {}).get("project_id")
    if project_id in (None, ""):
        raise ValueError("project id required via --project-id or Kanboard env file")

    client = KanboardJsonRpcClient.from_env(env_config, timeout_seconds=args.timeout_seconds)
    existing = fetch_existing_by_reference(loaded["rows"], project_id=int(project_id), rpc_call=client.call)
    with Path(args.column_map_out).expanduser().resolve().open("r", encoding="utf-8") as handle:
        column_map = json.load(handle)

    plan = build_dry_run_plan(
        loaded["rows"],
        project_id=int(project_id),
        now_iso=now_iso,
        existing_by_reference=existing,
        column_by_status=column_map,
    )
    plan["input_source"] = {"path": runsheet_path}

    apply_report = None
    if args.apply:
        apply_report = apply_sync_plan(plan, client.call)
        plan["mode"] = "apply"
        plan["authority_boundary"] = {
            "mutates_kanboard": True,
            "kanboard_is_not_source_of_truth": True,
        }

    report = build_sync_report(
        plan=plan,
        input_source_path=runsheet_path,
        report_path=str(Path(args.report_out).expanduser().resolve()),
        now_iso=now_iso,
        errors=apply_report["errors"] if apply_report else None,
        apply_report=apply_report,
    )
    _write_json(args.report_out, report)
    result = {
        "schema_version": "sb.ao_kanboard_control_sync_result.v0_1",
        "generated_at": now_iso,
        "mode": plan["mode"],
        "authority_boundary": runsheet["authority_boundary"],
        "runsheet": {"path": runsheet_path, "summary": runsheet["summary"]},
        "bootstrap_report": {"path": str(Path(args.bootstrap_report_out).expanduser().resolve())},
        "sync_report": report,
        "apply_report": apply_report,
    }
    _write_json(args.output, result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project durable AO status/heartbeat artifacts onto the local Kanboard control board."
    )
    parser.add_argument("--status-root", default=str(ROOT.parent), help="Directory containing AO status/heartbeat JSON")
    parser.add_argument("--env-file", default=DEFAULT_KANBOARD_ENV_PATH, help="Private local Kanboard env file")
    parser.add_argument("--endpoint", help="Override Kanboard JSON-RPC endpoint")
    parser.add_argument("--project-id", type=int, help="Override Kanboard project id")
    parser.add_argument("--project-name", help="Resolve/create project by name")
    parser.add_argument("--api-user", help="JSON-RPC user")
    parser.add_argument("--api-token", help="JSON-RPC token")
    parser.add_argument("--api-auth-header", help="Optional API auth header name")
    parser.add_argument("--apply", action="store_true", help="Mutate Kanboard; default is dry-run artifacts only")
    parser.add_argument("--now", help="Override timestamp")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--stale-seconds", type=int, default=1800)
    parser.add_argument("--include-prefix", default="", help="Only include orchestrator ids with this prefix")
    parser.add_argument("--interval-seconds", type=float, default=0.0, help="Repeat sync every N seconds when > 0")
    parser.add_argument("--iterations", type=int, default=1, help="Maximum loop iterations; 0 means unlimited with --interval-seconds")
    parser.add_argument("--runsheet-out", default=str(DEFAULT_OUTPUT_DIR / "ao_control_surface.json"))
    parser.add_argument("--column-map-out", default=str(DEFAULT_OUTPUT_DIR / "ao_control_column_map.json"))
    parser.add_argument("--bootstrap-report-out", default=str(DEFAULT_OUTPUT_DIR / "ao_control_bootstrap_report.json"))
    parser.add_argument("--report-out", default=str(DEFAULT_OUTPUT_DIR / "ao_control_sync_report.json"))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR / "ao_control_sync_result.json"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    iteration = 0
    while True:
        iteration += 1
        result = _run_once(args)
        print(
            json.dumps(
                {
                    "iteration": iteration,
                    "mode": result["mode"],
                    "summary": result["sync_report"]["summary"],
                    "progress": result["sync_report"]["progress"],
                    "runsheet": result["runsheet"],
                },
                sort_keys=True,
            )
        )
        if args.interval_seconds <= 0:
            break
        if args.iterations > 0 and iteration >= args.iterations:
            break
        time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
