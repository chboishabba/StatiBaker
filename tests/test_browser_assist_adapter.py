import json
from pathlib import Path

from adapters import browser_assist


def test_browser_assist_normalizes_preview_hashes_and_refs() -> None:
    row = browser_assist.normalize_record(
        {
            "ts": "2026-06-04T00:00:00Z",
            "session_id": "browser-assist-1",
            "task_label": "find the discussed item",
            "mode": "observe",
            "browser": "chrome",
            "page_url": "https://example.test/private?q=secret",
            "page_title": "Private Title",
            "text_preview": "alpha beta gamma delta",
            "structure_summary": {
                "heading_count": 2,
                "heading_text_hash": "sha256:headings",
                "heading_preview": ["A very private heading"],
                "link_count": 3,
                "form_control_count": 1,
                "landmark_roles": ["main", "navigation"],
            },
            "openrecall_entry_refs": ["openrecall.entry:7"],
            "playwright_snapshot_refs": ["snapshot-001.md"],
            "transcript_refs": ["transcript:1"],
            "pnf_candidates": [
                {
                    "predicate": "user_requested_find_on_page",
                    "structural_signature": "browser_assist_task_candidate",
                    "wrapper": {"evidence_only": True},
                }
            ],
            "task_identity_residual": "partial",
            "lifecycle_residual": "no_typed_meet",
        },
        "playwright_browser_assist",
        preview_chars=12,
    )

    assert row["signal"] == "browser_assist_activity"
    assert row["version"] == "browser_assist_activity_v1"
    assert row["page_url_hash"].startswith("sha256:")
    assert row["page_title_hash"].startswith("sha256:")
    assert "example.test" not in json.dumps(row)
    assert "Private Title" not in json.dumps(row)
    assert row["text_preview"] == "alpha beta…"
    assert row["text_hash"].startswith("sha256:")
    assert row["structure_summary"]["heading_count"] == 2
    assert row["structure_summary"]["heading_text_hash"] == "sha256:headings"
    assert row["structure_summary"]["link_count"] == 3
    assert row["openrecall_entry_refs"] == ["openrecall.entry:7"]
    assert row["pnf_candidates"][0]["predicate"] == "user_requested_find_on_page"
    assert row["task_identity_residual"] == "partial"
    assert row["lifecycle_residual"] == "no_typed_meet"
    assert row["kanban_projection_policy"] == "observer_only"
    assert row["non_authoritative"] is True


def test_browser_assist_metadata_only_suppresses_preview() -> None:
    row = browser_assist.normalize_record(
        {
            "ts": "2026-06-04T00:00:00Z",
            "session_id": "browser-assist-2",
            "text_preview": "visible page text",
            "storage_mode": "metadata_only",
        },
        "playwright_browser_assist",
    )

    assert row["storage_mode"] == "metadata_only"
    assert row["text_preview"] is None
    assert row["text_hash"].startswith("sha256:")


def test_browser_assist_cli_writes_jsonl(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "raw.jsonl"
    output = tmp_path / "normalized.jsonl"
    raw.write_text(
        '{"ts":"2026-06-04T00:00:00Z","session_id":"browser-assist-3","text_preview":"hello"}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["browser_assist.py", "--input", str(raw), "--output", str(output), "--metadata-only"],
    )
    browser_assist.main()

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["signal"] == "browser_assist_activity"
    assert rows[0]["text_preview"] is None
