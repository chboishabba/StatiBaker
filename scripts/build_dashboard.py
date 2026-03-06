#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build SB daily dashboard with optional weekly/lifetime summary views."
    )
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD.")
    parser.add_argument(
        "--sb-root",
        help="Path to StatiBaker root (default: inferred from this script).",
    )
    parser.add_argument(
        "--repo-root",
        help="Path to ITIR-suite root (default: parent of sb root).",
    )
    parser.add_argument(
        "--runs-root",
        help="Path to SB runs root (default: $SB_RUNS_ROOT or <sb-root>/runs_local).",
    )
    parser.add_argument(
        "--context-root",
        help="Path to context folder (default: <repo-root>/__CONTEXT).",
    )
    parser.add_argument(
        "--convo-ids",
        help="Path to __CONTEXT/convo_ids.md (default: <context-root>/convo_ids.md).",
    )
    parser.add_argument(
        "--chat-db",
        help="Path to chat sqlite archive (default: ~/.chat_archive.sqlite).",
    )
    parser.add_argument(
        "--chat-exports",
        help="Path to chat exports directory (default: <repo-root>/chat_exports).",
    )
    parser.add_argument(
        "--db-path",
        help="Path to canonical dashboard SQLite DB (default: <runs-root>/dashboard.sqlite).",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Disable writing dashboard payloads to the canonical SQLite DB.",
    )
    parser.add_argument(
        "--json-out",
        help="Legacy/regression output path for dashboard JSON (default: runs/<date>/outputs/dashboard.json).",
    )
    parser.add_argument(
        "--html-out",
        help="Legacy/regression output path for dashboard HTML (default: runs/<date>/outputs/dashboard.html).",
    )
    parser.add_argument(
        "--write-json",
        action="store_true",
        help="Write legacy dashboard JSON outputs (regression/debug only).",
    )
    parser.add_argument(
        "--write-html",
        action="store_true",
        help="Write legacy dashboard HTML outputs (regression/debug only).",
    )
    parser.add_argument(
        "--max-timeline-events",
        type=int,
        default=600,
        help="Keep only newest N timeline rows in outputs (default: 600).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug compilation mode (includes all chat threads for the date).",
    )
    parser.add_argument(
        "--debug-include-all-chat",
        action="store_true",
        help="Disable convo_ids chat scoping and scan all chat threads for the date.",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Also build a weekly summary view ending at --date.",
    )
    parser.add_argument(
        "--weekly-days",
        type=int,
        default=7,
        help="Number of days to include in weekly summary window (default: 7).",
    )
    parser.add_argument(
        "--weekly-json-out",
        help=(
            "Output path for weekly dashboard JSON "
            "(default: runs/<date>/outputs/dashboard_weekly_<N>d.json)."
        ),
    )
    parser.add_argument(
        "--weekly-html-out",
        help=(
            "Output path for weekly dashboard HTML "
            "(default: runs/<date>/outputs/dashboard_weekly_<N>d.html)."
        ),
    )
    parser.add_argument(
        "--lifetime",
        action="store_true",
        help="Also build a lifetime/global summary view up to --date.",
    )
    parser.add_argument(
        "--lifetime-start-date",
        help="Optional lifetime start date (YYYY-MM-DD). Default: earliest runs/<date> directory.",
    )
    parser.add_argument(
        "--lifetime-json-out",
        help=(
            "Output path for lifetime dashboard JSON "
            "(default: runs/<date>/outputs/dashboard_lifetime.json)."
        ),
    )
    parser.add_argument(
        "--lifetime-html-out",
        help=(
            "Output path for lifetime dashboard HTML "
            "(default: runs/<date>/outputs/dashboard_lifetime.html)."
        ),
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    sb_root = Path(args.sb_root).expanduser().resolve() if args.sb_root else script_path.parents[1]
    if str(sb_root) not in sys.path:
        sys.path.insert(0, str(sb_root))

    runs_root_default = Path(os.environ.get("SB_RUNS_ROOT", "")).expanduser().resolve() if os.environ.get("SB_RUNS_ROOT") else (sb_root / "runs_local")

    from sb.dashboard import (
        build_dashboard,
        build_lifetime_costing_payload,
        build_lifetime_dashboard,
        build_weekly_dashboard,
        write_costing_outputs,
        write_dashboard_outputs,
        write_lifetime_outputs,
        write_weekly_outputs,
    )
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    repo_root = (
        Path(args.repo_root).expanduser().resolve() if args.repo_root else sb_root.parent
    )
    runs_root = (
        Path(args.runs_root).expanduser().resolve() if args.runs_root else runs_root_default
    )
    context_root = (
        Path(args.context_root).expanduser().resolve()
        if args.context_root
        else repo_root / "__CONTEXT"
    )
    convo_ids = (
        Path(args.convo_ids).expanduser().resolve()
        if args.convo_ids
        else context_root / "convo_ids.md"
    )
    chat_db = (
        Path(args.chat_db).expanduser().resolve()
        if args.chat_db
        else Path.home() / ".chat_archive.sqlite"
    )
    chat_exports = (
        Path(args.chat_exports).expanduser().resolve()
        if args.chat_exports
        else repo_root / "chat_exports"
    )

    default_out_dir = runs_root / args.date / "outputs"
    db_path = (
        Path(args.db_path).expanduser().resolve()
        if args.db_path
        else (runs_root / "dashboard.sqlite")
    )

    write_json = bool(args.write_json or args.json_out)
    write_html = bool(args.write_html or args.html_out)
    json_out = (
        Path(args.json_out).expanduser().resolve()
        if args.json_out
        else (default_out_dir / "dashboard.json")
    )
    html_out = (
        Path(args.html_out).expanduser().resolve()
        if args.html_out
        else (default_out_dir / "dashboard.html")
    )

    payload = build_dashboard(
        date_text=args.date,
        repo_root=repo_root,
        runs_root=runs_root,
        context_root=context_root,
        convo_ids_path=convo_ids,
        chat_db_path=chat_db,
        chat_exports_dir=chat_exports,
        max_timeline_events=max(1, args.max_timeline_events),
        include_all_chat=bool(args.debug or args.debug_include_all_chat),
    )
    scope = "all" if bool(args.debug or args.debug_include_all_chat) else "scoped"
    if not args.no_db:
        upsert_dashboard_payload(
            db_path=db_path,
            key=DashboardKey(date=args.date, view="daily", scope=scope, window_days=0),
            payload=payload,
        )
        print(db_path)

    if write_json or write_html:
        # Legacy outputs (regression/debug-only). This emits both JSON and HTML to keep
        # the legacy writer interface simple and predictable.
        write_dashboard_outputs(payload, json_path=json_out, html_path=html_out)
        print(json_out)
        print(html_out)

    if args.weekly:
        weekly_json_out = (
            Path(args.weekly_json_out).expanduser().resolve()
            if args.weekly_json_out
            else default_out_dir / f"dashboard_weekly_{max(1, args.weekly_days)}d.json"
        )
        weekly_html_out = (
            Path(args.weekly_html_out).expanduser().resolve()
            if args.weekly_html_out
            else default_out_dir / f"dashboard_weekly_{max(1, args.weekly_days)}d.html"
        )
        weekly_payload = build_weekly_dashboard(
            end_date_text=args.date,
            days=max(1, args.weekly_days),
            repo_root=repo_root,
            runs_root=runs_root,
            context_root=context_root,
            convo_ids_path=convo_ids,
            chat_db_path=chat_db,
            chat_exports_dir=chat_exports,
            max_timeline_events=max(1, args.max_timeline_events),
            include_all_chat=bool(args.debug or args.debug_include_all_chat),
        )
        if not args.no_db:
            upsert_dashboard_payload(
                db_path=db_path,
                key=DashboardKey(date=args.date, view="weekly", scope=scope, window_days=max(1, args.weekly_days)),
                payload=weekly_payload,
            )
        if write_json or write_html:
            write_weekly_outputs(
                weekly_payload,
                json_path=weekly_json_out,
                html_path=weekly_html_out,
            )
            print(weekly_json_out)
            print(weekly_html_out)

    if args.lifetime:
        lifetime_json_out = (
            Path(args.lifetime_json_out).expanduser().resolve()
            if args.lifetime_json_out
            else default_out_dir / "dashboard_lifetime.json"
        )
        lifetime_html_out = (
            Path(args.lifetime_html_out).expanduser().resolve()
            if args.lifetime_html_out
            else default_out_dir / "dashboard_lifetime.html"
        )
        lifetime_payload = build_lifetime_dashboard(
            end_date_text=args.date,
            repo_root=repo_root,
            runs_root=runs_root,
            context_root=context_root,
            convo_ids_path=convo_ids,
            chat_db_path=chat_db,
            chat_exports_dir=chat_exports,
            max_timeline_events=max(1, args.max_timeline_events),
            include_all_chat=bool(args.debug or args.debug_include_all_chat),
            start_date_text=args.lifetime_start_date,
        )
        if not args.no_db:
            upsert_dashboard_payload(
                db_path=db_path,
                key=DashboardKey(date=args.date, view="lifetime", scope=scope, window_days=0),
                payload=lifetime_payload,
            )
        if write_json or write_html:
            write_lifetime_outputs(
                lifetime_payload,
                json_path=lifetime_json_out,
                html_path=lifetime_html_out,
            )
            print(lifetime_json_out)
            print(lifetime_html_out)

        suffix = "_all" if bool(args.debug or args.debug_include_all_chat) else ""
        costing_json_out = default_out_dir / f"dashboard_costing{suffix}.json"
        costing_html_out = default_out_dir / f"dashboard_costing{suffix}.html"
        costing_payload = build_lifetime_costing_payload(lifetime_payload=lifetime_payload)
        if not args.no_db:
            upsert_dashboard_payload(
                db_path=db_path,
                key=DashboardKey(date=args.date, view="costing", scope=scope, window_days=0),
                payload=costing_payload,
            )
        if write_json or write_html:
            write_costing_outputs(
                costing_payload,
                json_path=costing_json_out,
                html_path=costing_html_out,
            )
            print(costing_json_out)
            print(costing_html_out)


if __name__ == "__main__":
    main()
