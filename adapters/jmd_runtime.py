"""Reference-only JMD runtime overlay adapter for StatiBaker."""

from __future__ import annotations

from typing import Any, Mapping


def receipt_to_overlay_record(
    *,
    receipt: Mapping[str, Any],
    activity_event_id: str,
    annotation_id: str,
    state_date: str,
    provenance: Mapping[str, Any],
    status: str | None = None,
    confidence: str | None = None,
) -> dict[str, Any]:
    return {
        "activity_event_id": str(activity_event_id),
        "annotation_id": str(annotation_id),
        "provenance": dict(provenance),
        "state_date": str(state_date),
        "observer_kind": "jmd_runtime_v1",
        "status": status,
        "confidence": confidence,
        "receipt_refs": [
            {
                "receipt_id": receipt["receipt_id"],
                "provider_kind": receipt["provider_kind"],
                "provider_name": receipt["provider_name"],
            }
        ],
        "object_refs": list(receipt.get("object_refs") or []),
        "graph_refs": list(receipt.get("graph_refs") or []),
    }
