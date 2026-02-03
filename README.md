# StatiBaker




Just old fashioned organisation.



We don’t tell you what to do, who to be, or how to optimise.



We help you remember what actually happened — so you can decide.


StatiBaker is a daily state distillation engine. It compiles human and machine state
into a single, coherent brief with traceability back to raw logs and actions.
This is not a chatbot. It is a state compiler.

## Core idea
StatiBaker ingests everything you generate or operate, then emits:
- What happened
- What matters today
- What is unresolved
- What agents should do next

## Inputs (state surface)
If it produces state, it can be baked.
- Human streams: journal, TODOs, notes, calendar, questions, sleep and activity
- System and agent streams: agent logs, tool outputs, git commits and diffs
- Environment: smart home status, alerts, deadlines, constraints

## Outputs (daily bake)
- Human-readable daily brief (morning)
- Machine-readable state for agents (JSON)
- Retrospective summary (evening)

## Key artifacts
- `BRIEF_TEMPLATE.md` (human brief and retrospective)
- `STATE_SCHEMA.json` (machine-readable state)
- `SAMPLE_STATE.json` (synthetic example)
- `INGESTION_FORMATS.md` (append-only log formats)
- `DESIGN.md` (architecture notes)
- `TODO.md` (plan and open questions)

## Design principles (anti-enshit)
These principles reflect the enshittification research notes in
`ITIR - anti-enshit.pdf`.
- User utility over extractive optimization
- Transparent, traceable state and summaries
- Data portability and interoperability
- Append-only logs, no memory rewriting

## Non-goals
- A generic conversational assistant
- Opaque personalization driven by engagement
- Rewriting history rather than summarizing it

## Current status
Docs-only foundation based on the proposal PDFs. No implementation yet.
