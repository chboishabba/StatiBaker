import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List

ALLOWED_EVENT_FIELDS = {
    "signal",
    "event",
    "event_type",
    "platform",
    "browser",
    "engine",
    "status",
}


def _hash_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _safe_summary(record: Dict[str, object]) -> str:
    parts = []
    for key in ("signal", "event", "event_type", "platform", "browser"):
        value = record.get(key)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts) if parts else "observed_signal"


def iter_observed_events(log_root: Path) -> Iterable[Dict[str, object]]:
    if not log_root.exists():
        return []

    for jsonl in log_root.rglob("*.jsonl"):
        if jsonl.name.endswith(".jsonl"):
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = record.get("ts")
                if not ts:
                    continue
                safe_record = {k: record.get(k) for k in ALLOWED_EVENT_FIELDS if k in record}
                summary = _safe_summary(record)
                event_id = _hash_id(f"{jsonl}:{ts}:{summary}")
                yield {
                    "id": f"signal-{event_id}",
                    "ts": ts,
                    "source": "observed",
                    "type": "signal",
                    "text": summary,
                    "meta": safe_record,
                }


def load_observed_events(log_root: str | Path) -> List[Dict[str, object]]:
    return list(iter_observed_events(Path(log_root)))
