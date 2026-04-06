from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_ROOT = ROOT.parent
SENSIBLAW_ROOT = SUITE_ROOT / "SensibLaw"
SENSIBLAW_SRC = SENSIBLAW_ROOT / "src"

if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))
if str(SENSIBLAW_SRC) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb.itir_ingest import validate_overlay  # noqa: E402
from src.policy.sl_to_sb_observer import build_sl_to_sb_iso_run_observer_payload  # noqa: E402


def test_sl_iso_run_observer_payload_validates_at_sb_boundary() -> None:
    payload = build_sl_to_sb_iso_run_observer_payload(
        suite_normalized_artifact={
            "artifact_id": "sl.normative_policy_extract:iso-demo",
            "artifact_role": "derived_product",
            "context_envelope_ref": {"envelope_id": "semantic:iso-demo"},
            "provenance_anchor": {"source_artifact_id": "semantic:iso-demo"},
            "lineage": {"upstream_artifact_ids": ["text:iso42001:clause-5.2"]},
            "follow_obligation": {
                "trigger": "open_iso_follow_pressure",
                "scope": "bounded follow on ISO clause coverage",
                "stop_condition": "follow pressure cleared or explicitly held",
            },
            "unresolved_pressure_status": "follow_needed",
        },
        state_date="2026-04-06",
        casey_observer_refs=[
            {"operation_id": "op:casey:1", "build_id": "build:casey:1", "receipt_hash": "a" * 64}
        ],
    )
    assert validate_overlay(payload) == []
    assert payload["observer_kind"] == "sensiblaw_iso_run_v1"
