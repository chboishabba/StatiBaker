import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or "command failed"
        raise RuntimeError(msg)
    return result.stdout


def _date_range(date_str):
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    start = day.strftime("%Y-%m-%d 00:00:00")
    end = (day + timedelta(days=1) - timedelta(seconds=1)).strftime("%Y-%m-%d 23:59:59")
    return start, end


def _load_event_map(path):
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("event map must be a JSON object")
    return data


def _event_from_entry(entry, event_map, allow_unmapped):
    message_id = entry.get("MESSAGE_ID")
    unit = entry.get("_SYSTEMD_UNIT")
    syslog_id = entry.get("SYSLOG_IDENTIFIER")
    key = None
    if message_id and message_id in event_map:
        key = f"message_id:{message_id}"
        event = event_map[message_id]
    elif unit and unit in event_map:
        key = f"unit:{unit}"
        event = event_map[unit]
    elif syslog_id and syslog_id in event_map:
        key = f"syslog:{syslog_id}"
        event = event_map[syslog_id]
    elif allow_unmapped:
        if message_id:
            key = f"message_id:{message_id}"
            event = "journald_message_id"
        elif unit:
            key = f"unit:{unit}"
            event = "journald_unit"
        elif syslog_id:
            key = f"syslog:{syslog_id}"
            event = "journald_syslog"
        else:
            return None
    else:
        return None

    record = {
        "ts": entry.get("__REALTIME_TIMESTAMP_ISO", entry.get("__REALTIME_TIMESTAMP")),
        "signal": "system",
        "event": event,
    }
    if key:
        record["event_key"] = key
    if unit:
        record["unit"] = unit
    if syslog_id:
        record["source"] = syslog_id
    priority = entry.get("PRIORITY")
    if priority is not None:
        record["priority"] = priority
    return record


def _iter_journal(since, until):
    cmd = ["journalctl", "--no-pager", "-o", "json"]
    if since:
        cmd += ["--since", since]
    if until:
        cmd += ["--until", until]
    output = _run(cmd)
    for line in output.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if "__REALTIME_TIMESTAMP" in entry and "__REALTIME_TIMESTAMP_ISO" not in entry:
            ts = datetime.utcfromtimestamp(int(entry["__REALTIME_TIMESTAMP"]) / 1_000_000)
            entry["__REALTIME_TIMESTAMP_ISO"] = ts.isoformat() + "Z"
        yield entry


def main():
    parser = argparse.ArgumentParser(description="Extract structured system events from journald.")
    parser.add_argument("--date", help="YYYY-MM-DD (local time)")
    parser.add_argument("--since", help="Since timestamp (journalctl format)")
    parser.add_argument("--until", help="Until timestamp (journalctl format)")
    parser.add_argument("--event-map", help="JSON map of MESSAGE_ID/UNIT/SYSLOG to event names")
    parser.add_argument("--allow-unmapped", action="store_true", help="Emit generic events when unmapped")
    parser.add_argument("--output", help="Write JSONL to file (default stdout)")
    args = parser.parse_args()

    if args.date and (args.since or args.until):
        print("error: use --date or --since/--until, not both", file=sys.stderr)
        sys.exit(2)
    if not args.date and not (args.since or args.until):
        print("error: provide --date or --since/--until", file=sys.stderr)
        sys.exit(2)

    since = args.since
    until = args.until
    if args.date:
        since, until = _date_range(args.date)

    try:
        event_map_path = args.event_map
        if not event_map_path:
            default_map = os.path.join(os.path.dirname(__file__), "..", "configs", "journald_event_map.json")
            if os.path.exists(default_map):
                event_map_path = default_map
        event_map = _load_event_map(event_map_path)
        records = []
        for entry in _iter_journal(since, until):
            record = _event_from_entry(entry, event_map, args.allow_unmapped)
            if record:
                records.append(record)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
        else:
            for record in records:
                sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
