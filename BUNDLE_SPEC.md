# SB Bundle Spec

## Layout
```
sb-bundle/
  state.json
  suite_normalized_artifact.json
  drift.json
  activity_ledger.json
  sessionizer_runtime_ms.txt
  daily_brief.md
  retrospective.md
  manifest.json
```

## Manifest fields
- `sb_version`
- `created_at`
- `policy_receipts`
- `files`: map of filename → sha256

## Rules
- Bundles are read-only.
- `suite_normalized_artifact.json` is the suite-level normalized wrapper for
  the compiled `state.json` output; it must stay aligned to the root
  `itir.normalized.artifact.v1` contract.
- `verify-bundle` must recompute drift from `state.json` and compare `drift.json`.
- Any hash mismatch or drift mismatch is a hard failure.
