"""SB boundary invariants over opaque SL-origin canonical payloads.

These fixtures deliberately keep the current SL-provided legal-flavoured
canonical IDs/names so the boundary test exercises preservation of upstream
canonical outputs as-is.

They do not mean SB owns legal semantics. SB is only required to preserve or
reject the payload shape without mutating SL-origin segment/ID content.
"""

from copy import deepcopy

from sb.itir_ingest import validate_overlay


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
        "canonical_lexeme_ids": [
            "case:2003_hca_2",
            "sec:75",
            "para:v",
        ],
    }
    original = deepcopy(record)
    assert validate_overlay(record) == []
    assert record == original


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
