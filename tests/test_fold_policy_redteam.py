import json

from sb.fold import apply_minimal_fold


def _iter_string_values(value):
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for v in value.values():
            yield from _iter_string_values(v)
        return
    if isinstance(value, list):
        for v in value:
            yield from _iter_string_values(v)


def test_fold_policy_uses_machine_flags_not_free_text_nudges():
    out = apply_minimal_fold(
        prev_state={"carryover_threads": ["a"], "carryover_age_days": {"a": 2}},
        curr_state={"carryover_threads": ["a", "b"]},
        date="2026-02-07",
    )
    policy = out.get("fold_policy") or {}
    flags = policy.get("mechanical_should_flags")
    assert isinstance(flags, dict) and flags
    assert all(isinstance(v, bool) for v in flags.values())


def test_fold_policy_and_loss_profile_reject_imperative_nudge_text():
    out = apply_minimal_fold(
        prev_state={"carryover_threads": ["a"], "carryover_age_days": {"a": 1}},
        curr_state={"carryover_threads": ["a"]},
        date="2026-02-07",
        policy_receipt="rcpt:fold-policy-v1",
    )
    policy = out.get("fold_policy") or {}
    banned_tokens = {"must", "should ", "should.", "ought", "immediately", "recommend", "urgent", "action now"}
    string_values = [s.lower() for s in _iter_string_values(policy)]
    dump = json.dumps(string_values, sort_keys=True)
    for token in banned_tokens:
        assert token not in dump
