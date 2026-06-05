# Tool Interop Observer Contract

Date: 2026-02-07
Source conversation: `Conductor vs SB/ITIR` (`6986c9f5-3988-839d-ad80-9338ea8a04eb`)
Latest synced assistant reply timestamp: `2026-02-07T05:31:50.850667Z`

## Purpose
Define how StatiBaker interoperates with agent orchestration tools without becoming
an orchestration control plane.

## Core stance
- Execution tools optimize for running work.
- StatiBaker optimizes for preserving reconstructible history.
- External orchestration systems are read-only observers from SB's perspective.
- Cloud execution is allowed but non-authoritative.

## Learn, do not clone
StatiBaker can learn from adjacent tools while refusing scope collapse.

### `fcoury/conductor`
- Learn: intent as first-class artifacts (`spec`, `plan`, explicit phases).
- Keep: declared intent as observable evidence.
- Refuse: normative workflow authority inside SB.

### `ryanmac/code-conductor`
- Learn: cheap operational isolation (worktrees, task-to-branch boundaries).
- Keep: event hooks for reconstruction (`task_claimed`, `worktree_created`, `pr_merged`).
- Refuse: schedulers, agent pools, queue ownership.

### `Dimillian/CodexMonitor`
- Learn: multi-agent observability lens design.
- Keep: timeline and provenance surfaces as optional read-only panels.
- Refuse: cockpit/editor replacement scope.

## Hard boundaries
StatiBaker must not implement:
- agent orchestration runtimes
- task claiming/execution scheduling
- workflow gate enforcement
- control-plane billing logic
- IDE replacement UX

## Interop contract (read-only)
Allowed ingress from orchestration tools:
- session metadata (`tool`, `provider`, `repo`, `branch`, `actor`, `ts`)
- action lifecycle events (`started`, `paused`, `resumed`, `completed`, `failed`)
- provenance pointers (`issue`, `pr`, `commit`, `ci_run`, `artifact_uri`)
- execution outcomes (status, duration, retry count)
- bounded observer-class `fuzzymodo` decision telemetry when it stays
  append-only and reference-heavy (selector hash / artifact refs / reason
  codes, not raw selector or policy payloads)
- bounded observer-class `casey-git-clone` operation/build telemetry when it
  stays append-only and reference-heavy (workspace/tree/build ids, receipt
  hashes, explicit collapse/build refs, not mutable candidate graphs)
- bounded Corkysoft reviewed-event overlays when they stay reference-heavy and
  preserve Corkysoft authority labels rather than importing mutable removals
  workflow state into SB
- bounded Tree-sitter code-structure observations when they stay append-only,
  provenance-backed, scan-scoped, and non-authoritative; syntax evidence may
  support residual review but must not create or move cards

Forbidden ingress:
- generated semantic summaries as authoritative truth
- hidden memory state
- inferred goals/preferences
- policy decisions about what should happen next
- syntax-only parser observations as task completion, runtime truth, or
  Kanban workflow authority

## Cloud posture
- Cloud is an observer and execution substrate, not memory authority.
- Truth must remain portable across vendors and billing regimes.
- Retention limits or pricing changes must not erase reconstructibility.

## SB invariant restatement
- Observe, do not control.
- Preserve, do not overwrite.
- Expand, do not hide.

## Threat-model mapping: ITIR vs adjacent tools

The critical distinction:
- ITIR/SB maintain authority boundaries, provenance, and append-only state.
- External tools are usually observers, action surfaces, or summarizers.

### Category map

Knowledge graph / structure tools (Ace, Airtable, Notion, Outline, Hex):
- Overlap: structure views and downstream organization surfaces.
- Boundary: editable schema/state is not canonical state authority.
- Verdict: adjacent, non-replacing.

CRM / "source of truth" systems (HubSpot, HighLevel, Monday, Streak, Clay, PitchBook, LSEG, Morningstar):
- Overlap: operational summaries and workflow status surfaces.
- Boundary: mutable records and schema drift break append-only provenance.
- Verdict: high-risk observer if misused as authority.

Dev/runtime observers (GitHub, Vercel, Netlify, Docker tooling, Slack, Teams, Zoom):
- Overlap: execution and collaboration telemetry.
- Boundary: action/event observers, not semantic authority.
- Verdict: first-class observer inputs.

Operational systems of decision (for example Corkysoft):
- Overlap: reviewed operational summaries and read-only query surfaces.
- Boundary: producer remains authoritative; SB stores only reviewed overlays or
  query receipts, not mutable workflow state.
- Verdict: supported when the seam is explicit and authority-safe.

AI productivity/summarization tools:
- Overlap: presentation/rendering of derived outputs.
- Boundary: no provenance guarantees, uncertain compression semantics.
- Verdict: downstream renderer only.

Learning/data platforms:
- Overlap: none at state-authority layer.
- Verdict: orthogonal.

### Bottom line
- These tools can replace specific input collectors or output surfaces.
- They do not replace ITIR/SB authority rules.
- If any external system is treated as canonical memory authority, that is a
  contract violation, not a feature.
