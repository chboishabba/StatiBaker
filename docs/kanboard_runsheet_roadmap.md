# Kanboard Runsheet Integration Roadmap

## Purpose

StatiBaker should project extracted task state into an inspectable Kanban UI
without making the UI canonical. The canonical bridge remains local JSON:
compiled StatiBaker task extraction, orchestration runsheets, and provenance
receipts. Kanboard is the first external synchronization target because its
JSON-RPC task procedures and task metadata model fit that bridge with minimal
translation.

Plane remains a mid/long-term candidate for a polished human-facing project UI
after the local bridge and Kanboard adapter prove the object model and sync
semantics.

## Source Surfaces

Primary local inputs:

- StatiBaker task extraction outputs from `src.statibaker_kanban`
- StatiBaker-style `timeline_cases` fixtures and derived task timelines
- orchestrator runner JSON: `status.<id>.json`, `heartbeat.<id>.json`
- local runsheet JSON:

```json
{
  "runsheet": {
    "items": [
      {"id": "read", "title": "Read execution brief", "status": "done"},
      {
        "id": "patch",
        "title": "Patch target module",
        "status": "in_progress",
        "subtasks": [
          {"title": "Add witness", "status": "done"},
          {"title": "Run validation", "status": "todo"}
        ]
      }
    ]
  }
}
```

Large extracted task sheets may be referenced instead of embedded:

```json
{
  "runsheet_source": {"path": "relative/or/absolute/tasks.json"}
}
```

## Bridge Model

Normalize all source forms into a single task row model before syncing:

- `stable_id`: local stable identifier for idempotency
- `title`: human task title
- `status`: `todo | in_progress | blocked | done | skipped`
- `runner_id`: optional orchestrator id
- `lane`: optional orchestration lane or source project lane
- `parent_id`: optional parent task id for subtasks or successors
- `depth`: `0` for top-level task, `1+` for subtasks
- `source`: `status | heartbeat | timeline_cases | statibaker_task_memory`
- `provenance`: dictionary of source receipts and residuals
- `acceptance_criteria`: optional task acceptance text
- `labels`: optional normalized tags
- `description`: optional durable card detail text
- `metadata`: optional `statibaker.*` values to stamp through Kanboard task
  metadata

The derived progress rule is intentionally simple:

- count only top-level non-skipped rows
- `completed = done rows`
- `total = counted rows`
- current milestone is the first `in_progress` or `blocked` row title
- percentage is derived by the consumer, not stored as authority

## Kanboard Mapping

Use a one-way projection at first: local JSON to Kanboard.

Kanboard project layout:

- One Kanboard project per StatiBaker board or orchestration domain.
- Columns map from normalized status:
  - `todo` -> `Backlog`
  - `in_progress` -> `Doing`
  - `blocked` -> `Blocked`
  - `done` -> `Done`
  - `skipped` -> `Skipped` or closed task, depending on board policy
- Swimlanes map to `lane` when present; otherwise use `Default`.
- Top-level task rows become Kanboard tasks.
- Subtasks can initially be rendered into task Markdown checklists; later they
  may become linked tasks if Kanboard task links are needed.

Required Kanboard API procedures:

- `getTaskByReference`: idempotency lookup by local `stable_id`
- `createTask`: create missing top-level cards
- `updateTask`: update title, description, owner/category/priority where mapped
- `moveTaskPosition`: move cards into the status column and preserve order
- task metadata procedures: store provenance and local sync state
- `setTaskTags`: project local labels as real Kanboard task tags

Task metadata keys should include:

- `statibaker.stable_id`
- `statibaker.source`
- `statibaker.runner_id`
- `statibaker.lane`
- `statibaker.parent_id`
- `statibaker.canonical_thread_id`
- `statibaker.source_message_id`
- `statibaker.lifecycle_residual`
- `statibaker.task_identity_residual`
- `statibaker.labels`
- `statibaker.ao.phase`
- `statibaker.ao.heartbeat`
- `statibaker.ao.current_step`
- `statibaker.ao.milestones`
- `statibaker.ao.runtime`
- `statibaker.ao.completed_at`
- `statibaker.ao.promotion`
- `statibaker.ao.validation`
- `statibaker.ao.retry_of`
- `statibaker.last_sync_at`

## AO Live Control Surface

The AO control board is a live projection from durable autonomous-orchestrator
artifacts, not from chat summaries:

```text
AO status/heartbeat/parent reports -> StatiBaker projection/sync -> Kanboard
```

Use `StatiBaker/scripts/sync_ao_kanboard_control_surface.py` to build and sync
the board. It bootstraps these additional operational columns when `--apply` is
used:

- `Queued`
- `Running`
- `Needs Retry`
- `Blocked Upstream`
- `Validation Needed`
- `Done`
- `Skipped`

Derived AO state:

- active child heartbeat -> `Running`
- nonzero exit or rejected/failed phase -> `Needs Retry`
- explicit blocker or blocked runsheet row -> `Blocked Upstream`
- completed lane with pending validation/test row -> `Validation Needed`
- accepted/done lane -> `Done`
- skipped lane -> `Skipped`

Labels are projected as Kanboard tags, for example:

- `ao:manager-accepted`
- `ao:manager-rejected`
- `ao:blocked-upstream`
- `ao:validation-needed`
- `ao:stale`
- `ao:non-promotion`

Completed stale heartbeats are rendered as `done@<timestamp>` metadata instead
of forcing a stale/blocker state. Refreshes should use live Kanboard reference
lookups before planning so existing cards can move columns without duplicate
creates.

## Phase Plan

## Completion Manager Lanes

Use up to six manager lanes to complete the Kanboard integration. Managers own
the lane plan, sequencing, integration, and promotion decision. Workers are not
lane steps. A manager may spawn up to six workers only for independent sidecar
tasks that can run in parallel without blocking the manager's immediate next
action and without sharing a write surface.

Worker allocation rules:

- Spawn zero workers when the next move is narrow, sequential, or blocked on one
  decision.
- Spawn workers only for parallelism, not as a substitute for the manager's
  critical-path implementation.
- Give each worker a disjoint write set or make it explicitly read-only.
- Merge and validate worker output in the manager lane before promotion.
- Do not spawn workers for dependent tasks such as "discover ids, then use those
  ids" unless the later task can proceed from a stable fixture or mock.
- Keep local JSON canonical throughout; Kanboard remains an external projection.

### Lane 1: Kanboard Board Bootstrap Manager

Objective: make the target Kanboard project structurally ready for sync.

Parallel worker candidates, only if independent:

- Discover project, swimlane, and column ids from JSON-RPC.
- Create or verify columns: `Backlog`, `Doing`, `Blocked`, `Done`, `Skipped`.
- Generate a local `column_map.json` artifact from observed Kanboard ids.
- Validate project `1` exists or create a named project when missing.
- Add focused tests for column-map parsing and status-to-column mapping.
- Document local endpoint/bootstrap assumptions without storing secrets.

Manager critical path:

- Discover or create the project/columns, then integrate the observed ids into
  one reviewed bootstrap command/report.

Exit gate:

- A repeatable bootstrap command can produce the same board shape without
  duplicating columns or projects.

### Lane 2: Live Sync Apply Manager

Objective: implement explicit one-way `--apply` sync from local runsheet JSON to
Kanboard.

Parallel worker candidates, only if independent:

- Implement JSON-RPC client/auth/env loading.
- Implement `getTaskByReference` lookup and create-if-missing behavior.
- Implement task update behavior for title and description.
- Implement status-column movement through `moveTaskPosition`.
- Implement metadata writes for all `statibaker.*` keys.
- Add dry-run/apply CLI separation so mutation requires explicit opt-in.

Manager critical path:

- Define the apply transaction/order first; then split client, metadata,
  movement, and CLI tests only if their write sets can remain separate.

Exit gate:

- `--apply` can create/update/move/metadata-write top-level cards against the
  local Kanboard instance.

### Lane 3: Idempotency And Failure Semantics Manager

Objective: prove repeated syncs are stable and failures do not corrupt local
state.

Parallel worker candidates, only if independent:

- Add mocked JSON-RPC tests for first-run creates and second-run no-creates.
- Add tests for partial RPC failure and retry/report behavior.
- Add duplicate reference and missing column failure tests.
- Verify skipped/blocked/done transitions move exactly once per changed state.
- Add local sync snapshot loading for existing cards.
- Ensure local status/runsheet JSON is never rewritten by Kanboard failures.

Manager critical path:

- Establish the idempotency invariant and failure model, then parallelize
  independent test cases against that invariant.

Exit gate:

- Second sync over unchanged input reports zero creates and no duplicate cards.

### Lane 4: Sync Report And Dashboard Manager

Objective: expose sync outcome as a first-class read-only StatiBaker artifact.

Parallel worker candidates, only if independent:

- Define sync report JSON schema and artifact path.
- Write sync reports with creates/updates/moves/metadata/errors.
- Add query surface for latest Kanboard sync report.
- Add dashboard panel/metrics for latest sync status.
- Add tests for report persistence and dashboard/query rendering.
- Link Kanboard ids/URLs as external references only.

Manager critical path:

- Freeze the report schema first; dashboard, query, persistence, and tests can
  then proceed in parallel if each worker owns a distinct file/module set.

Exit gate:

- StatiBaker can show the latest Kanboard sync outcome without making Kanboard
  authoritative.

### Lane 5: SensibLaw Bridge Source Manager

Objective: ensure extracted task memory/timeline outputs can feed the same
Kanboard sync path.

Parallel worker candidates, only if independent:

- Emit or export `sl.statibaker_runsheet_bridge.v0_1` rows to a file shape the
  StatiBaker adapter can consume.
- Add fixtures covering task memory plus timeline status reconciliation.
- Map SensibLaw residuals into `statibaker.lifecycle_residual` and
  `statibaker.task_identity_residual`.
- Verify unmatched timeline/task cases remain boundary gaps.
- Add one end-to-end dry-run from SensibLaw bridge output to Kanboard plan.
- Document taskhood authority boundaries for extracted tasks.

Manager critical path:

- Preserve taskhood authority and residual semantics first; workers may only
  parallelize fixtures, exports, and dry-run checks once that contract is fixed.

Exit gate:

- A SensibLaw bridge artifact can produce the same Kanboard operation plan shape
  as orchestrator `runsheet.items`.

### Lane 6: Governance, Docs, And Promotion Manager

Objective: close the integration as a governed one-way projection.

Parallel worker candidates, only if independent:

- Update roadmap phase status and remaining non-goals.
- Update `CHANGELOG.md`, `QUERY_SURFACE.md`, and docs index.
- Verify no token/secret is committed.
- Run focused StatiBaker and SensibLaw test gates.
- Produce final promotion report with residual risks.
- Define the future Plane/Taiga evaluation trigger without implementing it.

Manager critical path:

- Wait for implementation lanes to report before promotion. Secret scan, test
  gates, and independent doc surfaces may run in parallel, but the final
  promotion report is manager-owned.

Exit gate:

- Docs, tests, sync reports, and authority boundaries all agree that Kanboard is
  a one-way external projection and local JSON remains canonical.

### Phase 1: Local Runsheet Contract

- Keep `--print-runsheet` and `--watch-runsheet` as the canonical local view.
- Add sample runsheet artifacts under a non-production fixture path.
- Add validation for malformed statuses, missing ids, duplicate ids, and nested
  subtasks.
- Ensure agents and orchestrator workers update `runsheet.items` in runner
  state when they can identify task/subtask structure.

Exit criteria:

- Local rows render consistently from `runsheet.items`, generic `tasks`, and
  StatiBaker `timeline_cases`.
- Derived progress matches top-level runsheet status.

### Phase 2: Kanboard Adapter Dry Run

- Add a standalone adapter script or module under StatiBaker, not inside the
  orchestrator runner.
- Inputs: local runsheet JSON path, Kanboard base URL, API token, project id.
- Output: dry-run plan showing create/update/move/metadata operations.
- Do not mutate Kanboard by default.

Exit criteria:

- Dry-run output is deterministic.
- Existing Kanboard cards can be matched by `reference`.
- Provenance metadata payload is visible in the planned operations.

### Phase 3: One-Way Kanboard Sync

- Enable explicit `--apply` mode for local JSON to Kanboard sync.
- Use `getTaskByReference` before every create.
- Create or update task metadata on every sync.
- Move tasks only when normalized status changes.
- Keep a local sync report artifact with counts and failures.

Exit criteria:

- Re-running sync is idempotent.
- Kanboard shows the same top-level status counts as local `--print-runsheet`.
- Failed Kanboard calls do not corrupt local state.

### Phase 4: Feedback and Governance

- Keep Kanboard non-authoritative initially.
- Optionally ingest Kanboard card URLs or ids back into local metadata as
  external references only.
- Evaluate whether human edits in Kanboard should ever flow back into
  StatiBaker; default answer is no until a conflict policy exists.

Exit criteria:

- Round-trip policy is documented before any inbound sync is implemented.
- Human Kanboard edits cannot silently rewrite extracted task provenance.

### Phase 5: Plane Evaluation

- Revisit Plane after Kanboard sync proves the bridge model.
- Evaluate mapping local rows to Plane issues, states, labels, modules, and
  cycles.
- Treat Plane as a polished human-facing UI, not canonical state.

Exit criteria:

- A Plane adapter design exists with explicit object mapping and conflict
  policy.
- Kanboard adapter limitations are known and motivate the Plane integration.

## Non-Goals

- Do not make Kanboard or Plane the source of truth.
- Do not require external Kanban services for local orchestration progress.
- Do not store opaque JSON blobs in human descriptions when task metadata is
  available.
- Do not implement two-way sync until conflict semantics are explicit.
