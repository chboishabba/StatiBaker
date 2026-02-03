# Compactified Context

Date: 2026-02-03

## Sources
- `StatiBaker Proposal.pdf`: proposal for a daily state distillation engine.
- `ITIR - anti-enshit.pdf`: notes on enshittification phases and mitigation.

## Project intent
StatiBaker compiles human and machine state into a daily brief with traceability to
raw logs. It emits a human-readable brief, a machine-readable agent state, and an
end-of-day retrospective.

## Core model
- Events (atomic, timestamped facts)
- Threads (related events)
- Trajectories (thread histories over time)

## Pipeline
Ingest (append-only) -> Normalize -> Compress (bake) -> Emit (human brief, agent
JSON, optional graph).

## Anti-enshit principles
- User utility over engagement or extraction
- Transparent, traceable summaries
- Data portability and interoperability
- No memory rewriting; append-only logs

## Epistemic invariants
- Declared state is authoritative; observed state is evidentiary; derived artifacts are provisional.
- Derived artifacts (e.g., OCR) never become state without explicit promotion.
- Automatic extraction may occur, but automatic belief may not.

## MVP staging
- Week 1: journal/TODO/agent logs -> daily summary + nightly retrospective
- Week 2: calendar + git, agent task queue, carryover threads
- Week 3: smart home hooks, energy/alert annotations, drift detection

## Open questions
- Drift representation and scoring
- Safe defaults for agent autonomy
- Canonical portable export format
