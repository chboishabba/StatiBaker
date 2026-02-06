import hashlib
from datetime import datetime, timezone
from typing import Any, Dict


def sha256_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def coerce_ts(record: Dict[str, Any]) -> str:
    ts = record.get("ts") or record.get("timestamp") or record.get("time")
    if not ts:
        raise ValueError("missing ts")
    return ts


def collected_at(record: Dict[str, Any]) -> str:
    ts = record.get("collected_at") or record.get("ts") or record.get("timestamp")
    if not ts:
        raise ValueError("missing collected_at")
    return ts


def normalize_provenance(source: str, record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": source,
        "collected_at": collected_at(record),
    }
