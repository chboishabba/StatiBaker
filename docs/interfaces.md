# StatiBaker Interface Contract (Intended)

## Intersections
- Ingests state surfaces from ITIR projects and operator tooling.
- Consumes outputs from `SensibLaw/`, `tircorder-JOBBIE/`, and automation logs.
- Publishes distilled daily state for human and machine consumers.

## Interaction Model
1. Ingest append-only state streams from configured sources.
2. Compile temporal reductions (carryover/new/resolved) without rewriting source.
3. Emit traceable state briefs and unresolved-loop views.
4. Surface machine-action status as explicit pending/blocked state.

## Exchange Channels
### Channel A: State Ingress
- Input: logs, TODO ledgers, events, commits, tool outputs, metadata feeds.
- Constraint: append-only ingestion; no hidden normalization semantics.

### Channel B: Reduction Pipeline
- Input: reduction policies and time-window boundaries.
- Output: deterministic state snapshots per run.

### Channel C: Distilled Brief Egress
- Output: what happened, active intersections, unresolved loops, blockers.
- Consumer: ITIR operators and downstream dashboards.

### Channel D: Action-State Egress
- Output: machine action queue state (pending/blocked/completed) with provenance.
- Consumer: orchestration and audit tooling.
