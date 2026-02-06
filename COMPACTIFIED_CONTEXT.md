# Compactified Context

Date: 2026-02-05

## Sources
- `StatiBaker Proposal.pdf`: proposal for a daily state distillation engine.
- `ITIR - anti-enshit.pdf`: notes on enshittification phases and mitigation.

## Project intent
StatiBaker compiles human and machine state into a daily brief with traceability to
raw logs. It emits a human-readable brief, a machine-readable agent state, and an
end-of-day retrospective.
SB is a context prosthesis: a temporal compiler that reconstructs lived time
without interpreting meaning.
Primary focus: ADHD support via reliable state reconstruction after context collapse.

## Core model
- Events (atomic, timestamped facts)
- Threads (related events)
- Trajectories (thread histories over time)
- SB ingests refs to ITIR/TIRC/SL artifacts and compiles temporal deltas only.
- SB owns activity_events (deterministic segmentation of observed snapshots).
- ITIR ingests activity_events for narrative and linkage; OpenRecall renders evidence.

## Pipeline
Ingest (append-only) -> Normalize -> Temporal reduction (carryover/new/resolved)
-> Emit (human brief, agent JSON, optional graph).
Phase 1 minimal fold adds carryover age_days and rolling window counts (7/14/30)
and emits a daily brief from git log + optional uptime via `scripts/run_day.sh`.

## Anti-enshit principles
- User utility over engagement or extraction
- Transparent, traceable summaries
- Data portability and interoperability
- No memory rewriting; append-only logs

## Epistemic invariants
- Declared state is authoritative; observed state is evidentiary; derived artifacts are provisional.
- Derived artifacts (e.g., OCR) never become state without explicit promotion.
- Automatic extraction may occur, but automatic belief may not.
- No agency; append-only reality; explicit loss profiles; deterministic replay with cheap expansion.

## Observability decisions
- SB consumes numeric summaries from Prometheus (including Graphite exporter metrics).
- Grafana is display-only, not a data source.
- InfluxDB (Home Assistant) is optional once credentials and live data are confirmed.

## MVP staging
- Week 1: journal/TODO/agent logs -> daily summary + nightly retrospective
- Week 2: calendar + git, agent task queue, carryover threads
- Week 3: smart home hooks, energy/alert annotations, drift detection

## Sprint plan (2026-02-05)
- Sprint 1: core hardening and temporal trust (guard tests, multi-day replay).
- Sprint 2: external observation without authority (Wazuh lifecycle, Prometheus summaries, `/metrics`).
- Sprint 3: boundary definition (OCR contract, Android status contract, read-only query surface).
Detailed scope, acceptance criteria, and non-goals: `__CONTEXT/sprints/stati_baker_sprints.md`.

## Sprint plan (4–6 continuation)
- Sprint 4: stress/absence/drift characterization (read-only drift probes, bad data runs).
- Sprint 5: selective Phase-2 compression with explicit loss profiles and expansion tests.
- Sprint 6: read-only query surface + agent containment + ITIR overlay enforcement.
Plan: `__CONTEXT/sprints/stati_baker_sprints_4_6.md`.

## Recent execution (2026-02-05)
- Drift counters now emit to `runs/<date>/outputs/drift.json`.
- Phase-2 compression collapse is implemented for `low_signal=true` events.
- Read-only query surface is implemented as CLI (`scripts/query_state.py`).

## Sprint plan (7–9 continuation)
- Sprint 7: portability + replay integrity (bundle export/verify).
- Sprint 8: time hygiene + long-run decay (documented policy + stress tests).
- Sprint 9: boundary lock + red-team pass (failure modes + rejection tests).
Plan: `__CONTEXT/sprints/stati_baker_sprints_7_9.md`.

## Sprint 9 additions (2026-02-06)
- Red-team plan expanded to include event injection, command/RCE, credential leakage,
  path traversal, DoS/resource exhaustion, and blast-radius constraints.
- Failure modes updated with explicit blast-radius definition and limits.

## OpenClaw integration (2026-02-06)
- Execution envelope contract and truth-substrate doctrine documented in
  `docs/openclaw_integration.md`.

## Multi-modal doctrine (2026-02-06)
- Epistemic modes and boundary rules documented in
  `docs/multimodal_system_doctrine.md`.

## Open questions
- Drift representation and scoring
- Safe defaults for agent autonomy
- Canonical portable export format
