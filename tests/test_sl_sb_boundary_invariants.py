"""SB boundary invariants over opaque SL-origin canonical payloads.

These fixtures deliberately keep the current SL-provided legal-flavoured
canonical IDs/names so the boundary test exercises preservation of upstream
canonical outputs as-is.

They do not mean SB owns legal semantics. SB is only required to preserve or
reject the payload shape without mutating SL-origin segment/ID content.
"""

from copy import deepcopy
import itertools
import sys
from pathlib import Path

from sb.itir_ingest import validate_overlay

ROOT = Path(__file__).resolve().parents[1]
SUITE_ROOT = ROOT.parent
SENSIBLAW_ROOT = SUITE_ROOT / "SensibLaw"
SENSIBLAW_SRC = SUITE_ROOT / "SensibLaw" / "src"

if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))
if str(SENSIBLAW_SRC) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_SRC))

from sensiblaw.interfaces.shared_reducer import (  # noqa: E402
    collect_canonical_lexeme_refs,
    get_canonical_tokenizer_profile_receipt,
)


def test_segmentation_preservation_allows_canonical_segment_fields_without_mutation() -> None:
    record = {
        "activity_event_id": "ae:mabo:holding:1",
        "annotation_id": "ann:mabo:segment",
        "provenance": {
            "source": "SensibLaw",
            "fixture": "Mabo [No 2] - [1992] HCA 23",
            "fixture_role": "sl_cross_test_input_only",
            "segment_id": "seg:mabo:holding:1",
        },
        "state_date": "2026-03-07",
        "canonical_segment_id": "seg:mabo:holding:1",
        "canonical_anchor_span_id": "span:mabo:holding:1",
        "segment_start": 1024,
        "segment_end": 1168,
    }
    original = deepcopy(record)
    assert validate_overlay(record) == []
    assert record == original


def test_canonical_id_preservation_allows_shared_sl_ids_without_mutation() -> None:
    record = {
        "activity_event_id": "ae:plaintiff_s157:review:1",
        "annotation_id": "ann:plaintiff_s157:canonical",
        "provenance": {
            "source": "SensibLaw",
            "fixture": "Plaintiff S157/2002 v Commonwealth",
            "fixture_role": "sl_cross_test_input_only",
        },
        "state_date": "2026-03-07",
        "canonical_event_id": "ev:plaintiff_s157:review:1",
        "canonical_lexeme_refs": [
            {"occurrence_id": "occ:1", "kind": "case_ref", "span_start": 0, "span_end": 4},
            {"occurrence_id": "occ:2", "kind": "section_ref", "span_start": 5, "span_end": 7},
            {"occurrence_id": "occ:3", "kind": "paragraph_ref", "span_start": 8, "span_end": 9},
        ],
    }
    original = deepcopy(record)
    assert validate_overlay(record) == []
    assert record == original


def test_shared_reducer_adapter_can_supply_opaque_sl_origin_ids_to_sb() -> None:
    text = "Civil Liability Act 2002 (NSW) s 5B applies here."
    canonical_refs = [ref for ref in collect_canonical_lexeme_refs(text) if str(ref["kind"]).endswith("_ref")]
    assert canonical_refs

    record = {
        "activity_event_id": "ae:civil_liability_act:review:1",
        "annotation_id": "ann:civil_liability_act:canonical",
        "provenance": {
            "source": "SensibLaw",
            "fixture": "Civil Liability Act 2002 (NSW) s 5B",
            "fixture_role": "sl_shared_reducer_input_only",
            "tokenizer_profile_receipt": get_canonical_tokenizer_profile_receipt(),
        },
        "state_date": "2026-03-15",
        "canonical_event_id": "ev:civil_liability_act:review:1",
        "canonical_lexeme_refs": canonical_refs,
    }
    original = deepcopy(record)
    assert validate_overlay(record) == []
    assert record == original


def test_sb_runtime_code_does_not_import_sl_tokenizer_internals_directly() -> None:
    forbidden = (
        "src.text.lexeme_index",
        "src.text.deterministic_legal_tokenizer",
    )
    offender_paths: list[str] = []
    for path in itertools.chain(
        (ROOT / "sb").rglob("*.py"),
        (ROOT / "scripts").rglob("*.py"),
    ):
        text = path.read_text(encoding="utf-8")
        if any(forbidden_import in text for forbidden_import in forbidden):
            offender_paths.append(str(path.relative_to(ROOT)))
    assert offender_paths == []


def test_no_summary_injection_rejects_synthetic_summary_fields() -> None:
    record = {
        "activity_event_id": "ae:house_v_king:summary:1",
        "annotation_id": "ann:house_v_king:summary",
        "provenance": {
            "source": "SensibLaw",
            "fixture": "House v The King",
            "fixture_role": "sl_cross_test_input_only",
        },
        "state_date": "2026-03-07",
        "summary_text": "Synthetic summary that should never enter the canonical evidence lane.",
    }
    errors = validate_overlay(record)
    assert errors
    assert any("summary_text" in error for error in errors)


def test_mission_observer_overlay_preserves_reference_only_payload() -> None:
    record = {
        "activity_event_id": "ae:slack:followup:1",
        "annotation_id": "obs:mission:followup:1",
        "provenance": {
            "source": "SensibLaw",
            "fixture_role": "mission_overlay_input_only",
        },
        "sb_state_id": "itir:mission:fixture",
        "observer_kind": "itir_mission_graph_v1",
        "status": "linked",
        "confidence": "medium",
        "mission_refs": [
            {
                "mission_id": "mission:demo:notification_routing_feature",
                "node_kind": "task",
                "topic_label": "notification routing feature",
                "ref_type": "followup_resolution",
            }
        ],
        "evidence_refs": [
            {
                "event_id": "ae:slack:followup:1",
                "source_id": "slack-thread-1",
                "ref_kind": "followup_message",
            }
        ],
    }
    original = deepcopy(record)
    assert validate_overlay(record) == []
    assert record == original
