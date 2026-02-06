from copy import deepcopy


def _signature(event):
    return (
        event.get("source"),
        event.get("type"),
        event.get("text"),
        event.get("thread_id"),
    )


def collapse_low_signal_events(events):
    if not events:
        return [], []

    compressed = []
    loss_profiles = []
    current = None

    for event in events:
        if not event.get("low_signal"):
            if current is not None:
                compressed.append(current)
                current = None
            compressed.append(event)
            continue

        if current is None:
            current = deepcopy(event)
            current.setdefault("collapsed_count", 1)
            current.setdefault("collapsed_ids", [event.get("id")])
            continue

        if _signature(current) == _signature(event):
            current["collapsed_count"] += 1
            current["collapsed_ids"].append(event.get("id"))
        else:
            compressed.append(current)
            current = deepcopy(event)
            current.setdefault("collapsed_count", 1)
            current.setdefault("collapsed_ids", [event.get("id")])

    if current is not None:
        compressed.append(current)

    if compressed != events:
        loss_profiles.append(
            {
                "kind": "collapse_low_signal_events",
                "details": {"collapsed": True},
            }
        )

    return compressed, loss_profiles


def apply_phase2_compression(state):
    events = state.get("events", [])
    compressed, loss_profiles = collapse_low_signal_events(events)
    state["events"] = compressed
    state["compression"] = {"loss_profiles": loss_profiles}
    return state


def expand_low_signal_events(events):
    expanded = []
    for event in events:
        collapsed_ids = event.get("collapsed_ids")
        if not collapsed_ids:
            expanded.append(event)
            continue
        for event_id in collapsed_ids:
            clone = {
                "id": event_id,
                "source": event.get("source"),
                "type": event.get("type"),
                "text": event.get("text"),
                "thread_id": event.get("thread_id"),
                "low_signal": event.get("low_signal", True),
            }
            expanded.append(clone)
    return expanded
