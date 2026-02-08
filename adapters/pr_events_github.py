import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Iterable, List

from adapters.common import sha256_text


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        msg = proc.stderr.strip() or "command failed"
        raise RuntimeError(msg)
    return proc.stdout


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _date_bounds(date_text: str) -> tuple[datetime, datetime]:
    try:
        day = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    start = day.replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


def parse_github_repo_from_url(url: str) -> str | None:
    text = url.strip()
    if not text:
        return None
    patterns = [
        r"^git@github\.com:([^/]+)/([^.]+?)(?:\.git)?$",
        r"^https://github\.com/([^/]+)/([^.]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/([^/]+)/([^.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return None


def _repo_from_git_remote(repo_path: str) -> str:
    remote = _run(["git", "-C", repo_path, "remote", "get-url", "origin"]).strip()
    parsed = parse_github_repo_from_url(remote)
    if not parsed:
        raise ValueError("unable to derive GitHub repo from git origin URL")
    return parsed


def _gh_api_json(path: str, *, jq: str | None = None) -> Any:
    cmd = ["gh", "api", path]
    if jq:
        cmd.extend(["--jq", jq])
    output = _run(cmd).strip()
    if not output:
        return []
    return json.loads(output)


def _in_range(ts: str | None, start: datetime, end: datetime) -> datetime | None:
    dt = _parse_iso(ts)
    if dt is None:
        return None
    if start <= dt < end:
        return dt
    return None


def _normalize_event(
    *,
    ts: datetime,
    event_type: str,
    repo: str,
    pr_number: int,
    actor: str | None,
    state: str | None,
    source: str,
    collected_at: datetime,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ts": ts.isoformat().replace("+00:00", "Z"),
        "signal": "pr_event",
        "event_type": event_type,
        "repo": repo,
        "pr_number": int(pr_number),
        "pr_key_hash": sha256_text(f"{repo}#{pr_number}"),
        "state": state,
        "provenance": {
            "source": source,
            "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
        },
    }
    if actor:
        payload["actor_hash"] = sha256_text(str(actor))
    return payload


def _pr_number_from_url(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"/pulls?/(\d+)$", value)
    if not match:
        return None
    return int(match.group(1))


def build_events(
    *,
    repo: str,
    start: datetime,
    end: datetime,
    pulls: Iterable[Dict[str, Any]],
    comments: Iterable[Dict[str, Any]],
    collected_at: datetime,
) -> List[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    source = "github_gh_cli"

    for pr in pulls:
        if not isinstance(pr, dict):
            continue
        number = pr.get("number")
        if not isinstance(number, int):
            continue
        actor = ((pr.get("user") or {}).get("login")) if isinstance(pr.get("user"), dict) else None
        state = str(pr.get("state") or "")

        opened = _in_range(pr.get("created_at"), start, end)
        if opened:
            events.append(
                _normalize_event(
                    ts=opened,
                    event_type="pr_received",
                    repo=repo,
                    pr_number=number,
                    actor=actor,
                    state=state,
                    source=source,
                    collected_at=collected_at,
                )
            )

        merged = _in_range(pr.get("merged_at"), start, end)
        if merged:
            events.append(
                _normalize_event(
                    ts=merged,
                    event_type="pr_merged",
                    repo=repo,
                    pr_number=number,
                    actor=actor,
                    state="closed",
                    source=source,
                    collected_at=collected_at,
                )
            )
            continue

        closed = _in_range(pr.get("closed_at"), start, end)
        if closed:
            events.append(
                _normalize_event(
                    ts=closed,
                    event_type="pr_closed",
                    repo=repo,
                    pr_number=number,
                    actor=actor,
                    state="closed",
                    source=source,
                    collected_at=collected_at,
                )
            )

    for comment in comments:
        if not isinstance(comment, dict):
            continue
        number = _pr_number_from_url(comment.get("pull_request_url"))
        if number is None:
            continue
        commented = _in_range(comment.get("created_at"), start, end)
        if not commented:
            continue
        actor = ((comment.get("user") or {}).get("login")) if isinstance(comment.get("user"), dict) else None
        events.append(
            _normalize_event(
                ts=commented,
                event_type="pr_commented",
                repo=repo,
                pr_number=number,
                actor=actor,
                state="open",
                source=source,
                collected_at=collected_at,
            )
        )

    deduped: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for event in events:
        key = (
            str(event["ts"]),
            str(event["event_type"]),
            int(event["pr_number"]),
            str(event.get("actor_hash") or ""),
        )
        deduped[key] = event
    ordered = sorted(
        deduped.values(),
        key=lambda row: (row["ts"], row["event_type"], row["pr_number"]),
    )
    return ordered


def fetch_and_build_events(
    *,
    repo: str,
    date_text: str,
    max_prs: int,
    max_comments: int,
) -> List[dict[str, Any]]:
    start, end = _date_bounds(date_text)
    collected_at = datetime.now(UTC)

    pulls = _gh_api_json(
        (
            f"repos/{repo}/pulls"
            f"?state=all&sort=updated&direction=desc&per_page={max(1, max_prs)}"
        )
    )
    comments = _gh_api_json(
        f"repos/{repo}/issues/comments?since={start.isoformat().replace('+00:00','Z')}&per_page={max(1, max_comments)}"
    )
    if not isinstance(pulls, list):
        pulls = []
    if not isinstance(comments, list):
        comments = []
    return build_events(
        repo=repo,
        start=start,
        end=end,
        pulls=pulls,
        comments=comments,
        collected_at=collected_at,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub PR lifecycle events directly via gh CLI for SB."
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--repo", help="GitHub repo owner/name")
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Local git repo path used to derive --repo when omitted.",
    )
    parser.add_argument("--output", required=True, help="Write JSONL output")
    parser.add_argument("--max-prs", type=int, default=100, help="Max PRs to query (default 100)")
    parser.add_argument(
        "--max-comments",
        type=int,
        default=100,
        help="Max issue comments to query (default 100)",
    )
    args = parser.parse_args()

    try:
        if shutil.which("gh") is None:
            raise RuntimeError("gh CLI not found in PATH")

        repo = args.repo or _repo_from_git_remote(args.repo_path)
        events = fetch_and_build_events(
            repo=repo,
            date_text=args.date,
            max_prs=max(1, args.max_prs),
            max_comments=max(1, args.max_comments),
        )
        with open(args.output, "w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

