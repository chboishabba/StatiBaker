# ADR 0003: External Signal Condensers Are Non-Authoritative

Date: 2026-02-05
Status: Accepted

## Context

SB ingests signals from external tools (e.g., Wazuh, osquery, Prometheus) to
explain conditions and support deterministic segmentation. These tools provide
filtered, opinionated outputs that can drift into security or operational
semantics if adopted as truth.

## Decision

1. Treat external signal condensers as **non-authoritative observers**.
2. SB may ingest only **curated facts or summaries** (no raw logs, no free text).
3. Alerts, severities, and threat labels are **not** adopted as meaning.
4. External signals may influence **confidence** and **explanation** only.
5. Activity segmentation remains **SB authority**; external signals may not
   create or split activity_events.

## Rationale

- Prevents security or compliance semantics from contaminating SB state.
- Preserves the time/meaning split across SB and ITIR.
- Keeps provenance auditable and deterministic across replays.

## Consequences

- Adapters must strip tool-specific semantics (CVE, alert classes, etc.).
- SB documentation must describe accepted fields and ignore lists.
- Tool outputs are stored as append-only observations, not facts of meaning.

## Alternatives Considered

- **Inherit tool semantics**: faster integration, but violates authority split.
- **Raw log ingestion**: higher fidelity, but noisy and non-deterministic.
