import json


def _safe_len(value):
    if isinstance(value, list):
        return len(value)
    return 0


def _read_json(path):
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_runtime_ms(path, fallback):
    if fallback is not None:
        return fallback
    if not path:
        return 0
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def render_metrics(state_path=None, ledger_path=None, runtime_path=None, runtime_ms=None):
    state = _read_json(state_path) if state_path else None
    ledger = _read_json(ledger_path) if ledger_path else None

    activity_events = 0
    if isinstance(ledger, dict):
        activity_events = _safe_len(ledger.get("activity_events"))

    carryover_threads = 0
    if isinstance(state, dict):
        carryover_threads = _safe_len(state.get("carryover_threads"))

    runtime = _read_runtime_ms(runtime_path, runtime_ms)

    lines = [
        f"sb_activity_events_total {activity_events}",
        f"sb_carryover_threads_total {carryover_threads}",
        f"sb_sessionizer_runtime_ms {runtime}",
    ]
    return "\n".join(lines) + "\n"
