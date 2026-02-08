import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from typing import Iterable

from adapters.common import sha256_text

DATE_FROM_SELECTOR_RE = re.compile(r"@\{(.+)\}$")
CHECKOUT_RE = re.compile(r"^checkout: moving from (.+) to (.+)$")


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or "command failed"
        raise RuntimeError(msg)
    return result.stdout


def _repo_name(repo_path: str) -> str:
    try:
        top = _run(["git", "-C", repo_path, "rev-parse", "--show-toplevel"]).strip()
    except RuntimeError:
        return os.path.basename(os.path.abspath(repo_path))
    return os.path.basename(top)


def _date_range(date_str: str) -> tuple[datetime, datetime]:
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    start = day.replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


def _parse_selector_ts(selector: str) -> datetime | None:
    match = DATE_FROM_SELECTOR_RE.search(selector)
    if not match:
        return None
    text = match.group(1).strip()
    # git returns ISO8601-compatible values under --date=iso-strict.
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _event_type(message: str) -> tuple[str, dict[str, str]]:
    lowered = message.lower()
    details: dict[str, str] = {}
    checkout = CHECKOUT_RE.match(message)
    if checkout:
        details["from_ref"] = checkout.group(1)
        details["to_ref"] = checkout.group(2)
        return "branch_checkout", details
    if lowered.startswith("branch: created"):
        return "branch_created", details
    if lowered.startswith("branch: renamed"):
        return "branch_renamed", details
    if lowered.startswith("merge "):
        return "branch_merge", details
    if lowered.startswith("update by push"):
        return "branch_tip_update", details
    if lowered.startswith("commit"):
        return "branch_commit", details
    return "branch_event", details


def _iter_reflog(repo_path: str) -> Iterable[tuple[str, str, str]]:
    try:
        _run(["git", "-C", repo_path, "rev-parse", "--verify", "HEAD"])
    except RuntimeError:
        return []
    output = _run(
        [
            "git",
            "-C",
            repo_path,
            "log",
            "-g",
            "--all",
            "--date=iso-strict",
            "--pretty=format:%gD%x1f%gs%x1f%H",
        ]
    )
    rows: list[tuple[str, str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        rows.append((parts[0], parts[1], parts[2]))
    return rows


def iter_git_branch_events(
    repo_path: str,
    start: datetime,
    end: datetime,
) -> Iterable[dict[str, object]]:
    repo = _repo_name(repo_path)
    for selector, message, commit_hash in _iter_reflog(repo_path):
        dt = _parse_selector_ts(selector)
        if dt is None or not (start <= dt < end):
            continue
        evt_type, details = _event_type(message)
        ref_name = selector.split("@{", 1)[0]
        payload = {
            "ts": dt.isoformat().replace("+00:00", "Z"),
            "signal": "git_branch",
            "event_type": evt_type,
            "repo": repo,
            "ref": ref_name,
            "commit_hash": commit_hash,
            "event_hash": sha256_text(f"{selector}|{message}|{commit_hash}"),
            "provenance": {
                "source": "git_reflog",
                "collected_at": dt.isoformat().replace("+00:00", "Z"),
            },
        }
        payload.update(details)
        yield payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit git branch history events for SB dashboarding.")
    parser.add_argument("--repo", default=".", help="Path to git repository")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output", help="Write JSONL to file (default stdout)")
    args = parser.parse_args()

    try:
        start, end = _date_range(args.date)
        events = iter_git_branch_events(args.repo, start, end)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                for entry in events:
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
        else:
            for entry in events:
                sys.stdout.write(json.dumps(entry, sort_keys=True) + "\n")
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
