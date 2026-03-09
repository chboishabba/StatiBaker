# StatiBaker Interface Contract (Intended)

## Intersections
- Ingests state surfaces from ITIR projects and operator tooling.
- Consumes outputs from `SensibLaw/`, `tircorder-JOBBIE/`, and automation logs.
- May consume observer-only Wikipedia revision-monitor exports from
  `SensibLaw/` as external-signal refs (run summaries, candidate-pair refs,
  issue-packet refs, section-delta refs, contested-graph refs/summaries).
- May consume observer-only `fuzzymodo` decision/execution artifacts through a
  bounded append-only seam; see suite note
  `docs/planning/fuzzymodo_statiBaker_interface_20260309.md`.
- May consume observer-only `casey-git-clone` workspace/collapse/build
  receipts through a bounded append-only seam; see suite note
  `docs/planning/casey_git_clone_statiBaker_interface_20260309.md`.
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
- Wikipedia-revision-monitor rule:
  - allowed only as observer-class refs or append-only external-signal rows
  - pair scores, section deltas, and issue packets do not become SB canonical
    truth or SB policy
  - article text/revision text is not ingested as SB authoritative state
- `fuzzymodo`-specific rule:
  - allowed only as observer events or reference-heavy overlays
  - selector DSL payloads and norm constraints are not SB canonical state
  - speculative or approved decisions do not become SB policy
- `casey-git-clone`-specific rule:
  - allowed only as observer events or reference-heavy overlays
  - workspace/candidate/build authority remains in Casey
  - SB may store operation/build refs but not mutable candidate graphs

### Channel B: Reduction Pipeline
- Input: reduction policies and time-window boundaries.
- Output: deterministic state snapshots per run.

### Channel C: Distilled Brief Egress
- Output: what happened, active intersections, unresolved loops, blockers.
- Consumer: ITIR operators and downstream dashboards.

### Channel D: Action-State Egress
- Output: machine action queue state (pending/blocked/completed) with provenance.
- Consumer: orchestration and audit tooling.

### Channel E: Observer Overlay Ingress
- Input: reference-heavy overlays attached to existing SB activity/state rows.
- Intended use:
  - ITIR observer overlays already accepted under existing contracts
  - future `fuzzymodo_selector_v1` overlays may attach selector hashes,
    decision artifact refs, and reason codes by reference only
  - future `casey_workspace_v1` overlays may attach workspace refs, operation
    receipts, and build refs by reference only
- Constraint:
  - overlays cannot rewrite SB history
  - overlays cannot inject raw thread/event dumps
  - overlays cannot import external policy as SB authority
