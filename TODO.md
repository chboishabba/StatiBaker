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

## Normalization and compression
- Define rules for event extraction and thread grouping
- Draft redundancy and failure-collapse heuristics
- Define carryover thread detection

## Emission
- Produce a sample daily brief from real logs
- Produce a sample agent JSON state from real logs
- Define retrospective summary format for real data

## Integration roadmap
- Calendar ingestion adapter
- Git log ingestion adapter
- Agent log adapters
- Smart home status adapter

## Open questions
- How to represent and score drift signals
- What level of agent autonomy defaults are safe
- Which export format is the canonical portable bundle
