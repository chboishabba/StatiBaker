# TODO

## Completed (2026-02-03)
- Drafted human daily brief and retrospective templates (`BRIEF_TEMPLATE.md`)
- Defined machine state JSON schema (`STATE_SCHEMA.json`)
- Created synthetic sample state (`SAMPLE_STATE.json`)
- Specified append-only ingestion formats (`INGESTION_FORMATS.md`)

## Define intent and scope
- Review daily brief template and finalize fields
- Validate machine state JSON schema with real samples
- Confirm minimal event/thread/trajectory model
- Define and document epistemic layers in `STATE_SCHEMA.json`

## Normalization and compression
- Define rules for event extraction and thread grouping
- Draft redundancy and failure-collapse heuristics
- Define carryover thread detection
- Specify fold definitions and loss profiles (create `FOLDS.md`)

## Emission
- Produce a sample daily brief from real logs
- Produce a sample agent JSON state from real logs
- Define retrospective summary format for real data

## Integration roadmap
- Calendar ingestion adapter
- Git log ingestion adapter
- Agent log adapters
- Smart home status adapter

## Governance and safety
- Create ADRs directory and add ADRs for folds and OCR guardrails
- Define promotion rules and consent UX copy in a canonical policy doc
- Add tests/fixtures for “no silent promotion” behavior

## Open questions
- How to represent and score drift signals
- What level of agent autonomy defaults are safe
- Which export format is the canonical portable bundle
