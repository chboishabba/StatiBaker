#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date as date_cls
from pathlib import Path
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


def _run_json_command(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_worldmonitor_repo_path(repo_path: Path, configured: Path | None) -> Path:
    candidate = configured if configured is not None else repo_path.parent / "worldmonitor"
    return candidate.resolve()


def _resolve_worldmonitor_source_path(repo_path: Path, wm_repo_path: Path, configured: Path | None) -> Path:
    candidate = configured if configured is not None else wm_repo_path / "data"
    return candidate.resolve()


def _run_checked(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _find_latest_populated_import_run(itir_db_path: Path, *, source_path: Path) -> str | None:
    conn = sqlite3.connect(str(itir_db_path))
    try:
        row = conn.execute(
            """
            SELECT import_run_id
            FROM worldmonitor_import_runs
            WHERE source_path = ?
              AND imported_capture_count > 0
            ORDER BY imported_at DESC, import_run_id DESC
            LIMIT 1
            """,
            (str(source_path),),
        ).fetchone()
    finally:
        conn.close()
    return None if row is None else str(row[0] or "").strip() or None


def _bootstrap_worldmonitor(wm_repo_path: Path) -> dict[str, Any]:
    package_json = wm_repo_path / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"WorldMonitor repo missing package.json: {package_json}")
    completed = _run_checked(["npm", "install"], cwd=wm_repo_path)
    return {
        "ok": True,
        "repoPath": str(wm_repo_path),
        "stdoutTail": completed.stdout.splitlines()[-20:],
        "stderrTail": completed.stderr.splitlines()[-20:],
    }


def _smoke_worldmonitor_dev(wm_repo_path: Path, *, port: int, timeout_seconds: int = 45) -> dict[str, Any]:
    cmd = ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(
        cmd,
        cwd=wm_repo_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    start = time.monotonic()
    try:
        while time.monotonic() - start < timeout_seconds:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                raise RuntimeError(
                    "WorldMonitor dev server exited before becoming ready\n"
                    f"stdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )
            try:
                with urlopen(url, timeout=2) as response:
                    status = int(getattr(response, "status", 0) or 0)
                    if 200 <= status < 500:
                        return {
                            "ok": True,
                            "repoPath": str(wm_repo_path),
                            "url": url,
                            "port": port,
                            "status": status,
                        }
            except URLError:
                time.sleep(1)
        raise TimeoutError(f"Timed out waiting for WorldMonitor dev server at {url}")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded WorldMonitor bridge: SL import, SB export/ingest, and SL summary readout."
    )
    parser.add_argument("--date", default=date_cls.today().isoformat(), help="Run date (YYYY-MM-DD)")
    parser.add_argument("--repo-path", type=Path, default=Path(__file__).resolve().parents[2], help="Repo root path")
    parser.add_argument(
        "--worldmonitor-repo-path",
        type=Path,
        default=None,
        help="Path to the sibling WorldMonitor repo (defaults to ../worldmonitor from repo root)",
    )
    parser.add_argument(
        "--source-path",
        type=Path,
        default=None,
        help="WorldMonitor source export path (defaults to <worldmonitor-repo>/data)",
    )
    parser.add_argument(
        "--itir-db-path",
        type=Path,
        default=Path(".cache_local/itir.sqlite"),
        help="Path to the canonical ITIR SQLite DB",
    )
    parser.add_argument(
        "--sb-runs-root",
        type=Path,
        default=None,
        help="Override StatiBaker runs root (defaults to SB_RUNS_ROOT or StatiBaker/runs_local)",
    )
    parser.add_argument("--import-run-id", default=None, help="Optional stable import run id")
    parser.add_argument("--limit", type=int, default=None, help="Optional max source rows/files to import")
    parser.add_argument("--source", default="worldmonitor_capture_bridge", help="Provenance source label")
    parser.add_argument(
        "--captured-date",
        default=None,
        help="Optional WorldMonitor captured_date filter for SB export (defaults to the whole import run)",
    )
    parser.add_argument(
        "--bootstrap-worldmonitor",
        action="store_true",
        help="Run `npm install` in the WorldMonitor repo before bridge ingest",
    )
    parser.add_argument(
        "--smoke-worldmonitor-dev",
        action="store_true",
        help="Start WorldMonitor locally, wait for the dev server to answer, then stop it before ingest",
    )
    parser.add_argument(
        "--worldmonitor-dev-port",
        type=int,
        default=4173,
        help="Port used for the optional WorldMonitor dev smoke check",
    )
    args = parser.parse_args(argv)

    repo_path = args.repo_path.resolve()
    wm_repo_path = _resolve_worldmonitor_repo_path(repo_path, args.worldmonitor_repo_path)
    source_path = _resolve_worldmonitor_source_path(repo_path, wm_repo_path, args.source_path)
    sb_root = Path(__file__).resolve().parents[1]
    runs_root = (
        args.sb_runs_root.resolve()
        if args.sb_runs_root is not None
        else Path(os.environ.get("SB_RUNS_ROOT", str(sb_root / "runs_local"))).resolve()
    )
    run_dir = runs_root / args.date
    wm_output_path = run_dir / "logs" / "worldmonitor" / f"{args.date}.jsonl"
    sl_summary_path = run_dir / "outputs" / "worldmonitor" / "sl_summary.json"
    sl_chronology_path = run_dir / "outputs" / "worldmonitor" / "sl_chronology.json"
    itir_db_path = args.itir_db_path.resolve()
    import_script = repo_path / "SensibLaw" / "scripts" / "import_observation.py"
    export_script = sb_root / "scripts" / "export_worldmonitor_observed.py"
    run_day_script = sb_root / "scripts" / "run_day.sh"
    query_script = repo_path / "SensibLaw" / "scripts" / "query_worldmonitor_import.py"
    bootstrap_summary: dict[str, Any] | None = None
    dev_smoke_summary: dict[str, Any] | None = None

    if args.bootstrap_worldmonitor:
        bootstrap_summary = _bootstrap_worldmonitor(wm_repo_path)
    if args.smoke_worldmonitor_dev:
        dev_smoke_summary = _smoke_worldmonitor_dev(
            wm_repo_path,
            port=args.worldmonitor_dev_port,
        )

    import_cmd = [
        sys.executable,
        str(import_script),
        "--lane",
        "worldmonitor",
        "--source-path",
        str(source_path),
        "--itir-db-path",
        str(itir_db_path),
    ]
    if args.import_run_id:
        import_cmd.extend(["--import-run-id", args.import_run_id])
    if args.limit is not None:
        import_cmd.extend(["--limit", str(args.limit)])
    import_summary = _run_json_command(import_cmd, cwd=repo_path)

    requested_import_run_id = args.import_run_id or str(import_summary.get("importRunId") or "").strip()
    if not requested_import_run_id:
        raise ValueError("WorldMonitor import did not return an importRunId")
    import_run_id = requested_import_run_id
    reused_existing_import_run_id: str | None = None
    if int(import_summary.get("importedCaptureCount") or 0) == 0:
        latest_populated = _find_latest_populated_import_run(itir_db_path, source_path=source_path)
        if latest_populated is not None:
            import_run_id = latest_populated
            if latest_populated != requested_import_run_id:
                reused_existing_import_run_id = latest_populated

    export_cmd = [
        sys.executable,
        str(export_script),
        "--itir-db-path",
        str(itir_db_path),
        "--output",
        str(wm_output_path),
        "--import-run-id",
        import_run_id,
        "--source",
        args.source,
    ]
    if args.captured_date:
        export_cmd.extend(["--date", args.captured_date])
    export_summary = _run_json_command(export_cmd, cwd=repo_path)

    run_env = os.environ.copy()
    run_env["SB_RUNS_ROOT"] = str(runs_root)
    subprocess.run(
        ["bash", str(run_day_script), args.date, str(repo_path)],
        cwd=repo_path,
        env=run_env,
        check=True,
        capture_output=True,
        text=True,
    )

    sl_query_cmd = [
        sys.executable,
        str(query_script),
        "--itir-db-path",
        str(itir_db_path),
        "summary",
        "--import-run-id",
        import_run_id,
    ]
    sl_summary = _run_json_command(sl_query_cmd, cwd=repo_path)
    _write_json(sl_summary_path, sl_summary)

    chronology_cmd = [
        sys.executable,
        str(query_script),
        "--itir-db-path",
        str(itir_db_path),
        "chronology",
        "--import-run-id",
        import_run_id,
    ]
    sl_chronology = _run_json_command(chronology_cmd, cwd=repo_path)
    _write_json(sl_chronology_path, sl_chronology)

    payload: dict[str, Any] = {
        "ok": True,
        "date": args.date,
        "repoPath": str(repo_path),
        "worldmonitorRepoPath": str(wm_repo_path),
        "itirDbPath": str(itir_db_path),
        "runsRoot": str(runs_root),
        "runDir": str(run_dir),
        "importRunId": import_run_id,
        "sourcePath": str(source_path),
        "worldmonitorObservedPath": str(wm_output_path),
        "slSummaryPath": str(sl_summary_path),
        "slChronologyPath": str(sl_chronology_path),
        "importSummary": import_summary,
        "exportSummary": export_summary,
        "slSummary": sl_summary,
        "slChronology": sl_chronology,
    }
    if requested_import_run_id != import_run_id:
        payload["requestedImportRunId"] = requested_import_run_id
    if reused_existing_import_run_id is not None:
        payload["reusedExistingImportRunId"] = reused_existing_import_run_id
    if bootstrap_summary is not None:
        payload["worldmonitorBootstrap"] = bootstrap_summary
    if dev_smoke_summary is not None:
        payload["worldmonitorDevSmoke"] = dev_smoke_summary
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
