import json
from pathlib import Path

from adapters import (
    aquaponics_calculator_stub,
    av_status,
    browser_usage,
    cli_meta,
    cloud_audit,
    crops_stub,
    input_activity,
    inaturalist_stub,
    living_environment_simulator_stub,
    maps_timeline_stub,
    mood_self_report_stub,
    pet_wearable_stub,
    medication_tracker_stub,
    notes_meta,
    social_feed,
    social_bluesky_stub,
    social_facebook_messenger_stub,
    social_mastodon_stub,
    social_reddit_stub,
    social_telegram_stub,
    social_twitter_stub,
    social_whatsapp_stub,
    window_focus,
)


FORBIDDEN_FIELDS = {
    "content",
    "body",
    "message",
    "summary",
    "url",
    "path",
}


def _contains_forbidden(data):
    blob = json.dumps(data).lower()
    return any(field in blob for field in FORBIDDEN_FIELDS)


def test_input_activity_rejects_content_fields():
    record = {
        "ts": "2026-02-06T12:00:00Z",
        "focus_app": "org.gnome.Terminal",
        "keys": {"text": 3},
        "mouse": {"clicks": 1},
        "content": "rm -rf /",
        "collected_at": "2026-02-06T12:00:01Z",
    }
    normalized = input_activity.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_window_focus_hashes_title():
    record = {
        "ts": "2026-02-06T12:05:00Z",
        "app_id": "org.gnome.Terminal",
        "window_title": "Top secret",
        "collected_at": "2026-02-06T12:05:01Z",
    }
    normalized = window_focus.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_cli_meta_hashes_cmd():
    record = {
        "ts": "2026-02-06T12:10:00Z",
        "cmd": "curl http://example.com",
        "cwd": "/home/c",
        "collected_at": "2026-02-06T12:10:01Z",
    }
    normalized = cli_meta.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_av_status_strips_names():
    record = {
        "ts": "2026-02-06T12:12:00Z",
        "engine": "defender",
        "status": "ok",
        "threat_name": "evil.exe",
        "collected_at": "2026-02-06T12:12:01Z",
    }
    normalized = av_status.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_browser_usage_hashes_domain():
    record = {
        "ts": "2026-02-06T12:15:00Z",
        "browser": "firefox",
        "domain": "example.com",
        "collected_at": "2026-02-06T12:15:01Z",
    }
    normalized = browser_usage.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_cloud_audit_hashes_ids():
    record = {
        "ts": "2026-02-06T12:20:00Z",
        "provider": "google_drive",
        "event_type": "file_updated",
        "resource_id": "file-123",
        "actor": "user@example.com",
        "ip": "10.0.0.1",
        "collected_at": "2026-02-06T12:20:01Z",
    }
    normalized = cloud_audit.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_notes_meta_hashes_ids():
    record = {
        "ts": "2026-02-06T12:25:00Z",
        "app": "obsidian",
        "note_id": "note-123",
        "vault_id": "vault-xyz",
        "content": "secret",
        "collected_at": "2026-02-06T12:25:01Z",
    }
    normalized = notes_meta.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_social_feed_hashes_ids():
    record = {
        "ts": "2026-02-06T12:30:00Z",
        "platform": "bluesky",
        "event_type": "post_created",
        "post_id": "at://did:plc:abc/post/123",
        "author": "did:plc:abc",
        "collected_at": "2026-02-06T12:30:01Z",
    }
    normalized = social_feed.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)


def test_social_stubs_hash_ids():
    record = {
        "ts": "2026-02-06T12:35:00Z",
        "post_id": "id-1",
        "author": "user",
        "content": "leak-this",
        "collected_at": "2026-02-06T12:35:01Z",
    }
    for adapter in (
        social_bluesky_stub,
        social_twitter_stub,
        social_mastodon_stub,
        social_reddit_stub,
        social_facebook_messenger_stub,
        social_telegram_stub,
        social_whatsapp_stub,
    ):
        normalized = adapter.normalize_record(record, "test")
        assert not _contains_forbidden(normalized)


def test_environment_and_agro_stubs_strip_content_fields():
    record = {
        "ts": "2026-02-06T12:40:00Z",
        "scenario_id": "sim-1",
        "system_id": "aq-1",
        "plot_id": "plot-1",
        "body": "should-not-pass",
        "message": "should-not-pass",
        "collected_at": "2026-02-06T12:40:01Z",
    }
    normalized = living_environment_simulator_stub.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)
    normalized = aquaponics_calculator_stub.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)
    normalized = crops_stub.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)
    normalized = medication_tracker_stub.normalize_record(record, "test")
    assert not _contains_forbidden(normalized)
    normalized = mood_self_report_stub.normalize_record({**record, "mood_code": "neutral"}, "test")
    assert not _contains_forbidden(normalized)
    normalized = inaturalist_stub.normalize_record(
        {**record, "taxon_id": "taxon-1", "iconic_taxon_name": "Insecta"},
        "test",
    )
    assert not _contains_forbidden(normalized)
    normalized = pet_wearable_stub.normalize_record({**record, "device_id": "d1", "pet_id": "p1"}, "test")
    assert not _contains_forbidden(normalized)
    normalized = maps_timeline_stub.normalize_record(
        {**record, "device_id": "d1", "place_id": "p-1", "lat": 1.0, "lon": 2.0},
        "test",
        provider="apple_maps",
        grid_deg=0.01,
    )
    assert not _contains_forbidden(normalized)
