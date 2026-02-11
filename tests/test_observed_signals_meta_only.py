import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import (
    aquaponics_calculator_stub,
    av_status,
    browser_usage,
    cli_meta,
    cloud_audit,
    crops_stub,
    inaturalist_stub,
    input_activity,
    lastfm_scrobble_stub,
    living_environment_simulator_stub,
    media_consumption,
    medication_tracker_stub,
    mood_self_report_stub,
    maps_timeline_stub,
    notebooklm_meta,
    notes_meta,
    pet_wearable_stub,
    spotify_history_stub,
    window_focus,
    youtube_watch_stub,
)
from adapters import macos_unified_log_stub, vlc_history_stub, windows_event_stub
from adapters import (
    social_bluesky_stub,
    social_facebook_messenger_stub,
    social_mastodon_stub,
    social_reddit_stub,
    social_telegram_stub,
    social_twitter_stub,
    social_whatsapp_stub,
)


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


def test_notebooklm_meta_hashes_ids():
    record = {
        "ts": "2026-02-08T12:00:00Z",
        "event_type": "source_observed",
        "notebook_id": "nb-123",
        "source_id": "src-456",
        "collected_at": "2026-02-08T12:00:01Z",
    }
    normalized = notebooklm_meta.normalize_record(record, "test")
    assert normalized["signal"] == "notes_meta"
    assert normalized["app"] == "notebooklm"
    assert normalized["notebook_id_hash"].startswith("sha256:")
    assert normalized["note_id_hash"].startswith("sha256:")
    assert normalized["event"] == "source_observed"


def test_notebooklm_meta_preserves_display_fields_and_snippet():
    record = {
        "ts": "2026-02-08T12:00:00Z",
        "event_type": "source_observed",
        "notebook_id": "nb-123",
        "notebook_title": "Policy Notebook",
        "source_id": "src-456",
        "source_title": "Vendor transition notes",
        "source_type": "google_doc",
        "source_status": "ready",
        "source_url": "https://example.test/doc/123",
        "source_summary": "Short summary snippet",
        "source_keywords": ["vendor", "transition"],
        "collected_at": "2026-02-08T12:00:01Z",
    }
    normalized = notebooklm_meta.normalize_record(record, "test")
    assert normalized["event"] == "source_observed"
    assert normalized["notebook_title"] == "Policy Notebook"
    assert normalized["source_title"] == "Vendor transition notes"
    assert normalized["source_type"] == "google_doc"
    assert normalized["source_status"] == "ready"
    assert normalized["source_url"] == "https://example.test/doc/123"
    assert normalized["source_summary"] == "Short summary snippet"
    assert normalized["source_keywords"] == ["vendor", "transition"]


def test_notebooklm_meta_artifact_event_hashes_artifact_id():
    record = {
        "ts": "2026-02-08T12:00:00Z",
        "event_type": "artifact_observed",
        "notebook_id": "nb-123",
        "artifact_id": "art-789",
        "artifact_title": "Executive Brief",
        "artifact_type": "report",
        "artifact_status": "ready",
        "artifact_created_at": "2026-02-08T11:59:58Z",
        "collected_at": "2026-02-08T12:00:01Z",
    }
    normalized = notebooklm_meta.normalize_record(record, "test")
    assert normalized["event"] == "artifact_observed"
    assert normalized["artifact_id_hash"].startswith("sha256:")
    assert normalized["artifact_title"] == "Executive Brief"
    assert normalized["artifact_type"] == "report"
    assert normalized["artifact_status"] == "ready"
    assert normalized["artifact_created_at"] == "2026-02-08T11:59:58Z"


def test_notebooklm_meta_expands_cli_list_payloads():
    record = {
        "ts": "2026-02-08T12:00:00Z",
        "collected_at": "2026-02-08T12:00:01Z",
        "notebooks": [{"id": "nb-1", "title": "Notebook 1"}],
    }
    normalized = list(notebooklm_meta.normalize_records([record], "test"))
    assert len(normalized) == 1
    assert normalized[0]["event"] == "notebook_observed"
    assert normalized[0]["notebook_id_hash"].startswith("sha256:")


def test_notebooklm_meta_expands_artifact_list_payloads():
    record = {
        "ts": "2026-02-08T12:00:00Z",
        "collected_at": "2026-02-08T12:00:01Z",
        "notebook_id": "nb-1",
        "artifacts": [{"id": "art-1", "title": "Study Guide", "type": "report", "status": "ready"}],
    }
    normalized = list(notebooklm_meta.normalize_records([record], "test"))
    assert len(normalized) == 1
    assert normalized[0]["event"] == "artifact_observed"
    assert normalized[0]["artifact_title"] == "Study Guide"


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


def test_social_facebook_messenger_stub():
    record = _load(FIXTURE_DIR / "social_facebook_messenger_sample.jsonl")
    normalized = social_facebook_messenger_stub.normalize_record(record, "test")
    assert normalized["signal"] == "social_feed"
    assert normalized["platform"] == "facebook_messenger"


def test_social_telegram_stub():
    record = _load(FIXTURE_DIR / "social_telegram_sample.jsonl")
    normalized = social_telegram_stub.normalize_record(record, "test")
    assert normalized["signal"] == "social_feed"
    assert normalized["platform"] == "telegram"


def test_social_whatsapp_stub():
    record = _load(FIXTURE_DIR / "social_whatsapp_sample.jsonl")
    normalized = social_whatsapp_stub.normalize_record(record, "test")
    assert normalized["signal"] == "social_feed"
    assert normalized["platform"] == "whatsapp"


def test_media_consumption_hashes_ids_and_computes_ratio():
    record = _load(FIXTURE_DIR / "media_consumption_sample.jsonl")
    normalized = media_consumption.normalize_record(record, "test")
    assert normalized["signal"] == "media_consumption"
    assert normalized["item_id_hash"].startswith("sha256:")
    assert normalized["item_title_hash"].startswith("sha256:")
    assert normalized["channel_hash"].startswith("sha256:")
    assert normalized["completion_ratio"] == 0.4


def test_media_youtube_stub():
    record = _load(FIXTURE_DIR / "media_youtube_sample.jsonl")
    normalized = youtube_watch_stub.normalize_record(record, "test")
    assert normalized["signal"] == "media_consumption"
    assert normalized["platform"] == "youtube"
    assert normalized["completion_ratio"] == 0.333


def test_media_spotify_stub():
    record = _load(FIXTURE_DIR / "media_spotify_sample.jsonl")
    normalized = spotify_history_stub.normalize_record(record, "test")
    assert normalized["signal"] == "media_consumption"
    assert normalized["platform"] == "spotify"
    assert normalized["consumed_seconds"] == 180
    assert normalized["content_duration_seconds"] == 240


def test_media_vlc_stub():
    record = _load(FIXTURE_DIR / "media_vlc_sample.jsonl")
    normalized = vlc_history_stub.normalize_record(record, "test")
    assert normalized["signal"] == "media_consumption"
    assert normalized["platform"] == "vlc"
    assert normalized["item_id_hash"].startswith("sha256:")


def test_media_lastfm_stub():
    record = _load(FIXTURE_DIR / "media_lastfm_sample.jsonl")
    normalized = lastfm_scrobble_stub.normalize_record(record, "test")
    assert normalized["signal"] == "media_consumption"
    assert normalized["platform"] == "lastfm"
    assert normalized["consumed_seconds"] == 210


def test_living_environment_simulator_stub():
    record = _load(FIXTURE_DIR / "living_environment_sample.jsonl")
    normalized = living_environment_simulator_stub.normalize_record(record, "test")
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "living_environment"
    assert normalized["zone_id_hash"].startswith("sha256:")
    assert normalized["co2_ppm"] == 612.0


def test_aquaponics_calculator_stub():
    record = _load(FIXTURE_DIR / "aquaponics_sample.jsonl")
    normalized = aquaponics_calculator_stub.normalize_record(record, "test")
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "aquaponics"
    assert normalized["system_id_hash"].startswith("sha256:")
    assert normalized["pump_on"] == 1
    assert normalized["ph"] == 6.8


def test_crops_stub():
    record = _load(FIXTURE_DIR / "crops_sample.jsonl")
    normalized = crops_stub.normalize_record(record, "test")
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "crops"
    assert normalized["crop_id_hash"].startswith("sha256:")
    assert normalized["stage_code"] == "vegetative"
    assert normalized["pest_flag"] == 0


def test_medication_tracker_stub():
    record = _load(FIXTURE_DIR / "medication_tracker_sample.jsonl")
    normalized = medication_tracker_stub.normalize_record(record, "test")
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "medication"
    assert normalized["medication_id_hash"].startswith("sha256:")
    assert normalized["route_code"] == "oral"
    assert normalized["dose_unit"] == "mg"
    assert normalized["adherence_flag"] == 1


def test_mood_self_report_stub():
    record = _load(FIXTURE_DIR / "mood_self_report_sample.jsonl")
    normalized = mood_self_report_stub.normalize_record(record, "test")
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "mood"
    assert normalized["mood_code"] == "stressed"
    assert normalized["note_id_hash"].startswith("sha256:")


def test_inaturalist_stub_insect_flag():
    record = _load(FIXTURE_DIR / "inaturalist_sample.jsonl")
    normalized = inaturalist_stub.normalize_record(record, "test")
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "inaturalist"
    assert normalized["taxon_id_hash"].startswith("sha256:")
    assert normalized["place_id_hash"].startswith("sha256:")
    assert normalized["obs_count"] == 2
    assert normalized["insect_flag"] == 1


def test_pet_wearable_stub():
    record = _load(FIXTURE_DIR / "pet_wearable_sample.jsonl")
    normalized = pet_wearable_stub.normalize_record(record, "test")
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "pet_wearable"
    assert normalized["device_id_hash"].startswith("sha256:")
    assert normalized["pet_id_hash"].startswith("sha256:")
    assert normalized["hr_bpm"] == 78


def test_maps_timeline_stub_hashes_location():
    record = _load(FIXTURE_DIR / "maps_timeline_sample.jsonl")
    normalized = maps_timeline_stub.normalize_record(record, "test", provider="google_maps", grid_deg=0.01)
    assert normalized["signal"] == "context_field"
    assert normalized["context_type"] == "location_timeline"
    assert normalized["timeline_provider"] == "google_maps"
    assert normalized["device_id_hash"].startswith("sha256:")
    assert normalized["place_id_hash"].startswith("sha256:")
    assert normalized["location_cell_hash"].startswith("sha256:")
