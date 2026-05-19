#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb import query


def main():
    parser = argparse.ArgumentParser(description="Read-only SB query surface (CLI).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    parser.add_argument("--base", help="Optional base directory for safe reads")

    activity = sub.add_parser("activity-events", help="List activity events")
    activity.add_argument("--ledger", required=True)

    carryover = sub.add_parser("carryover", help="Carryover summary")
    carryover.add_argument("--state", required=True)

    prov = sub.add_parser("provenance", help="Provenance summary")
    prov.add_argument("--state", required=True)
    prov.add_argument("--ledger")
    prov.add_argument("--drift")

    commitments = sub.add_parser("commitments", help="Commitment feed from dashboard payload")
    commitments.add_argument("--dashboard", required=True)

    candidates = sub.add_parser("completion-candidates", help="Completion candidates from dashboard payload")
    candidates.add_argument("--dashboard", required=True)

    runsheet = sub.add_parser("runsheet-progress", help="Runsheet progress from dashboard payload")
    runsheet.add_argument("--dashboard", required=True)

    kanboard_sync = sub.add_parser(
        "kanboard-sync-report",
        help="Read the latest Kanboard sync report artifact (or a specific report path)",
    )
    kanboard_sync.add_argument("--report", help="Specific Kanboard sync report JSON path")
    kanboard_sync.add_argument("--runs-root", help="Runs root to scan for latest report (default: StatiBaker/runs)")

    kanboard_manager_wave = sub.add_parser(
        "kanboard-manager-wave",
        help="Summarize Kanboard manager status/heartbeat reconciliation candidates",
    )
    kanboard_manager_wave.add_argument(
        "--status-root",
        help="Directory containing status/heartbeat manager JSON files (default: repo root)",
    )
    kanboard_manager_wave.add_argument(
        "--stabilization-status",
        default="status.statibaker-kanboard-stabilization-manager.json",
        help="Stabilization status filename used as the closeout anchor",
    )

    corkysoft_reviews = sub.add_parser("corkysoft-reviews", help="Corkysoft reviewed-event feed from dashboard payload")
    corkysoft_reviews.add_argument("--dashboard", required=True)

    codex_dashboard = sub.add_parser("codex-trace-dashboard", help="Codex trace facts from dashboard payload")
    codex_dashboard.add_argument("--dashboard", required=True)

    codex_archive = sub.add_parser("codex-trace-archive", help="Codex trace facts from chat archive SQLite")
    codex_archive.add_argument("--db", required=True)
    codex_archive.add_argument("--thread-id")
    codex_archive.add_argument("--limit", type=int)

    codex_logs = sub.add_parser("codex-trace-logs", help="Codex trace facts from raw Codex log files")
    codex_logs.add_argument("--history", required=True)
    codex_logs.add_argument("--log", required=True)
    codex_logs.add_argument("--thread-id")

    todo_graph = sub.add_parser("todo-graph", help="Repo TODO causal graph summary")
    todo_graph.add_argument("--repo-root", required=True)
    todo_graph.add_argument("--todo", action="append")

    todo_obligations = sub.add_parser("todo-obligations", help="Repo TODO obligations")
    todo_obligations.add_argument("--repo-root", required=True)
    todo_obligations.add_argument("--todo", action="append")

    todo_obligation = sub.add_parser("todo-obligation", help="Inspect one repo TODO obligation")
    todo_obligation.add_argument("--repo-root", required=True)
    todo_obligation.add_argument("--obligation-id", required=True)
    todo_obligation.add_argument("--todo", action="append")

    todo_candidates = sub.add_parser("todo-candidates", help="Repo TODO completion candidates")
    todo_candidates.add_argument("--repo-root", required=True)
    todo_candidates.add_argument("--todo", action="append")

    todo_alignment = sub.add_parser("todo-alignment", help="Repo TODO alignment summary")
    todo_alignment.add_argument("--repo-root", required=True)
    todo_alignment.add_argument("--todo", action="append")

    runsheet = sub.add_parser("runsheet", help="Project canonical local runsheet rows/progress from runner state")
    runsheet.add_argument("--state", required=True)

    args = parser.parse_args()

    if args.cmd == "activity-events":
        payload = query.list_activity_events(args.ledger, base_dir=args.base)
    elif args.cmd == "carryover":
        payload = query.carryover_summary(args.state, base_dir=args.base)
    elif args.cmd == "commitments":
        payload = query.commitment_feed(args.dashboard, base_dir=args.base)
    elif args.cmd == "completion-candidates":
        payload = query.completion_candidates(args.dashboard, base_dir=args.base)
    elif args.cmd == "runsheet-progress":
        payload = query.runsheet_progress(args.dashboard, base_dir=args.base)
    elif args.cmd == "kanboard-sync-report":
        if args.report:
            payload = query.kanboard_sync_report(args.report, base_dir=args.base)
        else:
            default_runs_root = ROOT / "runs"
            payload = query.latest_kanboard_sync_report(
                args.runs_root or str(default_runs_root),
                base_dir=args.base,
            )
    elif args.cmd == "kanboard-manager-wave":
        payload = query.kanboard_manager_wave_status(
            args.status_root or str(ROOT.parent),
            stabilization_status_name=args.stabilization_status,
            base_dir=args.base,
        )
    elif args.cmd == "corkysoft-reviews":
        payload = query.corkysoft_review_feed(args.dashboard, base_dir=args.base)
    elif args.cmd == "codex-trace-dashboard":
        payload = query.codex_trace_dashboard(args.dashboard, base_dir=args.base)
    elif args.cmd == "codex-trace-archive":
        payload = query.codex_trace_archive(
            args.db,
            canonical_thread_id=args.thread_id,
            limit=args.limit,
            base_dir=args.base,
        )
    elif args.cmd == "codex-trace-logs":
        payload = query.codex_trace_logs(
            args.history,
            args.log,
            canonical_thread_id=args.thread_id,
            base_dir=args.base,
        )
    elif args.cmd == "todo-graph":
        payload = query.todo_graph(args.repo_root, todo_paths=args.todo, base_dir=args.base)
    elif args.cmd == "todo-obligations":
        payload = query.todo_obligations(args.repo_root, todo_paths=args.todo, base_dir=args.base)
    elif args.cmd == "todo-obligation":
        payload = query.todo_obligation(
            args.repo_root,
            args.obligation_id,
            todo_paths=args.todo,
            base_dir=args.base,
        )
    elif args.cmd == "todo-candidates":
        payload = query.todo_candidates(args.repo_root, todo_paths=args.todo, base_dir=args.base)
    elif args.cmd == "todo-alignment":
        payload = query.todo_alignment(args.repo_root, todo_paths=args.todo, base_dir=args.base)
    elif args.cmd == "runsheet":
        payload = query.runsheet_projection(args.state, base_dir=args.base)
    else:
        payload = query.provenance(
            args.state,
            ledger_path=args.ledger,
            drift_path=args.drift,
            base_dir=args.base,
        )

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
