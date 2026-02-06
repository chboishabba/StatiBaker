#!/usr/bin/env python
import argparse
import json
from pathlib import Path

from sb.bundle import verify_manifest
from sb.drift import compute_drift


def main():
    parser = argparse.ArgumentParser(description="Verify SB bundle integrity.")
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()

    bundle = Path(args.bundle)
    errors = verify_manifest(bundle)
    if errors:
        raise SystemExit("; ".join(errors))

    state = json.loads((bundle / "state.json").read_text(encoding="utf-8"))
    drift = json.loads((bundle / "drift.json").read_text(encoding="utf-8"))
    recomputed = compute_drift(state)

    if drift.get("counters") != recomputed.get("counters"):
        raise SystemExit("drift counters mismatch")
    if drift.get("flags") != recomputed.get("flags"):
        raise SystemExit("drift flags mismatch")


if __name__ == "__main__":
    main()
