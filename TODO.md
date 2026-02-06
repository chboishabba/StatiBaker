# TODO

## Completed (2026-02-03)
- Drafted human daily brief and retrospective templates (`BRIEF_TEMPLATE.md`)
- Defined machine state JSON schema (`STATE_SCHEMA.json`)
- Created synthetic sample state (`SAMPLE_STATE.json`)
- Specified append-only ingestion formats (`INGESTION_FORMATS.md`)

## Completed (2026-02-05)
- Drafted ADR for Recall-class capture + activity events
- Added snapshot and activity_event schema stubs to `STATE_SCHEMA.json`
- Drafted sessionization spec (`SESSIONIZATION_SPEC.md`)
- Implemented deterministic sessionizer stub with provenance ledger
- Added golden snapshot fixtures and tests for sessionization
- Added sessionizer config file and Makefile targets
- Added sessionizer config validation and Justfile targets
- Added config validation tests and CLI error handling
- Added CLI exit-code test for invalid config
- Added "core questions + context prosthesis" section to `CONTEXT.md`
- Added ADR: external signal condensers (Wazuh, osquery) are non-authoritative observers
- Implemented carryover window counts (7/14/30) in minimal fold + schema
- Included carryover deltas in generated daily brief
- Generated a sample daily brief from real logs
- Added guard tests for fold non-mutation and no content summarization.
- Ran multi-day replay (2026-02-06 to 2026-02-08) to validate deterministic carryover aging.
- Added Wazuh lifecycle adapter (structured, lifecycle-only).
- Added metrics HTTP server for `/metrics` over baked state outputs.
- Added determinism tests for adapter outputs and Prometheus summary helpers.
- Drafted OCR/Android/query/ITIR ingest contracts.
- Added ITIR overlay validation helper and tests.
- Implemented drift counters (separate `drift.json`) + drift doc.
- Implemented Phase-2 compression collapse for `low_signal=true` events.
- Added read-only query CLI (`scripts/query_state.py`).
- Added bundle export/verify tooling and spec.
- Documented time hygiene policy and failure modes.
- Added red-team boundary tests and bundle verification tests.
- Expanded red-team plan and added injection/RCE/metric-smuggling/env-leak tests.
- Added inactivity run test for empty git repositories.
- Added bundle export/replay test (export + verify).

## Completed (2026-02-06)
- Expanded red-team plan to cover DoS/resource exhaustion, path traversal, and
  blast-radius constraints.
- Updated failure-mode catalog with explicit blast-radius definition and limits.
- Added query base-path guard for safe reads with optional CLI enforcement.
- Extended ITIR ingest contract with explicit forbidden fields.

## Sprint plan references (2026-02-05)
- Sprint plan: `__CONTEXT/sprints/stati_baker_sprints.md`.
- Sprint 1 focus: guard tests + multi-day replay (see "Normalization and compression (Phase 1: minimal fold)").
- Sprint 2 focus: Wazuh lifecycle + Prometheus summaries + `/metrics` (see "Integration roadmap" and "Observability").
- Sprint 3 focus: OCR/Android/read-only contracts (see "Integration roadmap" and "Governance and safety").

## Define intent and scope
- Sprint plan reference: `__CONTEXT/sprints/stati_baker_sprints.md`.
- Review daily brief template and finalize fields
- Validate machine state JSON schema with real samples
- Confirm minimal event/thread/trajectory model
- Define and document epistemic layers in `STATE_SCHEMA.json`

## Normalization and compression (Phase 1: minimal fold)
- Define carryover thread detection
- Specify temporal reduction rules (carryover/new/resolved sets, age_days counters) for atoms and threads

## Normalization and compression (Phase 2: advanced)
- Define rules for event extraction and thread grouping
- Draft redundancy and failure-collapse heuristics
- Specify fold definitions and loss profiles (create `FOLDS.md`)
- Define SB atom/handle types (event_id, thread_id, atom_id, constraint_id, annotation_id) and allowed fields
- Define loss-profile metadata and expansion contract for SITREP lines (lossy index rules)
- Note: align compression diagnostics with SensibLaw work (entropy proxy + compression ratio guards, deterministic stability tests) to reuse methodology where applicable.

## Emission (early feedback loop)
- Produce a sample agent JSON state from real logs
- Define retrospective summary format for real data

## Integration roadmap (order by determinism)
- Git log ingestion adapter
- Calendar ingestion adapter
- Wazuh adapter (system lifecycle only)
- Prometheus adapter (summaries only; must not create/split activity_events)
- Input activity adapter (keyboard/mouse counts only)
- Window/app focus adapter (title hashed, no content)
- Browser usage adapter (domain hash + duration only)
- Antivirus/endpoint status adapter (counts only)
- Cloud audit adapters (Google Drive + MS365; read-only)
- Notes app metadata adapters (Obsidian + Evernote; file events only)
- Social feed adapters (Bluesky + other socials; meta-only)
- Android status adapter (ADB/Termux/Wazuh agent)
- Agent log adapters
- Tool execution envelope adapter (OpenClaw or similar; evidence-only)
- Smart home status adapter
- TIRC event adapter (trajectory/open/closed signals as SB events)
- SL constraint adapter (rule/constraint IDs with refs only)
- ITIR overlay adapter (annotation IDs, no content)
- Read-only query surface for agents (MCP or equivalent)

## Observability (Prometheus / Grafana)
- Define SB metrics surface (`/metrics`)
- Add a minimal HTTP metrics server for `sb.metrics.render_metrics`
- Specify allowed metric ingestion classes (numeric only)
- Add Prometheus adapter for time-window summaries
- Add determinism tests for adapter outputs (fixed inputs → stable JSONL)
- Define Grafana dashboards scoped to activity_event windows
- Grafana dashboard (current):
```
https://truenas.local:30037/d/truenas-overview4/truenas-scale-overview4
```
- Prometheus source: TrueNAS scrape with Graphite exporter metrics at `http://truenas.local:9109/metrics`
- InfluxDB (Home Assistant) is optional; requires confirmed credentials and live data
- Add guardrails: no semantic labels, no content promotion, and metrics must not create/split activity_events

## Observed capture / Recall-class substrate (optional)
- Define snapshot event schema for screen/app capture (append-only, content-addressed)
- Define `activity_event` schema and deterministic sessionization rules
- Implement SB sessionizer (deterministic, testable, golden snapshot fixtures)
- Emit SB activity_event ledger with provenance (algorithm, input hash, policy receipt)
- Add ITIR ingest adapter for SB activity_events (no re-segmentation)
- Document Wayland-first capture strategy with X11 legacy flag
- Specify OCR/embedding policy gates and redaction rules for sensitive apps
- Sketch timeline UI model: event cards + scrubber with event expansion
- Invariant: Recall-class capture is evidence-only and may not influence segmentation without SB policy

## External signal providers (reference index)
- Wazuh: lifecycle and failures; ignore alert semantics
- osquery: curated facts snapshots only
- Prometheus: numeric summaries only
- OpenRecall: visual evidence only
- Android: coarse status only

## Governance and safety
- Create ADRs directory and add ADRs for folds and OCR guardrails
- Define promotion rules and consent UX copy in a canonical policy doc
- Add tests/fixtures for “no silent promotion” behavior

## Open questions
- How to represent and score drift signals
- What level of agent autonomy defaults are safe
- Which export format is the canonical portable bundle
- How to represent execution envelopes in `STATE_SCHEMA.json` without granting authority
- How to surface epistemic modes without implying promotion or authority

## Sprint 4–6 (next arc)
- Sprint 4: run bad-data runs + manual brief review (drift counters done, bad-data tests added; manual review pending).
- Sprint 5: add expansion tests for Phase-2 compression and document loss profile usage.
- Sprint 6: add agent containment rules to docs and enforce ITIR overlay rejection on mutation attempts.

## Sprint 7–9 (next arc)
- Sprint 7: run bundle replay cross-host test (same outputs or explicit reject). (done)
- Sprint 8: implement carryover saturation label and inactivity stress runs. (done)
- Sprint 9: add metric-smuggling rejection tests (semantic labels) and document responses. (done)
- Sprint 9: add red-team tests for event injection, command/RCE payloads, and credential leakage. (done)
- Sprint 9: add tests for provenance laundering and systemic dependency failure. (done)
