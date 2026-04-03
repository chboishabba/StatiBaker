from collections import Counter


DEFAULTS = {
    "stale_days": 7,
    "low_signal_run_min": 3,
    "high_activity_min": 20,
    "low_diversity_max": 1,
    "context_dominance_threshold": 0.85,
}


def _count_low_signal_runs(events, min_len):
    runs = 0
    current = 0
    for event in events:
        if event.get("low_signal"):
            current += 1
        else:
            if current >= min_len:
                runs += 1
            current = 0
    if current >= min_len:
        runs += 1
    return runs


def compute_drift(state, *, cfg=None):
    cfg = {**DEFAULTS, **(cfg or {})}

    age_days = state.get("carryover_age_days", {})
    stale = sum(1 for age in age_days.values() if age >= cfg["stale_days"])

    events = state.get("events", [])
    low_signal_events = sum(1 for event in events if event.get("low_signal"))
    low_signal_runs = _count_low_signal_runs(events, cfg["low_signal_run_min"])

    sources = {event.get("source") for event in events if event.get("source")}
    source_diversity = len(sources)

    thread_ids = [event.get("thread_id") for event in events if event.get("thread_id")]
    dominant_thread_fraction = 0.0
    dominant_thread_id = None
    if thread_ids:
        counter = Counter(thread_ids)
        dominant_thread_id, dominant_count = counter.most_common(1)[0]
        dominant_thread_fraction = dominant_count / max(len(events), 1)

    context_dominance = dominant_thread_fraction >= cfg["context_dominance_threshold"]

    high_activity_low_diversity = (
        len(events) >= cfg["high_activity_min"] and source_diversity <= cfg["low_diversity_max"]
    )

    flags = []
    if high_activity_low_diversity:
        flags.append("high_activity_low_diversity")
    if context_dominance:
        flags.append("context_dominance")

    counters = {
        "stale_carryover_threads": stale,
        "low_signal_events": low_signal_events,
        "low_signal_runs": low_signal_runs,
        "event_source_diversity": source_diversity,
        "dominant_thread_fraction": dominant_thread_fraction,
        "dominant_thread_id": dominant_thread_id,
    }

    return {
        "counters": counters,
        "flags": flags,
        "provenance": {
            "algorithm": "sb.drift.v1",
            "config": cfg,
        },
    }
