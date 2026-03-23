import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List

# --- Adapter for SL shared reducer ---
try:
    _SUITE_ROOT = Path(__file__).resolve().parents[2]
    _SENSIBLAW_ROOT = _SUITE_ROOT / "SensibLaw"
    _SENSIBLAW_SRC = _SENSIBLAW_ROOT / "src"
    
    if str(_SENSIBLAW_ROOT) not in sys.path:
        sys.path.insert(0, str(_SENSIBLAW_ROOT))
    if str(_SENSIBLAW_SRC) not in sys.path:
        sys.path.insert(0, str(_SENSIBLAW_SRC))
        
    from sensiblaw.interfaces.shared_reducer import (
        collect_canonical_lexeme_occurrences,
        get_canonical_tokenizer_profile,
    )
    HAS_REDUCER = True
except ImportError:
    HAS_REDUCER = False
# -------------------------------------

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
                    yield {
                        "id": f"signal-err-json-{_hash_id(line)}",
                        "ts": None,
                        "source": "observed",
                        "type": "error",
                        "text": "malformed_json",
                        "meta": {"line_snippet": line[:100]},
                    }
                    continue
                ts = record.get("ts")
                if not ts:
                    yield {
                        "id": f"signal-err-ts-{_hash_id(json.dumps(record))}",
                        "ts": None,
                        "source": "observed",
                        "type": "error",
                        "text": "missing_ts",
                        "meta": {"record_snippet": json.dumps(record)[:100]},
                    }
                    continue
                safe_record = {k: record.get(k) for k in ALLOWED_EVENT_FIELDS if k in record}
                summary = _safe_summary(record)
                event_id = _hash_id(f"{jsonl}:{ts}:{summary}")
                record_payload = {
                    "id": f"signal-{event_id}",
                    "ts": ts,
                    "source": "observed",
                    "type": "signal",
                    "text": summary,
                    "meta": safe_record,
                }
                
                if HAS_REDUCER and summary:
                    # Provide an adapter surface generating canonical refs via SL
                    record_payload["canonical_lexeme_ids"] = [
                        occ.norm_text 
                        for occ in collect_canonical_lexeme_occurrences(summary)
                    ]
                    record_payload["tokenizer_profile"] = get_canonical_tokenizer_profile()

                yield record_payload


def load_observed_events(log_root: str | Path) -> List[Dict[str, object]]:
    return list(iter_observed_events(Path(log_root)))
