# ADR 0002: Recall-class Capture + Activity Events

Date: 2026-02-05
Status: Accepted

## Context

SB may adopt a Recall/OpenRecall-class substrate for observed capture (screens,
app context, optional OCR). This introduces privacy, determinism, and consent
risks if it is treated as "memory" rather than observed evidence. SB must
preserve its anti-enshittification invariants and avoid silent promotion of
derived artifacts.

## Decision

1. Treat Recall-class capture as **observed evidence** only.
2. Use **Wayland-first** capture (PipeWire + xdg-desktop-portal) with an
   explicit X11 legacy flag as fallback.
3. Require **policy-gated extraction**:
   - No silent OCR.
   - Redaction for sensitive apps/fields before any embedding.
4. Store **append-only snapshots** with content-addressed payloads.
5. Introduce a deterministic **activity_event** layer that groups snapshots into
   timeline segments ("then this → then this") without contaminating raw logs.
6. **Authority split**: SB decides activity_events; ITIR consumes them; OpenRecall
   renders snapshots and timelines without semantic authority.

## Rationale

- Wayland-first capture aligns with consent and least-privilege norms.
- Policy gates prevent accidental surveillance behaviors.
- Append-only snapshots preserve auditability and replay.
- Activity events provide higher-level timeline utility while remaining
  recomputable and non-authoritative.

## Consequences

- Capture pipelines must surface explicit consent indicators.
- OCR and embeddings are optional derived stores, never authoritative state.
- Sessionization rules must be deterministic and reversible.
- UI can render event cards while keeping raw snapshots reachable.

## Alternatives Considered

- **X11-only capture**: faster, but insecure and future-hostile.
- **Implicit OCR**: higher recall, but violates consent and trust boundaries.
- **LLM-generated activity summaries**: useful, but non-deterministic and
  contaminating without strict provenance controls.

## Guarantees (Non-Negotiable)

- No silent OCR.
- No hidden context injection.
- Expansion is always cheaper than summarization.
- Raw events are always reachable.
