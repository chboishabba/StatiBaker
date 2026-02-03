# OCR and Screen Capture Safety

This document defines how screen capture and OCR can exist in StatiBaker without
creating Recall-style failure modes.

## Canonical rules

- **Automatic extraction may occur. Automatic belief may not.**
- **Derived artifacts never become state without an explicit act.**
- **Screens are evidence. Events are truth.**

## The core distinction

Copilot Recall treats pixels as memory.
StatiBaker treats pixels as evidence.

StatiBaker does not infer intent, and it does not promote observations to state
without explicit, inspectable promotion.

## Trust lattice

1. **Declared state**
   Tasks, notes, logs, commits. Authoritative.

2. **Observed state**
   Screens, sensors, passive signals. Evidentiary.

3. **Derived artifacts**
   OCR, transcripts, transforms. Provisional.

4. **Signals**
   Classifiers, hints, flags. Non-semantic.

Only **declared state** enters folds by default.

## Screen capture placement

Screen capture is **low-trust observational state**.
It exists to support expansion and verification when other logs are missing.
It does not enter summaries without promotion.

## OCR guardrails

OCR is a **derived artifact**, not an event.

- OCR results are quarantined by default.
- OCR results do not enter folds or summaries.
- OCR results never alter “what happened.”
- OCR results can only affect “what matters” via disclosure signals.
- All OCR activity must be visible and reversible.

### Promotion rule

OCR text becomes state only via explicit promotion:

- Human promotion ("turn this into a task")
- Named, opt-in policy promotion (explicit rules)

Promotion creates a **new declared event** referencing the artifact.

## Opportunistic OCR

OCR may run automatically when a capture occurs if and only if:

- results are quarantined
- results are non-indexed by default
- results are excluded from folds and summaries
- results are user-visible and reversible

This is **precomputation**, not memory.

## Always-on OCR (policy-scoped)

Allowed only with explicit, named policies that are:

- inspectable
- reversible
- scoped
- logged as state changes

## Disclosure vs interpretation

OCR may surface disclosure signals (e.g., "a capture contains banking content")
that affect what matters today as a hygiene concern.

OCR may not state semantic conclusions (e.g., "you reviewed a bank statement").

## Litmus test

If an OCR result is wrong, misleading, or sensitive:

- Can the user notice it?
- Can the user undo it?

If the answer is no, the change is invalid.
