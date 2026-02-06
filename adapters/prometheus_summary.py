import argparse
import json
import sys
from datetime import datetime, timedelta
from statistics import mean
from urllib.parse import urlencode, urljoin
from urllib.request import urlopen


DEFAULT_QUERIES = {
    "cpu_usage": '1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))',
    "mem_available_ratio": "node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes",
}


def _date_range(date_str):
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    start = day.strftime("%Y-%m-%dT00:00:00Z")
    end = (day + timedelta(days=1) - timedelta(seconds=1)).strftime("%Y-%m-%dT23:59:59Z")
    return start, end


def _fetch_range(base_url, query, start, end, step):
    params = urlencode({"query": query, "start": start, "end": end, "step": step})
    url = urljoin(base_url, "/api/v1/query_range") + "?" + params
    with urlopen(url) as handle:
        payload = json.load(handle)
    if payload.get("status") != "success":
        raise RuntimeError("prometheus query failed")
    return payload["data"]["result"]


def _flatten_values(series):
    values = []
    for item in series:
        for _, value in item.get("values", []):
            try:
                values.append(float(value))
            except ValueError:
                continue
    return values


def _percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    k = int((len(ordered) - 1) * pct)
    return ordered[k]


def _summarize(values):
    if not values:
        return {"mean": 0.0, "p95": 0.0, "samples": 0}
    return {"mean": mean(values), "p95": _percentile(values, 0.95), "samples": len(values)}


def _build_record(name, start, end, values):
    summary = _summarize(values)
    return {
        "t_start": start,
        "t_end": end,
        "signal": "metric_summary",
        "metric": name,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize Prometheus metrics into SB JSONL.")
    parser.add_argument("--base-url", required=True, help="Prometheus base URL")
    parser.add_argument("--date", help="YYYY-MM-DD (UTC)")
    parser.add_argument("--start", help="Range start (RFC3339)")
    parser.add_argument("--end", help="Range end (RFC3339)")
    parser.add_argument("--step", default="60s", help="Query range step (default 60s)")
    parser.add_argument("--output", help="Write JSONL to file (default stdout)")
    parser.add_argument("--queries", help="Path to JSON query map (name -> promql)")
    parser.add_argument(
        "--query",
        action="append",
        help="Custom query in form name=promql (can repeat)",
    )
    args = parser.parse_args()

    if args.date and (args.start or args.end):
        print("error: use --date or --start/--end, not both", file=sys.stderr)
        sys.exit(2)
    if not args.date and not (args.start and args.end):
        print("error: provide --date or --start/--end", file=sys.stderr)
        sys.exit(2)

    start = args.start
    end = args.end
    if args.date:
        start, end = _date_range(args.date)

    queries = DEFAULT_QUERIES.copy()
    if args.queries:
        with open(args.queries, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("queries file must be a JSON object")
        queries = {str(name): str(promql) for name, promql in data.items()}
    if args.query:
        for entry in args.query:
            if "=" not in entry:
                print("error: --query must be name=promql", file=sys.stderr)
                sys.exit(2)
            name, promql = entry.split("=", 1)
            queries[name.strip()] = promql.strip()

    try:
        records = []
        for name, promql in queries.items():
            series = _fetch_range(args.base_url, promql, start, end, args.step)
            values = _flatten_values(series)
            records.append(_build_record(name, start, end, values))

        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
        else:
            for record in records:
                sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
