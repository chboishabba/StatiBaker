# GOV-1 execution/service evidence projection

StatiBaker supplies operational evidence to GOV-1. It does **not** evaluate
controls, create semantic truth, decide compliance, rank users, or promote a
service from implemented to validated.

The projection owned by `src/statibaker_governance_evidence.py` carries two
orthogonal state coordinates:

```text
ServiceChangeState:
  proposed | implemented | verified | validated | released | observed |
  incident | rolled_back

EvidenceState:
  source_written | compile_checked | fixture_checked | runtime_observed |
  production_observed
```

`implemented != validated` and `compile_checked != runtime_observed` are hard
boundaries. A requested validated service state is downgraded to implemented
unless explicit validation receipt refs are supplied.

Execution evidence includes:

- execution refs;
- change refs;
- release refs;
- incident refs;
- problem refs;
- provenance refs;
- validation receipt refs;
- external synchronization status;
- whether canonical local state stayed unchanged.

An external-sync failure may create incident/problem evidence. It does not
rewrite canonical local state or alter semantic truth.

This projection is intended to be consumed by SensibLaw's control evaluator
and ITIR-suite's GOV-1 acceptance map. It remains an observer payload.
