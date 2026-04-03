#!/usr/bin/env python
import argparse
import json
from pathlib import Path

from sb.bundle import write_manifest
from sb.suite_normalized_artifact import write_compiled_state_normalized_artifact


DEFAULT_FILES = [
    "state.json",
    "drift.json",
    "activity_ledger.json",
    "sessionizer_runtime_ms.txt",
    "daily_brief.md",
    "retrospective.md",
]

GENERATED_FILES = [
    "suite_normalized_artifact.json",
]


def main():
    parser = argparse.ArgumentParser(description="Export SB bundle from run outputs.")
    parser.add_argument("--run-dir", required=True, help="runs/<date>/outputs")
    parser.add_argument("--out", required=True, help="output bundle directory")
    parser.add_argument("--sb-version", default="unknown")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    missing = []
    for name in DEFAULT_FILES:
        src = run_dir / name
        if not src.exists():
            missing.append(name)
            continue
        (out_dir / name).write_bytes(src.read_bytes())

    if missing:
        raise SystemExit(f"missing files: {', '.join(missing)}")

    state = json.loads((out_dir / "state.json").read_text(encoding="utf-8"))
    write_compiled_state_normalized_artifact(
        out_dir / "suite_normalized_artifact.json",
        state,
        artifact_ref="state.json",
    )

    write_manifest(out_dir, DEFAULT_FILES + GENERATED_FILES, sb_version=args.sb_version)


if __name__ == "__main__":
    main()
