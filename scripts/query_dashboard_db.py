#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date as Date, timedelta
from pathlib import Path


def _is_date_text(value: str) -> bool:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        return False
    try:
        Date(int(value[0:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        return False
    return True


def _date_range_inclusive(start: str, end: str) -> list[str]:
    if start > end:
        start, end = end, start
    sy, sm, sd = (int(x) for x in start.split("-"))
    ey, em, ed = (int(x) for x in end.split("-"))
    cur = Date(sy, sm, sd)
    end_date = Date(ey, em, ed)
    out: list[str] = []
    while cur <= end_date:
        out.append(cur.isoformat())
        cur = cur + timedelta(days=1)
    return out


def _try_read_json_payload(file_path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _load_daily_json_rows(*, runs_root: Path, start: str, end: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for d in _date_range_inclusive(start, end):
        full_path = runs_root / d / "outputs" / "dashboard_all.json"
        scoped_path = runs_root / d / "outputs" / "dashboard.json"
        full = _try_read_json_payload(full_path)
        if full is not None:
            rows.append({"date": d, "scope": "all", "payload": full, "source": str(full_path)})
            continue
        scoped = _try_read_json_payload(scoped_path)
        if scoped is not None:
            rows.append({"date": d, "scope": "scoped", "payload": scoped, "source": str(scoped_path)})
    return rows


def _list_date_dirs(runs_root: Path) -> list[str]:
    try:
        return sorted(
            entry.name
            for entry in runs_root.iterdir()
            if entry.is_dir() and _is_date_text(entry.name)
        )
    except Exception:
        return []


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
    p.add_argument(
        "--projection",
        choices=["raw", "timeline_ribbon"],
        default="raw",
        help="Optional projection. timeline_ribbon returns merged timeline payload + source metadata.",
    )
    p.add_argument(
        "--runs-root",
        help="Optional runs root for timeline_ribbon fallback to dashboard_all.json/dashboard.json when DB rows are missing.",
    )
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sb_root = repo_root / "StatiBaker"
    if str(sb_root) not in sys.path:
        sys.path.insert(0, str(sb_root))

    from sb.dashboard_store_sqlite import (  # noqa: PLC0415
        DashboardKey,
        build_timeline_ribbon_payload,
        list_dates_with_dashboards,
        load_timeline_ribbon_rows_for_range,
        load_best_daily_payload_for_date,
        load_dashboard_payload,
    )

    db_path = Path(args.db_path).expanduser().resolve()
    runs_root = Path(args.runs_root).expanduser().resolve() if args.runs_root else None

    if args.list_dates:
        dates = list_dates_with_dashboards(db_path=db_path, view=args.view) if db_path.exists() else []
        if not dates and runs_root is not None and args.view == "daily":
            dates = _list_date_dirs(runs_root)
        sys.stdout.write(json.dumps(dates, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return

    if args.projection == "timeline_ribbon":
        start = args.start or args.date
        end = args.end or start
        if not start or not end:
            raise SystemExit("timeline_ribbon projection requires --date or --start/--end.")

        rows: list[dict[str, object]] = []
        if db_path.exists():
            rows = load_timeline_ribbon_rows_for_range(
                db_path=db_path,
                start=start,
                end=end,
                prefer_all=bool(args.prefer_all),
                scope=args.scope,
            )
            for row in rows:
                row["source"] = f"{db_path}#daily:{row['date']}:{row['scope']}"

        if not rows and runs_root is not None:
            rows = _load_daily_json_rows(runs_root=runs_root, start=start, end=end)

        if not rows:
            sys.stdout.write("null\n")
            return

        payloads = [row["payload"] for row in rows if isinstance(row.get("payload"), dict)]
        payload: dict[str, object]
        if len(payloads) == 1 and start == end:
            payload = payloads[0]
        else:
            payload = build_timeline_ribbon_payload(
                dailies=[p for p in payloads if isinstance(p, dict)],
                start=start,
                end=end,
            )

        source = (
            str(rows[0].get("source") or "")
            if len(rows) == 1 and start == end
            else f"{len(rows)} payloads merged from {start} to {end}"
        )

        sys.stdout.write(
            json.dumps(
                {
                    "start": start,
                    "end": end,
                    "rows_loaded": len(rows),
                    "dates_loaded": [str(row.get("date") or "") for row in rows],
                    "source": source,
                    "payload": payload,
                },
                indent=2,
                sort_keys=True,
            )
        )
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
