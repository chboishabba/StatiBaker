REQUIRED_FIELDS = {"activity_event_id", "annotation_id", "provenance"}
OPTIONAL_FIELDS = {"sb_state_id", "state_date"}
FORBIDDEN_FIELDS = {
    "activity_events",
    "activity_ledger",
    "drift",
    "events",
    "snapshots",
    "state",
    "threads",
    "mutations",
}


def validate_overlay(record):
    if not isinstance(record, dict):
        return ["overlay must be a dict"]

    errors = []
    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    if not ("sb_state_id" in record or "state_date" in record):
        errors.append("missing sb_state_id or state_date")

    forbidden = FORBIDDEN_FIELDS.intersection(record.keys())
    if forbidden:
        errors.append(f"forbidden fields present: {sorted(forbidden)}")

    return errors
