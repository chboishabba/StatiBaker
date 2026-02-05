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

## Immediate next (authority guardrails)
- Add a "core questions + context prosthesis" section to `CONTEXT.md` (time vs meaning split and SB-only invariants)
- Add ADR: external signal condensers (Wazuh, osquery) are non-authoritative observers

## Define intent and scope
- Review daily brief template and finalize fields
- Validate machine state JSON schema with real samples
- Confirm minimal event/thread/trajectory model
- Define and document epistemic layers in `STATE_SCHEMA.json`

## Normalization and compression (Phase 1: minimal fold)
- Define carryover thread detection
- Specify temporal reduction rules (carryover/new/resolved sets, age_days counters) for atoms and threads
- Define rolling window policy for carryover and unresolved counts (e.g., 7/14/30-day windows)
- Add guard tests: SB must not re-tokenize, promote phrases, or summarize artifact content

## Normalization and compression (Phase 2: advanced)
- Define rules for event extraction and thread grouping
- Draft redundancy and failure-collapse heuristics
- Specify fold definitions and loss profiles (create `FOLDS.md`)
- Define SB atom/handle types (event_id, thread_id, atom_id, constraint_id, annotation_id) and allowed fields
- Define loss-profile metadata and expansion contract for SITREP lines (lossy index rules)
- Note: align compression diagnostics with SensibLaw work (entropy proxy + compression ratio guards, deterministic stability tests) to reuse methodology where applicable.

## Emission (early feedback loop)
- Produce a sample daily brief from real logs
- Produce a sample agent JSON state from real logs
- Define retrospective summary format for real data

## Integration roadmap (order by determinism)
- Git log ingestion adapter
- Calendar ingestion adapter
- Wazuh adapter (system lifecycle only)
- Prometheus adapter (summaries only; must not create/split activity_events)
- Android status adapter (ADB/Termux/Wazuh agent)
- Agent log adapters
- Smart home status adapter
- TIRC event adapter (trajectory/open/closed signals as SB events)
- SL constraint adapter (rule/constraint IDs with refs only)
- ITIR overlay adapter (annotation IDs, no content)
- Read-only query surface for agents (MCP or equivalent)

## Observability (Prometheus / Grafana)
- Define SB metrics surface (`/metrics`)
- Specify allowed metric ingestion classes (numeric only)
- Add Prometheus adapter for time-window summaries
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
