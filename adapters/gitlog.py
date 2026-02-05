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


def _repo_name(repo_path):
    try:
        top = _run(["git", "-C", repo_path, "rev-parse", "--show-toplevel"]).strip()
    except RuntimeError:
        return os.path.basename(os.path.abspath(repo_path))
    return os.path.basename(top)


def _date_range(date_str):
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    start = day.strftime("%Y-%m-%dT00:00:00")
    end = (day + timedelta(days=1) - timedelta(seconds=1)).strftime("%Y-%m-%dT23:59:59")
    return start, end


def _iter_git_log(repo_path, since, until, use_committer, include_summary):
    repo_name = _repo_name(repo_path)
    time_field = "%cI" if use_committer else "%aI"
    fields = ["%H", time_field]
    if include_summary:
        fields.append("%s")
    fmt = "%x1f".join(fields)
    cmd = [
        "git",
        "-C",
        repo_path,
        "log",
        "--reverse",
        "--date=iso-strict",
        f"--pretty=format:{fmt}",
    ]
    if since:
        cmd += ["--since", since]
    if until:
        cmd += ["--until", until]
    output = _run(cmd)
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if include_summary:
            commit_hash, ts, summary = parts
        else:
            commit_hash, ts = parts
            summary = ""
        yield {
            "ts": ts,
            "type": "commit",
            "repo": repo_name,
            "hash": commit_hash,
            "summary": summary,
        }


def main():
    parser = argparse.ArgumentParser(description="Emit SB git activity JSONL.")
    parser.add_argument("--repo", default=".", help="Path to git repository")
    parser.add_argument("--date", help="YYYY-MM-DD (local time)")
    parser.add_argument("--since", help="Since timestamp (git-recognized format)")
    parser.add_argument("--until", help="Until timestamp (git-recognized format)")
    parser.add_argument("--use-committer-time", action="store_true", help="Use committer time")
    parser.add_argument(
        "--include-summary",
        action="store_true",
        help="Include commit subject in summary field",
    )
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
        entries = _iter_git_log(
            args.repo,
            since,
            until,
            use_committer=args.use_committer_time,
            include_summary=args.include_summary,
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                for entry in entries:
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
        else:
            for entry in entries:
                sys.stdout.write(json.dumps(entry, sort_keys=True) + "\n")
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
