#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="Query StatiBaker dashboard payloads from the canonical SQLite store.")
    p.add_argument("--db-path", required=True, help="Path to dashboard.sqlite (canonical store).")
    p.add_argument("--view", default="daily", choices=["daily", "weekly", "lifetime", "costing"], help="Dashboard view.")
    p.add_argument("--scope", default=None, choices=["scoped", "all"], help="Dashboard scope (default: view-dependent).")
    p.add_argument("--window-days", type=int, default=0, help="Weekly window length (N). Use 0 for non-weekly.")
    p.add_argument("--date", help="Date in YYYY-MM-DD (end date for weekly/lifetime).")
    p.add_argument("--start", help="Range start date YYYY-MM-DD (inclusive).")
    p.add_argument("--end", help="Range end date YYYY-MM-DD (inclusive).")
    p.add_argument("--prefer-all", action="store_true", help="For daily range queries, prefer scope=all when available.")
    p.add_argument("--list-dates", action="store_true", help="List available dates for this view.")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sb_root = repo_root / "StatiBaker"
    if str(sb_root) not in sys.path:
        sys.path.insert(0, str(sb_root))

    from sb.dashboard_store_sqlite import (  # noqa: PLC0415
        DashboardKey,
        list_dates_with_dashboards,
        load_best_daily_payload_for_date,
        load_dashboard_payload,
    )

    db_path = Path(args.db_path).expanduser().resolve()

    if args.list_dates:
        dates = list_dates_with_dashboards(db_path=db_path, view=args.view)
        sys.stdout.write(json.dumps(dates, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return

    if args.start and args.end:
        # Range query: return list of daily payloads (best-effort).
        # Keep this deterministic: inclusive YYYY-MM-DD stepping by 1 day in UTC.
        from datetime import date as Date, timedelta

        sy, sm, sd = (int(x) for x in args.start.split("-"))
        ey, em, ed = (int(x) for x in args.end.split("-"))
        cur = Date(sy, sm, sd)
        end = Date(ey, em, ed)
        out = []
        while cur <= end:
            d = cur.isoformat()
            if args.view != "daily":
                key = DashboardKey(
                    date=d,
                    view=args.view,
                    scope=(args.scope or "scoped"),
                    window_days=max(0, int(args.window_days or 0)),
                )
                payload = load_dashboard_payload(db_path=db_path, key=key)
                if payload is not None:
                    out.append({"date": d, "scope": key.scope, "payload": payload})
            else:
                if args.prefer_all:
                    best = load_best_daily_payload_for_date(db_path=db_path, date=d)
                    if best is not None:
                        payload, scope = best
                        out.append({"date": d, "scope": scope, "payload": payload})
                else:
                    key = DashboardKey(date=d, view="daily", scope=(args.scope or "scoped"), window_days=0)
                    payload = load_dashboard_payload(db_path=db_path, key=key)
                    if payload is not None:
                        out.append({"date": d, "scope": key.scope, "payload": payload})
            cur = cur + timedelta(days=1)

        sys.stdout.write(json.dumps(out, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return

    if not args.date:
        raise SystemExit("Must provide --date or --start/--end (or --list-dates).")

    if args.view == "daily" and args.scope is None and args.prefer_all:
        best = load_best_daily_payload_for_date(db_path=db_path, date=args.date)
        if best is None:
            sys.stdout.write("null\n")
            return
        payload, scope = best
        sys.stdout.write(json.dumps({"date": args.date, "scope": scope, "payload": payload}, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return

    key = DashboardKey(
        date=args.date,
        view=args.view,
        scope=(args.scope or "scoped"),
        window_days=max(0, int(args.window_days or 0)),
    )
    payload = load_dashboard_payload(db_path=db_path, key=key)
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) if payload is not None else "null")
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

