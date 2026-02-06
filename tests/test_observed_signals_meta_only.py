import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import (
    av_status,
    browser_usage,
    cli_meta,
    cloud_audit,
    input_activity,
    notes_meta,
    window_focus,
)
from adapters import macos_unified_log_stub, windows_event_stub
from adapters import social_bluesky_stub, social_twitter_stub, social_mastodon_stub, social_reddit_stub


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8").strip())


def test_input_activity_meta_only():
    record = _load(FIXTURE_DIR / "input_activity_sample.jsonl")
    normalized = input_activity.normalize_record(record, "test")
    assert normalized["signal"] == "input"
    assert "text" in normalized["keys"]
    assert "provenance" in normalized


def test_window_focus_hashes_title():
    record = _load(FIXTURE_DIR / "window_focus_sample.jsonl")
    normalized = window_focus.normalize_record(record, "test")
    assert normalized["signal"] == "window_focus"
    assert normalized["window_title_hash"].startswith("sha256:")


def test_cli_meta_hashes_cmd():
    record = _load(FIXTURE_DIR / "cli_meta_sample.jsonl")
    normalized = cli_meta.normalize_record(record, "test")
    assert normalized["signal"] == "cli"
    assert normalized["cmd_hash"].startswith("sha256:")
    assert normalized["cwd_hash"].startswith("sha256:")


def test_av_status_meta_only():
    record = _load(FIXTURE_DIR / "av_status_sample.jsonl")
    normalized = av_status.normalize_record(record, "test")
    assert normalized["signal"] == "av_status"
    assert "name" not in json.dumps(normalized)


def test_browser_usage_hashes_domain():
    record = _load(FIXTURE_DIR / "browser_usage_sample.jsonl")
    normalized = browser_usage.normalize_record(record, "test")
    assert normalized["signal"] == "browser_usage"
    assert normalized["domain_hash"].startswith("sha256:")


def test_cloud_audit_hashes_ids():
    record = _load(FIXTURE_DIR / "cloud_audit_sample.jsonl")
    normalized = cloud_audit.normalize_record(record, "test")
    assert normalized["signal"] == "cloud_audit"
    assert normalized["resource_id_hash"].startswith("sha256:")
    assert normalized["actor_hash"].startswith("sha256:")
    assert normalized["ip_hash"].startswith("sha256:")


def test_notes_meta_hashes_ids():
    record = _load(FIXTURE_DIR / "notes_meta_sample.jsonl")
    normalized = notes_meta.normalize_record(record, "test")
    assert normalized["signal"] == "notes_meta"
    assert normalized["note_id_hash"].startswith("sha256:")
    assert normalized["vault_id_hash"].startswith("sha256:")


def test_windows_event_stub_normalizes():
    record = _load(FIXTURE_DIR / "windows_event_sample.jsonl")
    normalized = windows_event_stub.normalize_record(record, "test")
    assert normalized["signal"] == "system"
    assert normalized["platform"] == "windows"
    assert "provenance" in normalized


def test_macos_unified_stub_normalizes():
    record = _load(FIXTURE_DIR / "macos_unified_sample.jsonl")
    normalized = macos_unified_log_stub.normalize_record(record, "test")
    assert normalized["signal"] == "system"
    assert normalized["platform"] == "macos"
    assert "provenance" in normalized


def test_social_bluesky_stub():
    record = _load(FIXTURE_DIR / "social_bluesky_sample.jsonl")
    normalized = social_bluesky_stub.normalize_record(record, "test")
    assert normalized["signal"] == "social_feed"
    assert normalized["platform"] == "bluesky"


def test_social_twitter_stub():
    record = _load(FIXTURE_DIR / "social_twitter_sample.jsonl")
    normalized = social_twitter_stub.normalize_record(record, "test")
    assert normalized["signal"] == "social_feed"
    assert normalized["platform"] == "twitter"


def test_social_mastodon_stub():
    record = _load(FIXTURE_DIR / "social_mastodon_sample.jsonl")
    normalized = social_mastodon_stub.normalize_record(record, "test")
    assert normalized["signal"] == "social_feed"
    assert normalized["platform"] == "mastodon"


def test_social_reddit_stub():
    record = _load(FIXTURE_DIR / "social_reddit_sample.jsonl")
    normalized = social_reddit_stub.normalize_record(record, "test")
    assert normalized["signal"] == "social_feed"
    assert normalized["platform"] == "reddit"
