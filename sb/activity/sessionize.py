import argparse
import hashlib
import json
import sys
from datetime import datetime


DEFAULT_CONFIG = {
    "idle_gap_s": 300,
    "title_jaccard_min": 0.3,
    "phash_jump_min": 12,
    "app_label_map": {},
}


def _parse_ts(ts):
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _clean_title(title):
    return " ".join(title.strip().lower().split())


def _tokenize(title):
    return set(_clean_title(title).split())


def _jaccard(a, b):
    if not a or not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 1.0


def _parse_phash(hash_value):
    if not hash_value:
        return None
    if hash_value.startswith("phash:"):
        hash_value = hash_value.split(":", 1)[1]
    try:
        return int(hash_value, 16)
    except ValueError:
        return None


def _hamming_distance(a, b):
    if a is None or b is None:
        return 0
    return bin(a ^ b).count("1")


def _primary_app(snapshot_batch):
    counts = {}
    latest = None
    for snap in snapshot_batch:
        app_id = snap.get("app_id")
        if not app_id:
            continue
        counts[app_id] = counts.get(app_id, 0) + 1
        latest = app_id
    if not counts:
        return ""
    max_count = max(counts.values())
    tied = [app for app, count in counts.items() if count == max_count]
    if len(tied) == 1:
        return tied[0]
    return latest or tied[-1]


def _title_for_event(snapshot_batch, app_label_map):
    for snap in reversed(snapshot_batch):
        title = snap.get("window_title")
        if title:
            return _clean_title(title), True
    app_id = _primary_app(snapshot_batch)
    if app_id:
        label = app_label_map.get(app_id, "")
        if label:
            return _clean_title(label), False
        return f"using {app_id}", False
    return "activity", False


def _confidence(snapshot_batch, title_from_window):
    score = 0.5
    if len(snapshot_batch) >= 3:
        score += 0.2
    if title_from_window:
        score += 0.1
    if any(snap.get("redacted") for snap in snapshot_batch):
        score -= 0.2
    return max(0.0, min(1.0, score))


def _policy_flags(snapshot_batch):
    flags = []
    seen = set()
    for snap in snapshot_batch:
        for flag in snap.get("policy_flags", []):
            if flag not in seen:
                seen.add(flag)
                flags.append(flag)
    return flags


def sessionize_snapshots(snapshots, config=None):
    cfg = DEFAULT_CONFIG.copy()
    if config:
        cfg.update(config)

    ordered = sorted(snapshots, key=lambda s: (s["ts"], s["id"]))
    events = []
    current = []

    def flush():
        if not current:
            return
        title, from_window = _title_for_event(current, cfg.get("app_label_map", {}))
        event_id = f"act-{len(events) + 1:06d}"
        event = {
            "id": event_id,
            "t_start": current[0]["ts"],
            "t_end": current[-1]["ts"],
            "snapshot_ids": [snap["id"] for snap in current],
            "primary_app": _primary_app(current),
            "title": title,
            "key_text": [],
            "thumb_snapshot_id": current[-1]["id"],
            "confidence": _confidence(current, from_window),
            "policy_flags": _policy_flags(current),
            "derived_from": [snap["id"] for snap in current],
        }
        events.append(event)

    for snap in ordered:
        if not current:
            current.append(snap)
            continue

        prev = current[-1]
        prev_ts = _parse_ts(prev["ts"])
        curr_ts = _parse_ts(snap["ts"])
        delta_s = (curr_ts - prev_ts).total_seconds()

        app_change = bool(prev.get("app_id") and snap.get("app_id") and prev["app_id"] != snap["app_id"])
        display_change = bool(
            prev.get("display_id")
            and snap.get("display_id")
            and prev["display_id"] != snap["display_id"]
        )
        idle_gap = delta_s >= cfg["idle_gap_s"]

        prev_title = prev.get("window_title", "")
        curr_title = snap.get("window_title", "")
        title_sim = _jaccard(_tokenize(prev_title), _tokenize(curr_title))
        title_drift = title_sim < cfg["title_jaccard_min"]

        prev_phash = _parse_phash(prev.get("hash"))
        curr_phash = _parse_phash(snap.get("hash"))
        phash_jump = _hamming_distance(prev_phash, curr_phash) >= cfg["phash_jump_min"]

        soft_score = (1 if title_drift else 0) + (1 if phash_jump else 0)
        hard_break = idle_gap or app_change or display_change
        soft_break = soft_score >= 2

        if hard_break or soft_break:
            flush()
            current = [snap]
        else:
            current.append(snap)

    flush()
    return events


def _input_hash(snapshots):
    ordered = sorted(snapshots, key=lambda s: (s["ts"], s["id"]))
    payload = "\n".join(f"{snap['id']}|{snap['ts']}" for snap in ordered)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_ledger(snapshots, policy_receipt=None, config=None):
    return {
        "activity_events": sessionize_snapshots(snapshots, config=config),
        "provenance": {
            "algorithm": "sb.sessionize.v0",
            "input_hash": _input_hash(snapshots),
            "policy_receipt": policy_receipt or "",
        },
    }


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    validate_config(data)
    return data


def validate_config(config):
    if "idle_gap_s" in config and not isinstance(config["idle_gap_s"], int):
        raise ValueError("idle_gap_s must be an integer")
    if "idle_gap_s" in config and config["idle_gap_s"] < 0:
        raise ValueError("idle_gap_s must be >= 0")
    if "title_jaccard_min" in config and not isinstance(config["title_jaccard_min"], (int, float)):
        raise ValueError("title_jaccard_min must be a number")
    if "title_jaccard_min" in config:
        if config["title_jaccard_min"] < 0 or config["title_jaccard_min"] > 1:
            raise ValueError("title_jaccard_min must be between 0 and 1")
    if "phash_jump_min" in config and not isinstance(config["phash_jump_min"], int):
        raise ValueError("phash_jump_min must be an integer")
    if "phash_jump_min" in config and config["phash_jump_min"] < 0:
        raise ValueError("phash_jump_min must be >= 0")
    if "app_label_map" in config and not isinstance(config["app_label_map"], dict):
        raise ValueError("app_label_map must be an object")


def main():
    parser = argparse.ArgumentParser(description="Deterministic snapshot sessionizer")
    parser.add_argument("input", help="Path to snapshots JSON")
    parser.add_argument("--output", help="Path to write activity ledger JSON")
    parser.add_argument("--policy-receipt", default="", help="Policy receipt identifier")
    parser.add_argument("--config", help="Path to sessionizer config JSON")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            snapshots = data.get("snapshots", data)
        elif isinstance(data, list):
            snapshots = data
        else:
            raise ValueError("snapshots input must be a list or object")
        config = load_config(args.config) if args.config else None
        ledger = build_ledger(snapshots, policy_receipt=args.policy_receipt, config=config)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(ledger, handle, indent=2, sort_keys=True)
    else:
        json.dump(ledger, fp=sys.stdout, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
