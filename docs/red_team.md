# Red Team Plan (Boundary & Safety)

## Purpose
Exercise SB against authority leaks, injection, and exfiltration attempts. Tests must
fail loudly and leave SB state unchanged.

## Core principle
A successful red-team test may result in SB refusing to operate.

## Threat model (in-scope)
- Injection of synthetic events into SB outputs.
- Re-segmentation attempts (mutating `activity_events`).
- Command/RCE attempts via logs, metrics, or adapters.
- Credential theft or leakage via summaries or query surfaces.
- Semantic smuggling through metrics or drift signals.
- Provenance laundering (forged outputs or manifest).
- Temporal confusion (ordering attacks, skew, duplicates).
- Reference explosion / denial of clarity (valid but useless floods).
- Systemic dependency failure (global upstream failure).
- Side-channel inference risks (counts/timing/bundle size).
- Query path traversal or arbitrary file reads via CLI.
- Vector-embedding leakage from hostile content.

## Out-of-scope (for now)
- Host OS hardening.
- Kernel-level attacks.
- Supply-chain compromise.
- Network DDoS or multi-tenant abuse.

## Denial-of-service & resource exhaustion
SB treats DoS as a risk of silent epistemic corruption, not an availability issue.
It must fail loudly, refuse work, or surface saturation signals.
Input amplification, query-surface abuse, bundle replay exhaustion, and observer flooding
are in-scope for explicit refusal or saturation markers.

## Test matrix (structure)
For each attack:
- Vector
- Preconditions
- Attempt
- Expected SB response
- Failure severity (reject / warn / document)
- Authority violated (time / provenance / meaning)

## Attack classes

### Map SB invariants → real-world failure modes
This mapping captures centralized-control-plane failures (Cloudflare/CrowdStrike-class
and ERP/POS-style outages) and the SB invariant that prevents similar propagation.
1. **SB owns activity_event boundaries** → prevents centralized time authority failures.
2. **External tools are non-authoritative observers** → prevents vendor semantics becoming truth.
3. **Pull-based ingestion only** → prevents fast blast-radius propagation.
4. **Append-only, auditable logs** → prevents silent retroactive rewrites.
5. **Determinism and replayability** → prevents non-reproducible recovery.
6. **Explicit gaps/absence** → prevents invented continuity.
7. **Loss profiles declared + expandable** → prevents compression-as-concealment.
8. **Verify-or-refuse bundles** → prevents partial or corrupted imports.

### 1) Event injection
Goal: prevent external inputs from adding arbitrary events or summaries.
- Attempt to inject extra events into `state.json` or `activity_ledger.json`.
- Expectation: validation rejects; no output overwrite.

### 2) Re-segmentation attack
Goal: prevent mutation of `activity_events` by non-SB actors.
- Inject `activity_events` into ITIR overlay input.
- Expectation: `validate_overlay` rejects.

### 3) Command injection / RCE
Goal: ensure adapters never execute content.
- Provide logs containing backticks, `$(...)`, `; rm -rf`, or shell payloads.
- Expectation: treated as inert text; no execution.

### 4) Credential theft / leakage
Goal: prevent secrets from appearing in SB outputs.
- Feed logs containing fake secrets (API keys, tokens).
- Expectation: secrets do not appear in `daily_brief.md`, `state.json`, or query output.
- If detection is needed, add explicit redaction policy (documented) — no implicit stripping.

### 5) Metric smuggling
Goal: prevent semantic labels or content in metrics.
- Provide Prometheus samples with labels like `summary="user is coding"`.
- Expectation: adapter strips labels; output is numeric summary only.

### 6) Drift override injection
Goal: keep drift separate and read-only.
- Attempt to place drift payload in `state.json` or query output.
- Expectation: hard reject; drift only in `drift.json`.

### 7) Query surface abuse
Goal: keep query outputs read-only and limited.
- Attempt path traversal or environment leaks.
- Expectation: queries only read explicit files and return JSON.

### 8) Provenance laundering
Goal: prevent forged outputs from appearing SB-authored.
- Modify `manifest.json` hashes.
- Expectation: `verify-bundle` fails loudly.

### 9) Temporal confusion attacks
Goal: prevent ordering manipulation.
- Duplicate IDs with different timestamps.
- Future-dated or far-past events.
- Overlapping activity event ranges.
- Expectation: explicit anomaly markers or rejection; no silent correction.

### 10) Reference explosion / denial of clarity
Goal: avoid silent corruption under floods.
- Millions of low-signal events, massive carryover sets.
- Expectation: explicit saturation flags, refusal or bounded processing.

### 11) Systemic dependency failure
Goal: upstream failure cannot corrupt time or meaning.
- Simulate global observer outage (Prometheus/Wazuh/Android all missing).
- Expectation: explicit absence, no invented continuity, no cross-day corruption.

### 12) Side-channel inference
Goal: document leakage, not fix it.
- Bundle size, counts, and timing may reveal patterns.
- Expectation: documented as residual risk, not silently expanded.

### 13) Vector embedding leakage (addendum)
Goal: prevent content or secrets from being embedded and later leaked via
nearest-neighbor retrieval.
- Attempt: feed adapters records containing secrets in fields that must be
  hashed or dropped, then run any downstream embedding job.
- Expectation: embeddings are never computed over raw content fields; content
  fields are absent in normalized outputs; embedding jobs (if present) must
  refuse records missing explicit consent + policy receipts.

## Considerations
- Red-team tests must be deterministic and non-destructive.
- Any mitigation must be documented before code changes.
- Fail closed: reject inputs rather than attempting to “fix” them.
- Tests must include event injection, command/RCE payloads, credential leakage, and path traversal.
- Tests should include provenance laundering and systemic dependency failure cases.
- Resource exhaustion should fail loudly or emit saturation markers, never partial truth.

## Addendum: Platform-wide security concerns

These are cross-cutting risks beyond adapter content leakage. They should be
modeled in red-team exercises and kept visible in governance docs.

### A) Identity correlation across contexts
Risk: hashed identifiers can still enable cross-domain linkage (e.g., same hash
across personal/work contexts). Mitigation: scoped salts per context and
explicit non-join boundaries.

### B) Consent drift
Risk: metadata collection expands beyond original consent scope. Mitigation:
policy receipts and capture scope IDs on all records.

### C) Supply-chain adapter risk
Risk: third-party adapters smuggle content or execute payloads. Mitigation:
adapter allowlist + red-team payload fixtures + deterministic JSONL outputs.

### D) Cloud audit privilege escalation
Risk: audit feeds expose more than intended (e.g., content titles). Mitigation:
strict field allowlists, hash-only identifiers, reject unknown fields.

### E) UI over-interpretation
Risk: UI implies judgment (importance, blame). Mitigation: conservation-only
surfaces, explicit lens naming, and refusal of semantic labels.

### F) Retention misconfiguration
Risk: infinite retention of meta signals enables long-horizon surveillance.
Mitigation: user-controlled retention + explicit deletion receipts.

### G) Cross-project exfiltration
Risk: adapters read files outside allowed roots. Mitigation: base-path guards
and explicit source registries.

### H) Embedding leakage (global)
Risk: any embedding on raw content reintroduces semantics. Mitigation: explicit
no-embed policy for meta-only streams; embed only consented artifacts.
