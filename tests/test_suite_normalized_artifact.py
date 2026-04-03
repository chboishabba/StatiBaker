from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema

from sb.suite_normalized_artifact import build_compiled_state_normalized_artifact


ROOT = Path("/home/c/Documents/code/ITIR-suite")
SB_ROOT = ROOT / "StatiBaker"
ROOT_SCHEMA_PATH = ROOT / "schemas" / "itir.normalized.artifact.v1.schema.json"


def _validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads(ROOT_SCHEMA_PATH.read_text(encoding="utf-8")))


def test_compiled_state_normalized_artifact_validates() -> None:
    state = {
        "date": "2026-04-02",
        "day_state": "active",
        "human_energy": "medium",
        "priorities": ["Review state output"],
        "alerts": [],
        "open_questions": [],
        "blocked_tasks": [],
        "events": [{"id": "e1"}],
        "sources": [{"kind": "git", "uri": "/tmp/git.jsonl"}],
    }

    payload = build_compiled_state_normalized_artifact(state, artifact_ref="state.json")
    _validator().validate(payload)
    assert payload["artifact_role"] == "compiled_state"
    assert payload["authority"]["authority_class"] == "state"
    assert payload["authority"]["derived"] is False
    assert payload["unresolved_pressure_status"] == "none"
    assert "statiBaker.outputs:2026-04-02:state.json" in payload["lineage"]["upstream_artifact_ids"]
    assert payload["context_envelope_ref"]["envelope_ref"] == "context_envelope.json"


def test_bundle_export_writes_suite_normalized_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = tmp_path / "run"
        out_dir = tmp_path / "bundle"
        run_dir.mkdir(parents=True)

        (run_dir / "state.json").write_text(
            json.dumps(
                {
                    "date": "2026-04-02",
                    "day_state": "active",
                    "human_energy": "medium",
                    "priorities": ["Bundle export"],
                    "alerts": ["attention needed"],
                    "open_questions": [],
                    "blocked_tasks": [],
                    "sources": [{"kind": "git", "uri": "/tmp/git.jsonl"}],
                    "events": [],
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "drift.json").write_text("{}", encoding="utf-8")
        (run_dir / "activity_ledger.json").write_text("[]", encoding="utf-8")
        (run_dir / "sessionizer_runtime_ms.txt").write_text("0\n", encoding="utf-8")
        (run_dir / "daily_brief.md").write_text("brief\n", encoding="utf-8")
        (run_dir / "retrospective.md").write_text("retro\n", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(SB_ROOT)
        subprocess.check_call(
            [
                sys.executable,
                str(SB_ROOT / "scripts" / "bundle_export.py"),
                "--run-dir",
                str(run_dir),
                "--out",
                str(out_dir),
                "--sb-version",
                "test",
            ],
            env=env,
            cwd=str(SB_ROOT),
        )

        normalized_path = out_dir / "suite_normalized_artifact.json"
        assert normalized_path.exists()
        payload = json.loads(normalized_path.read_text(encoding="utf-8"))
        _validator().validate(payload)
        assert payload["unresolved_pressure_status"] == "follow_needed"

        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        assert "suite_normalized_artifact.json" in manifest["files"]


def test_compiled_state_normalized_artifact_accepts_custom_context_envelope() -> None:
    state = {
        "date": "2026-05-01",
        "day_state": "active",
        "human_energy": "medium",
        "priorities": [],
        "alerts": [],
        "open_questions": [],
        "blocked_tasks": [],
        "events": [],
        "sources": [],
    }
    payload = build_compiled_state_normalized_artifact(
        state,
        artifact_ref="state.json",
        context_envelope_ref="exports/context-envelope.json",
    )
    assert payload["context_envelope_ref"]["envelope_ref"] == "exports/context-envelope.json"
