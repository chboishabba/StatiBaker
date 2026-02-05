import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


def _hash_path(path):
    return hashlib.sha256(path.encode("utf-8")).hexdigest()


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_state(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("state must be a JSON object")
    return data


def _save_state(path, state):
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def _count_changes(root, since_ts):
    changes = 0
    scanned = 0
    for base, _, files in os.walk(root):
        for name in files:
            full = os.path.join(base, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            scanned += 1
            if stat.st_mtime >= since_ts:
                changes += 1
    return changes, scanned


def main():
    parser = argparse.ArgumentParser(description="Filesystem metadata change counters.")
    parser.add_argument("--dir", action="append", required=True, help="Directory to scan (repeatable)")
    parser.add_argument("--state", help="Path to adapter state JSON")
    parser.add_argument("--output", help="Write JSONL to file (default stdout)")
    args = parser.parse_args()

    try:
        state = _load_state(args.state)
        records = []
        now = datetime.now(timezone.utc).timestamp()
        ts = _now_iso()
        for root in args.dir:
            root = os.path.abspath(root)
            last_scan = float(state.get(root, 0.0))
            changes, scanned = _count_changes(root, last_scan)
            records.append(
                {
                    "ts": ts,
                    "signal": "fs_meta",
                    "dir_hash": f"sha256:{_hash_path(root)}",
                    "changes": changes,
                    "scanned_files": scanned,
                }
            )
            state[root] = now

        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
        else:
            for record in records:
                sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
        _save_state(args.state, state)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
