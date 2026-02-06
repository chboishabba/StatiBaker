import json
from pathlib import Path


def _resolve_path(path):
    return Path(path).expanduser().resolve()


def _read_json(path, base_dir=None):
    target = _resolve_path(path)
    if base_dir:
        base = _resolve_path(base_dir)
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"path escapes base_dir: {path}") from exc
    with open(target, "r", encoding="utf-8") as handle:
        return json.load(handle)


def list_activity_events(ledger_path, base_dir=None):
    ledger = _read_json(ledger_path, base_dir=base_dir)
    return ledger.get("activity_events", []) if isinstance(ledger, dict) else []


def carryover_summary(state_path, base_dir=None):
    state = _read_json(state_path, base_dir=base_dir)
    return {
        "carryover_threads": state.get("carryover_threads", []),
        "carryover_new_threads": state.get("carryover_new_threads", []),
        "carryover_resolved_threads": state.get("carryover_resolved_threads", []),
        "carryover_age_days": state.get("carryover_age_days", {}),
    }


def provenance(state_path, ledger_path=None, drift_path=None, base_dir=None):
    state = _read_json(state_path, base_dir=base_dir)
    payload = {"sources": state.get("sources", [])}
    if ledger_path:
        ledger = _read_json(ledger_path, base_dir=base_dir)
        payload["activity_ledger"] = ledger.get("provenance", {}) if isinstance(ledger, dict) else {}
    if drift_path:
        drift = _read_json(drift_path, base_dir=base_dir)
        payload["drift"] = drift.get("provenance", {}) if isinstance(drift, dict) else {}
    return payload
