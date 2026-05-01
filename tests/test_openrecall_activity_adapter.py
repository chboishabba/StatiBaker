import json
import sqlite3
from pathlib import Path

from adapters import openrecall_activity


def _seed_openrecall_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app TEXT,
            title TEXT,
            text TEXT,
            captured_date TEXT,
            timestamp INTEGER UNIQUE,
            embedding BLOB,
            normalized_text TEXT,
            normalization_version TEXT,
            normalization_issues_json TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO entries(app, title, text, captured_date, timestamp, embedding, normalized_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "firefox",
            "GitHub pull request",
            "captured_ date write- back details",
            "2026-05-01",
            1714521600,
            b"",
            "captured_date write-back details",
        ),
    )
    conn.execute(
        """
        INSERT INTO entries(app, title, text, captured_date, timestamp, embedding, normalized_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "discord",
            "DM with friend",
            "hello there",
            "2026-05-01",
            1714521660,
            b"",
            None,
        ),
    )
    conn.commit()
    conn.close()


def test_export_day_emits_bounded_rows_with_deep_links(tmp_path: Path) -> None:
    db_path = tmp_path / "recall.db"
    screenshots_dir = tmp_path / "screenshots"
    screenshots_dir.mkdir()
    _seed_openrecall_db(db_path)
    (screenshots_dir / "1714521600_0.webp").write_bytes(b"fake")

    rows = openrecall_activity.export_day(
        db_path=db_path,
        captured_date="2026-05-01",
        screenshots_dir=screenshots_dir,
        base_url="http://127.0.0.1:8082",
        device_id="workstation-a",
        session_id="session-1",
        source="openrecall_activity",
        preview_chars=24,
    )

    assert len(rows) == 2
    first = rows[0]
    second = rows[1]
    assert first["signal"] == "openrecall_activity"
    assert first["activity_kind"] == "research_activity"
    assert first["deep_link"] == "http://127.0.0.1:8082/entry/1"
    assert first["screenshot_present"] is True
    assert first["capture_count"] == 1
    assert first["ocr_preview"] == "captured_date write-bac…"
    assert first["device_id"] == "workstation-a"
    assert first["session_id"] == "session-1"
    assert second["activity_kind"] == "communication_activity"
    assert second["deep_link"] == "http://127.0.0.1:8082/entry/2"


def test_cli_writes_jsonl(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "recall.db"
    screenshots_dir = tmp_path / "screenshots"
    screenshots_dir.mkdir()
    _seed_openrecall_db(db_path)
    output_path = tmp_path / "openrecall.jsonl"

    monkeypatch.setattr(
        "sys.argv",
        [
            "openrecall_activity.py",
            "--db-path",
            str(db_path),
            "--date",
            "2026-05-01",
            "--output",
            str(output_path),
            "--screenshots-dir",
            str(screenshots_dir),
        ],
    )
    openrecall_activity.main()

    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    assert rows[0]["source_ref"] == "openrecall.entry:1"
