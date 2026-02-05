import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or "command failed"
        raise RuntimeError(msg)
    return result.stdout


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_queries(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("queries file must be a JSON array")
    queries = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("query entries must be objects")
        name = entry.get("name")
        query = entry.get("query")
        if not name or not query:
            raise ValueError("each query entry requires name and query")
        queries.append({"name": str(name), "query": str(query)})
    return queries


def _run_query(binary, query):
    output = _run([binary, "--json", query])
    data = json.loads(output)
    if not isinstance(data, list):
        raise ValueError("osquery output must be a JSON list")
    return data


def _hash_value(value):
    return f"sha256:{hashlib.sha256(str(value).encode('utf-8')).hexdigest()}"


def _maybe_hash_row(name, row, enabled):
    if not enabled:
        return row

    hash_fields = {
        "system_info": ["hostname"],
        "interface_addresses": ["address"],
        "mounts": ["path"],
        "usb_devices": ["serial"],
    }
    fields = hash_fields.get(name, [])
    if not fields:
        return row
    mutated = dict(row)
    for field in fields:
        if field in mutated and mutated[field] not in (None, ""):
            mutated[field] = _hash_value(mutated[field])
    return mutated


def main():
    parser = argparse.ArgumentParser(description="Poll osquery tables into SB JSONL.")
    parser.add_argument("--queries", required=True, help="Path to queries JSON file")
    parser.add_argument("--osquery-bin", default="osqueryi", help="Path to osqueryi binary")
    parser.add_argument("--hash-sensitive", action="store_true", help="Hash sensitive fields")
    parser.add_argument("--output", help="Write JSONL to file (default stdout)")
    parser.add_argument(
        "--query",
        action="append",
        help="Inline query in form name=SQL (can repeat)",
    )
    args = parser.parse_args()

    try:
        queries = _load_queries(args.queries)
        if args.query:
            for entry in args.query:
                if "=" not in entry:
                    raise ValueError("--query must be name=SQL")
                name, sql = entry.split("=", 1)
                queries.append({"name": name.strip(), "query": sql.strip()})

        records = []
        ts = _now_iso()
        for item in queries:
            rows = _run_query(args.osquery_bin, item["query"])
            for row in rows:
                row = _maybe_hash_row(item["name"], row, args.hash_sensitive)
                records.append(
                    {
                        "ts": ts,
                        "signal": "system_fact",
                        "source": "osquery",
                        "name": item["name"],
                        "row": row,
                    }
                )

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
