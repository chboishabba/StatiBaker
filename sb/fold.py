from datetime import datetime, timedelta


def _parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d")


def _carryover_sets(prev_state, curr_state):
    prev_threads = set(prev_state.get("carryover_threads", []))
    curr_threads = set(curr_state.get("carryover_threads", []))
    if not curr_threads and prev_threads:
        curr_threads = prev_threads
    new_threads = sorted(curr_threads - prev_threads)
    resolved_threads = sorted(prev_threads - curr_threads)
    carryover_threads = sorted(curr_threads)
    return carryover_threads, new_threads, resolved_threads


def _age_days(prev_state, carryover_threads, new_threads, date):
    prev_age = prev_state.get("carryover_age_days", {}) if prev_state else {}
    age_days = {}
    for thread in carryover_threads:
        if thread in new_threads:
            age_days[thread] = 0
        else:
            age_days[thread] = int(prev_age.get(thread, 0)) + 1
    return age_days


def _window_counts(age_days, windows=None):
    windows = windows or [7, 14, 30]
    counts = []
    for window in windows:
        count = sum(1 for age in age_days.values() if age <= window)
        counts.append({"window_days": window, "count": count})
    return counts


def apply_minimal_fold(prev_state, curr_state, date):
    carryover_threads, new_threads, resolved_threads = _carryover_sets(prev_state, curr_state)
    age_days = _age_days(prev_state or {}, carryover_threads, new_threads, date)
    labels = list(curr_state.get("labels", []))
    if len(carryover_threads) >= 20 and "carryover_saturation" not in labels:
        labels.append("carryover_saturation")
    curr_state["carryover_threads"] = carryover_threads
    curr_state["carryover_new_threads"] = new_threads
    curr_state["carryover_resolved_threads"] = resolved_threads
    curr_state["carryover_age_days"] = age_days
    curr_state["carryover_window_counts"] = _window_counts(age_days)
    curr_state["labels"] = labels
    return curr_state


def previous_date(value):
    return (_parse_date(value) - timedelta(days=1)).strftime("%Y-%m-%d")
