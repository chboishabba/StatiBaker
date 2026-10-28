"""Convert explicit TiRC trajectory lifecycle signals to replay-safe SB events.

This adapter does not infer state from transcripts. Only supplied open/closed
transitions become lifecycle events. Event IDs exclude ingestion time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from adapters.common import normalize_provenance, sha256_text

_STATES = {"open", "closed"}
_KIND_TO_STATE = {
    "trajectory_open": "open",
    "trajectory_opened": "open",
    "trajectory_closed": "closed",
    "trajectory_close": "closed",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {field}")
    return value.strip()


def normalize_record(record: Mapping[str, Any], source: str = "tircorder") -> dict[str, Any]:
    """Preserve explicit TiRC lifecycle facts without asserting inferred closures."""
    if not isinstance(record, Mapping):
        raise ValueError("event must be an object")
    source = _text(source, "source")
    ts = _text(record.get("ts") or record.get("timestamp"), "ts")
    trajectory_id = _text(record.get("trajectory_id"), "trajectory_id")
    raw_kind = _text(record.get("event_type") or record.get("signal"), "event_type").lower()
    state = _KIND_TO_STATE.get(raw_kind)
    if raw_kind == "trajectory":
        state = _text(record.get("state"), "state").lower()
    if state not in _STATES:
        raise ValueError(f"unsupported trajectory lifecycle: {raw_kind}")
    if record.get("state") is not None and _text(record["state"], "state").lower() != state:
        raise ValueError("event_type and state disagree")
    # An upstream event ID distinguishes separate, otherwise identical transitions.
    upstream_id = record.get("event_id")
    if upstream_id is not None:
        upstream_id = _text(upstream_id, "event_id")
    identity = [source, trajectory_id, state, ts, upstream_id]
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "ts": ts,
        "signal": "trajectory_event",
        "event_type": f"trajectory_{state}",
        "state": state,
        "event_id": f"sha256:{digest}",
        "trajectory_key_hash": sha256_text(f"{source}:{trajectory_id}"),
        "provenance": normalize_provenance(source, {"ts": ts}),
    }


def normalize_records(records: Iterable[Mapping[str, Any]], source: str = "tircorder"):
    for record in records:
        yield normalize_record(record, source)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert TiRC trajectory open/closed JSONL to SB events.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default="tircorder")
    args = parser.parse_args(argv)
    path = Path(args.input)
    events = [
        normalize_record(json.loads(line), args.source)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in events),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
