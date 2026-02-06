import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(bundle_dir: Path, files: list[str], policy_receipts=None, sb_version="unknown"):
    manifest = {
        "sb_version": sb_version,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy_receipts": policy_receipts or [],
        "files": {},
    }
    for name in files:
        path = bundle_dir / name
        manifest["files"][name] = _sha256(path)
    return manifest


def write_manifest(bundle_dir: Path, files: list[str], policy_receipts=None, sb_version="unknown"):
    manifest = build_manifest(bundle_dir, files, policy_receipts=policy_receipts, sb_version=sb_version)
    path = bundle_dir / "manifest.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    return manifest


def verify_manifest(bundle_dir: Path) -> list[str]:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    errors = []
    files = manifest.get("files", {})
    for name, digest in files.items():
        path = bundle_dir / name
        if not path.exists():
            errors.append(f"missing file: {name}")
            continue
        actual = _sha256(path)
        if actual != digest:
            errors.append(f"hash mismatch: {name}")
    return errors
