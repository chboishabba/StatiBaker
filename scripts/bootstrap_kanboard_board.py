#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb.kanboard_bootstrap import (  # noqa: E402
    KanboardBootstrapError,
    KanboardRpcClient,
    parse_env_file,
    resolve_runtime_config,
    write_json,
    bootstrap_board,
)


DEFAULT_ENV_FILE = Path("/home/c/.local/state/kanboard-local/statibaker-kanboard.env")
DEFAULT_OUTPUT_DIR = ROOT / "runs_local" / "kanboard"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap a Kanboard board structure for StatiBaker sync and emit "
            "a deterministic status->column map artifact."
        )
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Path to local Kanboard env file")
    parser.add_argument("--endpoint", help="Override JSON-RPC endpoint (for example http://127.0.0.1/kanboard/jsonrpc.php)")
    parser.add_argument("--project-id", type=int, help="Target Kanboard project id")
    parser.add_argument("--project-name", help="Project name to resolve or create when missing")
    parser.add_argument("--api-user", help="JSON-RPC user")
    parser.add_argument("--api-token", help="JSON-RPC token")
    parser.add_argument("--api-auth-header", help="Optional API auth header name (for example X-API-Auth)")
    parser.add_argument("--apply", action="store_true", help="Apply Kanboard mutations (create project/columns) when missing")
    parser.add_argument(
        "--column-map-output",
        default=str(DEFAULT_OUTPUT_DIR / "column_map.json"),
        help="Path to write status->column mapping JSON",
    )
    parser.add_argument(
        "--report-output",
        default=str(DEFAULT_OUTPUT_DIR / "bootstrap_report.json"),
        help="Path to write full bootstrap report JSON",
    )
    parser.add_argument("--timeout-seconds", type=float, default=5.0, help="JSON-RPC timeout seconds")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON on stdout")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    env = parse_env_file(args.env_file)

    overrides = {
        "KANBOARD_JSONRPC_ENDPOINT": args.endpoint,
        "KANBOARD_PROJECT_ID": args.project_id,
        "KANBOARD_PROJECT_NAME": args.project_name,
        "KANBOARD_API_USER": args.api_user,
        "KANBOARD_API_TOKEN": args.api_token,
        "KANBOARD_API_AUTH_HEADER": args.api_auth_header,
    }
    config = resolve_runtime_config(env, overrides)

    if not config.endpoint:
        raise KanboardBootstrapError("Missing Kanboard endpoint. Set KANBOARD_JSONRPC_ENDPOINT or --endpoint.")
    if not config.api_token:
        raise KanboardBootstrapError("Missing Kanboard API token. Set KANBOARD_API_TOKEN in local env or --api-token.")

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
    )
    report["input"] = {
        "env_file": str(Path(args.env_file).expanduser()),
        "endpoint": config.endpoint,
        "project_id": config.project_id,
        "project_name": config.project_name,
    }

    map_artifact = {
        "schema_version": "sb.kanboard_column_map.v0_1",
        "project": report["project"],
        "column_map": report["column_map"],
        "ready_for_sync": report["ready_for_sync"],
        "unresolved_statuses": report["unresolved_statuses"],
    }

    column_map_path = write_json(args.column_map_output, map_artifact)
    report_path = write_json(args.report_output, report)
    report["artifacts"] = {
        "column_map_path": column_map_path,
        "report_path": report_path,
    }

    rendered = json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KanboardBootstrapError as exc:
        print(json.dumps({"error": str(exc), "schema_version": "sb.kanboard_bootstrap.error.v0_1"}), file=sys.stderr)
        raise SystemExit(2)
