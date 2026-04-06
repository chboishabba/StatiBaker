from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sb.observed_ingest import load_observed_events


def _seed_worldmonitor_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "worldmonitor"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.json").write_text(
        """
{"source": "sample-source", "url": "https://example.org", "extracted": "2026-03-08", "cities": ["Sample"], "note": "bridge test"}
""".strip(),
        encoding="utf-8",
    )
    return source_dir


def _seed_worldmonitor_repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "worldmonitor-repo"
    data_dir = repo_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "package.json").write_text('{"name":"world-monitor-test","private":true}', encoding="utf-8")
    (data_dir / "sample.json").write_text(
        """
{"source": "sample-source", "url": "https://example.org", "extracted": "2026-03-08", "cities": ["Sample"], "note": "default source path test"}
""".strip(),
        encoding="utf-8",
    )
    return repo_dir


def _run_script(cmd: list[str], cwd: Path) -> dict[str, object]:
    return json.loads(
        subprocess.run(
            [*cmd],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


def test_worldmonitor_bridge_exports_observed_signals(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = _seed_worldmonitor_dir(tmp_path)
    itir_db = tmp_path / "itir.sqlite"
    wm_logs = tmp_path / "runs" / "2026-03-08" / "logs" / "worldmonitor"
    wm_output = wm_logs / "2026-03-08.jsonl"

    _run_script(
        [
            sys.executable,
            "SensibLaw/scripts/import_observation.py",
            "--lane",
            "worldmonitor",
            "--source-path",
            str(source_dir),
            "--import-run-id",
            "bridge-worldmonitor-v1",
            "--itir-db-path",
            str(itir_db),
        ],
        cwd=repo_root,
    )

    _run_script(
        [
            sys.executable,
            "StatiBaker/scripts/export_worldmonitor_observed.py",
            "--itir-db-path",
            str(itir_db),
            "--output",
            str(wm_output),
            "--import-run-id",
            "bridge-worldmonitor-v1",
            "--source",
            "bridge_worldmonitor_test",
        ],
        cwd=repo_root,
    )

    events = load_observed_events(tmp_path / "runs")
    assert events
    assert any(event["text"].startswith("signal=worldmonitor_capture") for event in events)
    worldmonitor_events = [event for event in events if event["meta"].get("source_kind") == "metadata"]
    assert worldmonitor_events
    assert worldmonitor_events[0]["meta"]["capture_id_hash"].startswith("sha256:")
    assert worldmonitor_events[0]["meta"]["source_file_hash"].startswith("sha256:")


def test_worldmonitor_bridge_wrapper_runs_sl_then_sb_then_sl(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = _seed_worldmonitor_dir(tmp_path)
    itir_db = tmp_path / "itir.sqlite"
    runs_root = tmp_path / "runs"

    payload = _run_script(
        [
            sys.executable,
            "StatiBaker/scripts/run_worldmonitor_bridge.py",
            "--date",
            "2026-03-08",
            "--repo-path",
            str(repo_root),
            "--source-path",
            str(source_dir),
            "--itir-db-path",
            str(itir_db),
            "--sb-runs-root",
            str(runs_root),
            "--import-run-id",
            "bridge-worldmonitor-roundtrip-v1",
        ],
        cwd=repo_root,
    )

    assert payload["ok"] is True
    assert payload["importRunId"] == "bridge-worldmonitor-roundtrip-v1"
    assert payload["importSummary"]["ok"] is True
    assert payload["exportSummary"]["ok"] is True
    assert payload["exportSummary"]["exportCount"] == 2
    assert payload["slSummary"]["ok"] is True
    assert payload["slChronology"]["ok"] is True
    assert payload["slSummary"]["summary"]["captureCount"] == 2
    assert payload["slChronology"]["chronology"]["chronologyCount"] == 2
    assert Path(payload["worldmonitorObservedPath"]).exists()
    assert Path(payload["slSummaryPath"]).exists()
    assert Path(payload["slChronologyPath"]).exists()
    chronology_rows = payload["slChronology"]["chronology"]["chronology"]
    assert chronology_rows[0]["order"] == 1
    assert chronology_rows[0]["time_start"] <= chronology_rows[-1]["time_start"]
    assert all("text" not in row for row in chronology_rows)

    events = load_observed_events(runs_root)
    assert any(event["text"].startswith("signal=worldmonitor_capture") for event in events)


def test_worldmonitor_bridge_wrapper_defaults_to_worldmonitor_repo_data_dir(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    wm_repo = _seed_worldmonitor_repo(tmp_path)
    itir_db = tmp_path / "itir.sqlite"
    runs_root = tmp_path / "runs"

    payload = _run_script(
        [
            sys.executable,
            "StatiBaker/scripts/run_worldmonitor_bridge.py",
            "--date",
            "2026-03-08",
            "--repo-path",
            str(repo_root),
            "--worldmonitor-repo-path",
            str(wm_repo),
            "--itir-db-path",
            str(itir_db),
            "--sb-runs-root",
            str(runs_root),
            "--import-run-id",
            "bridge-worldmonitor-default-source-v1",
        ],
        cwd=repo_root,
    )

    assert payload["ok"] is True
    assert payload["worldmonitorRepoPath"] == str(wm_repo.resolve())
    assert payload["sourcePath"] == str((wm_repo / "data").resolve())
    assert payload["exportSummary"]["exportCount"] == 2
    assert payload["slSummary"]["summary"]["captureCount"] == 2
    assert Path(payload["slChronologyPath"]).exists()


def test_worldmonitor_bridge_wrapper_reuses_latest_populated_import_run_when_source_is_unchanged(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = _seed_worldmonitor_dir(tmp_path)
    itir_db = tmp_path / "itir.sqlite"
    runs_root = tmp_path / "runs"

    first_payload = _run_script(
        [
            sys.executable,
            "StatiBaker/scripts/run_worldmonitor_bridge.py",
            "--date",
            "2026-03-08",
            "--repo-path",
            str(repo_root),
            "--source-path",
            str(source_dir),
            "--itir-db-path",
            str(itir_db),
            "--sb-runs-root",
            str(runs_root),
        ],
        cwd=repo_root,
    )

    second_payload = _run_script(
        [
            sys.executable,
            "StatiBaker/scripts/run_worldmonitor_bridge.py",
            "--date",
            "2026-03-08",
            "--repo-path",
            str(repo_root),
            "--source-path",
            str(source_dir),
            "--itir-db-path",
            str(itir_db),
            "--sb-runs-root",
            str(runs_root),
        ],
        cwd=repo_root,
    )

    assert first_payload["slSummary"]["summary"]["captureCount"] == 2
    assert second_payload["importSummary"]["importedCaptureCount"] == 0
    assert second_payload["exportSummary"]["exportCount"] == 2
    assert second_payload["slSummary"]["summary"]["captureCount"] == 2
    assert second_payload["reusedExistingImportRunId"] == first_payload["importRunId"]
