# Phase 0: Docs Foundation

## Objective
Consolidate repo context into a single authoritative README, move OCR/screen
capture guardrails into a dedicated safety doc, and align DESIGN/TODO/context
summaries with the new invariants.

## Scope
- README consolidation (single authoritative narrative)
- OCR/screen capture safety doc
- Design note updates for epistemic layers
- TODO alignment
- Compactified context refresh

## Success criteria
- README no longer contains multiple "takes"
- OCR guardrails live in a dedicated doc and are referenced from README/DESIGN
- TODO reflects new governance and fold work
- Compactified context captures new invariants

## Constraints
- Docs-only: no implementation changes
- Append-only ethos preserved in descriptions
- Explicit promotion rule for derived artifacts

## Assumptions
- Screen capture and OCR are supported as evidence, not memory
- Promotion is the only path from artifact to declared state

## Open questions
- Where ADRs should live and how they are named
- How to represent epistemic layers in `STATE_SCHEMA.json`

## Next action
Draft ADRs for folds and OCR guardrails.
