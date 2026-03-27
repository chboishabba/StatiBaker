from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal


# Canonical dashboard store (DB-first).
#
# Policy: we do not persist dashboard payload JSON blobs. We persist the payload in
# normalized tables and reconstruct a payload dict at query time.
#
# JSON/HTML exports are legacy/regression/debug-only; see docs.

DashboardView = Literal["daily", "weekly", "lifetime", "costing"]
DashboardScope = Literal["scoped", "all"]


@dataclass(frozen=True)
class DashboardKey:
    date: str  # YYYY-MM-DD, end date for weekly/lifetime
    view: DashboardView
    scope: DashboardScope
    window_days: int  # 0 for daily/lifetime/costing; N for weekly


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Keep this conservative for portability. WAL has caused "unable to open database file"
    # issues in other parts of the repo on some setups.
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=DELETE;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sb_dashboards (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          generated_at TEXT,
          period_start TEXT,
          period_end TEXT,
          days INTEGER,
          chat_source TEXT,
          chat_scope_mode TEXT,
          chat_scope_thread_count INTEGER,
          PRIMARY KEY (date, view, scope, window_days)
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_warnings (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          idx INTEGER NOT NULL,
          warning TEXT NOT NULL,
          PRIMARY KEY (date, view, scope, window_days, idx),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboards(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_artifact_links (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          idx INTEGER NOT NULL,
          label TEXT NOT NULL,
          path TEXT NOT NULL,
          PRIMARY KEY (date, view, scope, window_days, idx),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboards(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_timeline (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          idx INTEGER NOT NULL,
          ts TEXT NOT NULL,
          hour INTEGER NOT NULL,
          kind TEXT NOT NULL,
          detail TEXT NOT NULL,
          source_path TEXT,
          PRIMARY KEY (date, view, scope, window_days, idx),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboards(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_timeline_meta (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          timeline_idx INTEGER NOT NULL,
          path TEXT NOT NULL,
          value_type TEXT NOT NULL, -- null|bool|int|float|text
          value_int INTEGER,
          value_float REAL,
          value_text TEXT,
          PRIMARY KEY (date, view, scope, window_days, timeline_idx, path),
          FOREIGN KEY (date, view, scope, window_days, timeline_idx) REFERENCES sb_dashboard_timeline(date, view, scope, window_days, idx) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_frequency_by_hour (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          lane TEXT NOT NULL,
          hour INTEGER NOT NULL,
          count INTEGER NOT NULL,
          PRIMARY KEY (date, view, scope, window_days, lane, hour),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboards(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_chat_flow (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          message_count INTEGER,
          thread_count INTEGER,
          switch_count INTEGER,
          switch_rate REAL,
          dominant_thread_share REAL,
          active_hours INTEGER,
          first_ts TEXT,
          last_ts TEXT,
          waterfall_render_limit INTEGER,
          waterfall_truncated INTEGER,
          PRIMARY KEY (date, view, scope, window_days),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboards(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_chat_flow_hour_bins (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          hour INTEGER NOT NULL,
          count INTEGER NOT NULL,
          PRIMARY KEY (date, view, scope, window_days, hour),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboard_chat_flow(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_chat_flow_threads (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          idx INTEGER NOT NULL,
          thread_id TEXT NOT NULL,
          thread_key TEXT,
          thread_title TEXT,
          message_count INTEGER,
          share REAL,
          color_hex TEXT,
          color_index INTEGER,
          thread_start_ts TEXT,
          thread_start_hour INTEGER,
          PRIMARY KEY (date, view, scope, window_days, idx),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboard_chat_flow(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_chat_flow_waterfall (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          idx INTEGER NOT NULL,
          ts TEXT NOT NULL,
          hour INTEGER NOT NULL,
          role TEXT,
          thread_id TEXT NOT NULL,
          thread_key TEXT,
          thread_title TEXT,
          thread_start_ts TEXT,
          thread_start_hour INTEGER,
          switch INTEGER,
          gap_to_next_seconds REAL,
          color_hex TEXT,
          color_index INTEGER,
          PRIMARY KEY (date, view, scope, window_days, idx),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboard_chat_flow(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_dashboard_chat_threads (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          idx INTEGER NOT NULL,
          thread_id TEXT NOT NULL,
          title TEXT,
          title_resolved TEXT,
          origin TEXT,
          message_count INTEGER,
          first_ts TEXT,
          last_ts TEXT,
          first_user_preview TEXT,
          PRIMARY KEY (date, view, scope, window_days, idx),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboards(date, view, scope, window_days) ON DELETE CASCADE
        );

        -- Flattened roles/source_ids payload per chat thread.
        CREATE TABLE IF NOT EXISTS sb_dashboard_chat_thread_kv (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          thread_idx INTEGER NOT NULL,
          field TEXT NOT NULL, -- roles|source_ids
          path TEXT NOT NULL,
          value_type TEXT NOT NULL,
          value_int INTEGER,
          value_float REAL,
          value_text TEXT,
          PRIMARY KEY (date, view, scope, window_days, thread_idx, field, path),
          FOREIGN KEY (date, view, scope, window_days, thread_idx) REFERENCES sb_dashboard_chat_threads(date, view, scope, window_days, idx) ON DELETE CASCADE
        );

        -- Generic flattened dict/list stores for unknown-shape dicts.
        CREATE TABLE IF NOT EXISTS sb_dashboard_kv (
          date TEXT NOT NULL,
          view TEXT NOT NULL,
          scope TEXT NOT NULL,
          window_days INTEGER NOT NULL,
          section TEXT NOT NULL, -- summary|tool_use_summary|notes_meta_summary
          path TEXT NOT NULL,
          value_type TEXT NOT NULL,
          value_int INTEGER,
          value_float REAL,
          value_text TEXT,
          PRIMARY KEY (date, view, scope, window_days, section, path),
          FOREIGN KEY (date, view, scope, window_days) REFERENCES sb_dashboards(date, view, scope, window_days) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sb_itir_overlays (
          annotation_id TEXT PRIMARY KEY,
          activity_event_id TEXT NOT NULL,
          sb_state_id TEXT,
          state_date TEXT,
          observer_kind TEXT,
          status TEXT,
          confidence TEXT,
          provenance_json TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sb_itir_mission_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          mission_id TEXT NOT NULL,
          node_kind TEXT,
          topic_label TEXT,
          ref_type TEXT,
          payload_json TEXT NOT NULL,
          PRIMARY KEY (annotation_id, ref_order)
        );

        CREATE TABLE IF NOT EXISTS sb_itir_evidence_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          event_id TEXT,
          source_id TEXT,
          ref_kind TEXT,
          payload_json TEXT NOT NULL,
          PRIMARY KEY (annotation_id, ref_order)
        );

        -- Fuzzymodo selector v0.1 observer overlay extension tables.
        CREATE TABLE IF NOT EXISTS sb_fuzzymodo_selector_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          selector_hash TEXT NOT NULL,
          decision_state TEXT,
          matched INTEGER,
          policy_hash TEXT,
          replay_key TEXT,
          created_at TEXT,
          PRIMARY KEY (annotation_id, ref_order)
        );

        CREATE TABLE IF NOT EXISTS sb_fuzzymodo_reason_codes (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          reason_code TEXT NOT NULL,
          detail TEXT,
          PRIMARY KEY (annotation_id, ref_order)
        );

        CREATE TABLE IF NOT EXISTS sb_fuzzymodo_artifact_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          artifact_kind TEXT NOT NULL,
          artifact_locator TEXT NOT NULL,
          artifact_hash TEXT,
          PRIMARY KEY (annotation_id, ref_order)
        );

        -- Casey workspace v0.1 observer overlay extension tables.
        CREATE TABLE IF NOT EXISTS sb_casey_workspace_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          ws_id TEXT NOT NULL,
          head_tree_id TEXT,
          selected_path_count INTEGER,
          policy_tie_break TEXT,
          policy_prefer_author TEXT,
          PRIMARY KEY (annotation_id, ref_order)
        );

        CREATE TABLE IF NOT EXISTS sb_casey_operation_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          operation_kind TEXT NOT NULL,
          path TEXT,
          tree_id_before TEXT,
          tree_id_after TEXT,
          chosen_fv_id TEXT,
          resolved_fv_id TEXT,
          receipt_hash TEXT,
          created_at TEXT,
          PRIMARY KEY (annotation_id, ref_order)
        );

        CREATE TABLE IF NOT EXISTS sb_casey_build_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          build_id TEXT NOT NULL,
          tree_id TEXT NOT NULL,
          selection_digest TEXT NOT NULL,
          created_at TEXT,
          PRIMARY KEY (annotation_id, ref_order)
        );

        CREATE TABLE IF NOT EXISTS sb_corkysoft_review_events (
          annotation_id TEXT PRIMARY KEY REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          event_id TEXT NOT NULL,
          event_family TEXT NOT NULL,
          event_time TEXT NOT NULL,
          source_system TEXT NOT NULL,
          actor_ref TEXT NOT NULL,
          authority_class TEXT NOT NULL,
          correlation_key TEXT NOT NULL,
          summary TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sb_corkysoft_object_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          ref_key TEXT,
          ref_value TEXT,
          payload_json TEXT NOT NULL,
          PRIMARY KEY (annotation_id, ref_order)
        );

        CREATE TABLE IF NOT EXISTS sb_corkysoft_provenance_refs (
          annotation_id TEXT NOT NULL REFERENCES sb_itir_overlays(annotation_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          ref_kind TEXT,
          ref_uri TEXT,
          payload_json TEXT NOT NULL,
          PRIMARY KEY (annotation_id, ref_order)
        );
        """
    )


def _value_to_row(value: Any) -> tuple[str, int | None, float | None, str | None]:
    if value is None:
        return ("null", None, None, None)
    if isinstance(value, bool):
        return ("bool", 1 if value else 0, None, None)
    if isinstance(value, int) and not isinstance(value, bool):
        return ("int", int(value), None, None)
    if isinstance(value, float):
        return ("float", None, float(value), None)
    return ("text", None, None, str(value))


def _flatten(obj: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(obj, dict):
        for k in sorted(obj.keys(), key=lambda x: str(x)):
            kk = str(k)
            v = obj.get(k)
            p = kk if not prefix else f"{prefix}.{kk}"
            yield from _flatten(v, p)
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            p = str(i) if not prefix else f"{prefix}.{i}"
            yield from _flatten(v, p)
        return
    yield (prefix, obj)


def _unflatten(rows: Iterable[tuple[str, Any]]) -> Any:
    def is_index(seg: str) -> bool:
        return seg.isdigit()

    root: Any = {}

    for path, value in rows:
        segs = [s for s in (path or "").split(".") if s != ""]
        if not segs:
            root = value
            continue

        cur: Any = root
        parent: Any = None
        parent_key: str | int | None = None

        for j, seg in enumerate(segs):
            last = j == len(segs) - 1
            next_is_idx = (j + 1 < len(segs)) and is_index(segs[j + 1])

            if is_index(seg):
                idx = int(seg)
                if not isinstance(cur, list):
                    new_list: list[Any] = []
                    if parent is None:
                        root = new_list
                    else:
                        if isinstance(parent, dict) and isinstance(parent_key, str):
                            parent[parent_key] = new_list
                        elif isinstance(parent, list) and isinstance(parent_key, int):
                            while len(parent) <= parent_key:
                                parent.append(None)
                            parent[parent_key] = new_list
                        else:
                            raise ValueError("Invalid unflatten state (list container assignment)")
                    cur = new_list

                while len(cur) <= idx:
                    cur.append(None)

                if last:
                    cur[idx] = value
                    break

                if cur[idx] is None:
                    cur[idx] = [] if next_is_idx else {}

                parent, parent_key = cur, idx
                cur = cur[idx]
                continue

            # object segment
            if not isinstance(cur, dict):
                new_obj: dict[str, Any] = {}
                if parent is None:
                    root = new_obj
                else:
                    if isinstance(parent, dict) and isinstance(parent_key, str):
                        parent[parent_key] = new_obj
                    elif isinstance(parent, list) and isinstance(parent_key, int):
                        while len(parent) <= parent_key:
                            parent.append(None)
                        parent[parent_key] = new_obj
                    else:
                        raise ValueError("Invalid unflatten state (dict container assignment)")
                cur = new_obj

            if last:
                cur[seg] = value
                break

            if seg not in cur or cur[seg] is None:
                cur[seg] = [] if next_is_idx else {}

            parent, parent_key = cur, seg
            cur = cur[seg]

    return root


def upsert_dashboard_payload(
    *,
    db_path: Path,
    key: DashboardKey,
    payload: dict[str, Any],
) -> None:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        _upsert_dashboard_payload_conn(conn=conn, key=key, payload=payload)
        conn.commit()


def _delete_existing(conn: sqlite3.Connection, key: DashboardKey) -> None:
    where = "date=? AND view=? AND scope=? AND window_days=?"
    args = (key.date, key.view, key.scope, key.window_days)
    # Delete leaf tables first (no reliance on ON DELETE CASCADE ordering across SQLite versions).
    conn.execute(f"DELETE FROM sb_dashboard_timeline_meta WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_timeline WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_frequency_by_hour WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_chat_flow_hour_bins WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_chat_flow_waterfall WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_chat_flow_threads WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_chat_flow WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_chat_thread_kv WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_chat_threads WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_artifact_links WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_warnings WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboard_kv WHERE {where}", args)
    conn.execute(f"DELETE FROM sb_dashboards WHERE {where}", args)


def _upsert_dashboard_payload_conn(
    *,
    conn: sqlite3.Connection,
    key: DashboardKey,
    payload: dict[str, Any],
) -> None:
    _delete_existing(conn, key)

    conn.execute(
        """
        INSERT INTO sb_dashboards(
          date, view, scope, window_days, generated_at, period_start, period_end, days,
          chat_source, chat_scope_mode, chat_scope_thread_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key.date,
            key.view,
            key.scope,
            key.window_days,
            payload.get("generated_at"),
            payload.get("period_start"),
            payload.get("period_end"),
            payload.get("days"),
            payload.get("chat_source"),
            payload.get("chat_scope_mode"),
            payload.get("chat_scope_thread_count"),
        ),
    )

    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    for i, w in enumerate(warnings):
        conn.execute(
            "INSERT INTO sb_dashboard_warnings(date, view, scope, window_days, idx, warning) VALUES (?, ?, ?, ?, ?, ?)",
            (key.date, key.view, key.scope, key.window_days, i, str(w)),
        )

    links = payload.get("artifact_links") if isinstance(payload.get("artifact_links"), list) else []
    for i, l in enumerate(links):
        if not isinstance(l, dict):
            continue
        conn.execute(
            "INSERT INTO sb_dashboard_artifact_links(date, view, scope, window_days, idx, label, path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key.date, key.view, key.scope, key.window_days, i, str(l.get("label") or ""), str(l.get("path") or "")),
        )

    timeline = payload.get("timeline") if isinstance(payload.get("timeline"), list) else []
    for i, e in enumerate(timeline):
        if not isinstance(e, dict):
            continue
        conn.execute(
            """
            INSERT INTO sb_dashboard_timeline(date, view, scope, window_days, idx, ts, hour, kind, detail, source_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key.date,
                key.view,
                key.scope,
                key.window_days,
                i,
                str(e.get("ts") or ""),
                int(e.get("hour") or 0),
                str(e.get("kind") or ""),
                str(e.get("detail") or ""),
                str(e.get("source_path") or "") if e.get("source_path") is not None else None,
            ),
        )
        meta = e.get("meta")
        if isinstance(meta, dict) or isinstance(meta, list):
            for p, v in _flatten(meta, ""):
                vt, vi, vf, vs = _value_to_row(v)
                conn.execute(
                    """
                    INSERT INTO sb_dashboard_timeline_meta(
                      date, view, scope, window_days, timeline_idx, path, value_type, value_int, value_float, value_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key.date, key.view, key.scope, key.window_days, i, p, vt, vi, vf, vs),
                )

    freq = payload.get("frequency_by_hour") if isinstance(payload.get("frequency_by_hour"), dict) else {}
    for lane in sorted(freq.keys(), key=lambda x: str(x)):
        vals = freq.get(lane)
        if not isinstance(vals, list):
            continue
        for hour, count in enumerate(vals[:24]):
            c = int(count) if isinstance(count, (int, float)) else 0
            conn.execute(
                "INSERT INTO sb_dashboard_frequency_by_hour(date, view, scope, window_days, lane, hour, count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key.date, key.view, key.scope, key.window_days, str(lane), hour, max(0, c)),
            )

    chat_flow = payload.get("chat_flow") if isinstance(payload.get("chat_flow"), dict) else None
    if isinstance(chat_flow, dict):
        conn.execute(
            """
            INSERT INTO sb_dashboard_chat_flow(
              date, view, scope, window_days,
              message_count, thread_count, switch_count, switch_rate, dominant_thread_share,
              active_hours, first_ts, last_ts, waterfall_render_limit, waterfall_truncated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key.date,
                key.view,
                key.scope,
                key.window_days,
                chat_flow.get("message_count"),
                chat_flow.get("thread_count"),
                chat_flow.get("switch_count"),
                chat_flow.get("switch_rate"),
                chat_flow.get("dominant_thread_share"),
                chat_flow.get("active_hours"),
                chat_flow.get("first_ts"),
                chat_flow.get("last_ts"),
                chat_flow.get("waterfall_render_limit"),
                1 if chat_flow.get("waterfall_truncated") else 0,
            ),
        )
        hour_bins = chat_flow.get("hour_bins")
        if isinstance(hour_bins, list):
            for hour, count in enumerate(hour_bins[:24]):
                c = int(count) if isinstance(count, (int, float)) else 0
                conn.execute(
                    "INSERT INTO sb_dashboard_chat_flow_hour_bins(date, view, scope, window_days, hour, count) VALUES (?, ?, ?, ?, ?, ?)",
                    (key.date, key.view, key.scope, key.window_days, hour, max(0, c)),
                )

        threads = chat_flow.get("threads") if isinstance(chat_flow.get("threads"), list) else []
        for i, t in enumerate(threads):
            if not isinstance(t, dict):
                continue
            conn.execute(
                """
                INSERT INTO sb_dashboard_chat_flow_threads(
                  date, view, scope, window_days, idx, thread_id, thread_key, thread_title, message_count, share,
                  color_hex, color_index, thread_start_ts, thread_start_hour
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key.date,
                    key.view,
                    key.scope,
                    key.window_days,
                    i,
                    str(t.get("thread_id") or ""),
                    str(t.get("thread_key") or "") if t.get("thread_key") is not None else None,
                    str(t.get("thread_title") or "") if t.get("thread_title") is not None else None,
                    t.get("message_count"),
                    t.get("share"),
                    str(t.get("color_hex") or "") if t.get("color_hex") is not None else None,
                    t.get("color_index"),
                    str(t.get("thread_start_ts") or "") if t.get("thread_start_ts") is not None else None,
                    t.get("thread_start_hour"),
                ),
            )

        waterfall = chat_flow.get("waterfall") if isinstance(chat_flow.get("waterfall"), list) else []
        for i, w in enumerate(waterfall):
            if not isinstance(w, dict):
                continue
            conn.execute(
                """
                INSERT INTO sb_dashboard_chat_flow_waterfall(
                  date, view, scope, window_days, idx, ts, hour, role, thread_id, thread_key, thread_title,
                  thread_start_ts, thread_start_hour, switch, gap_to_next_seconds, color_hex, color_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key.date,
                    key.view,
                    key.scope,
                    key.window_days,
                    i,
                    str(w.get("ts") or ""),
                    int(w.get("hour") or 0),
                    str(w.get("role") or "") if w.get("role") is not None else None,
                    str(w.get("thread_id") or ""),
                    str(w.get("thread_key") or "") if w.get("thread_key") is not None else None,
                    str(w.get("thread_title") or "") if w.get("thread_title") is not None else None,
                    str(w.get("thread_start_ts") or "") if w.get("thread_start_ts") is not None else None,
                    w.get("thread_start_hour"),
                    1 if w.get("switch") else 0 if w.get("switch") is not None else None,
                    w.get("gap_to_next_seconds"),
                    str(w.get("color_hex") or "") if w.get("color_hex") is not None else None,
                    w.get("color_index"),
                ),
            )

    chat_threads = payload.get("chat_threads") if isinstance(payload.get("chat_threads"), list) else []
    for i, t in enumerate(chat_threads):
        if not isinstance(t, dict):
            continue
        conn.execute(
            """
            INSERT INTO sb_dashboard_chat_threads(
              date, view, scope, window_days, idx, thread_id, title, title_resolved, origin,
              message_count, first_ts, last_ts, first_user_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key.date,
                key.view,
                key.scope,
                key.window_days,
                i,
                str(t.get("thread_id") or ""),
                str(t.get("title") or "") if t.get("title") is not None else None,
                str(t.get("title_resolved") or "") if t.get("title_resolved") is not None else None,
                str(t.get("origin") or "") if t.get("origin") is not None else None,
                t.get("message_count"),
                str(t.get("first_ts") or "") if t.get("first_ts") is not None else None,
                str(t.get("last_ts") or "") if t.get("last_ts") is not None else None,
                str(t.get("first_user_preview") or "") if t.get("first_user_preview") is not None else None,
            ),
        )

        for field in ("roles", "source_ids"):
            obj = t.get(field)
            if not isinstance(obj, (dict, list)):
                continue
            for p, v in _flatten(obj, ""):
                vt, vi, vf, vs = _value_to_row(v)
                conn.execute(
                    """
                    INSERT INTO sb_dashboard_chat_thread_kv(
                      date, view, scope, window_days, thread_idx, field, path, value_type, value_int, value_float, value_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key.date, key.view, key.scope, key.window_days, i, field, p, vt, vi, vf, vs),
                )

    for section in ("summary", "tool_use_summary", "notes_meta_summary"):
        obj = payload.get(section)
        if not isinstance(obj, (dict, list)):
            continue
        for p, v in _flatten(obj, ""):
            vt, vi, vf, vs = _value_to_row(v)
            conn.execute(
                """
                INSERT INTO sb_dashboard_kv(
                  date, view, scope, window_days, section, path, value_type, value_int, value_float, value_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (key.date, key.view, key.scope, key.window_days, section, p, vt, vi, vf, vs),
            )


def _row_to_value(vt: str, vi: int | None, vf: float | None, vs: str | None) -> Any:
    if vt == "null":
        return None
    if vt == "bool":
        return bool(vi or 0)
    if vt == "int":
        return int(vi or 0)
    if vt == "float":
        return float(vf or 0.0)
    return vs


def list_dates_with_dashboards(*, db_path: Path, view: DashboardView = "daily") -> list[str]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            "SELECT DISTINCT date FROM sb_dashboards WHERE view=? ORDER BY date ASC",
            (view,),
        ).fetchall()
        return [str(r["date"]) for r in rows]


def load_best_daily_payload_for_date(*, db_path: Path, date: str) -> tuple[dict[str, Any], DashboardScope] | None:
    # Prefer `all` scope when present, else fall back to `scoped`.
    for scope in ("all", "scoped"):
        p = load_dashboard_payload(
            db_path=db_path,
            key=DashboardKey(date=date, view="daily", scope=scope, window_days=0),
        )
        if p is not None:
            return p, scope  # type: ignore[return-value]
    return None


def load_dashboard_payload(*, db_path: Path, key: DashboardKey) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        return _load_dashboard_payload_conn(conn=conn, key=key)


def _load_dashboard_payload_conn(*, conn: sqlite3.Connection, key: DashboardKey) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT *
        FROM sb_dashboards
        WHERE date=? AND view=? AND scope=? AND window_days=?
        """,
        (key.date, key.view, key.scope, key.window_days),
    ).fetchone()
    if not row:
        return None

    payload: dict[str, Any] = {
        "date": str(row["date"]),
    }
    for f in (
        "generated_at",
        "period_start",
        "period_end",
        "days",
        "chat_source",
        "chat_scope_mode",
        "chat_scope_thread_count",
    ):
        v = row[f]
        if v is not None:
            payload[f] = v

    warnings = conn.execute(
        "SELECT idx, warning FROM sb_dashboard_warnings WHERE date=? AND view=? AND scope=? AND window_days=? ORDER BY idx ASC",
        (key.date, key.view, key.scope, key.window_days),
    ).fetchall()
    if warnings:
        payload["warnings"] = [str(r["warning"]) for r in warnings]

    links = conn.execute(
        "SELECT idx, label, path FROM sb_dashboard_artifact_links WHERE date=? AND view=? AND scope=? AND window_days=? ORDER BY idx ASC",
        (key.date, key.view, key.scope, key.window_days),
    ).fetchall()
    if links:
        payload["artifact_links"] = [{"label": str(r["label"]), "path": str(r["path"])} for r in links]

    timeline_rows = conn.execute(
        """
        SELECT idx, ts, hour, kind, detail, source_path
        FROM sb_dashboard_timeline
        WHERE date=? AND view=? AND scope=? AND window_days=?
        ORDER BY idx ASC
        """,
        (key.date, key.view, key.scope, key.window_days),
    ).fetchall()
    if timeline_rows:
        timeline: list[dict[str, Any]] = []
        for r in timeline_rows:
            e: dict[str, Any] = {
                "ts": str(r["ts"]),
                "hour": int(r["hour"]),
                "kind": str(r["kind"]),
                "detail": str(r["detail"]),
            }
            if r["source_path"] is not None:
                e["source_path"] = str(r["source_path"])
            meta_rows = conn.execute(
                """
                SELECT path, value_type, value_int, value_float, value_text
                FROM sb_dashboard_timeline_meta
                WHERE date=? AND view=? AND scope=? AND window_days=? AND timeline_idx=?
                ORDER BY path ASC
                """,
                (key.date, key.view, key.scope, key.window_days, int(r["idx"])),
            ).fetchall()
            if meta_rows:
                flat = [(str(m["path"]), _row_to_value(str(m["value_type"]), m["value_int"], m["value_float"], m["value_text"])) for m in meta_rows]
                e["meta"] = _unflatten(flat)
            timeline.append(e)
        payload["timeline"] = timeline

    freq_rows = conn.execute(
        """
        SELECT lane, hour, count
        FROM sb_dashboard_frequency_by_hour
        WHERE date=? AND view=? AND scope=? AND window_days=?
        ORDER BY lane ASC, hour ASC
        """,
        (key.date, key.view, key.scope, key.window_days),
    ).fetchall()
    if freq_rows:
        freq: dict[str, list[int]] = {}
        for r in freq_rows:
            lane = str(r["lane"])
            hour = int(r["hour"])
            cnt = int(r["count"])
            if lane not in freq:
                freq[lane] = [0] * 24
            if 0 <= hour < 24:
                freq[lane][hour] = max(0, cnt)
        payload["frequency_by_hour"] = freq

    cf = conn.execute(
        "SELECT * FROM sb_dashboard_chat_flow WHERE date=? AND view=? AND scope=? AND window_days=?",
        (key.date, key.view, key.scope, key.window_days),
    ).fetchone()
    if cf:
        chat_flow: dict[str, Any] = {}
        for f in (
            "message_count",
            "thread_count",
            "switch_count",
            "switch_rate",
            "dominant_thread_share",
            "active_hours",
            "first_ts",
            "last_ts",
            "waterfall_render_limit",
        ):
            v = cf[f]
            if v is not None:
                chat_flow[f] = v
        if cf["waterfall_truncated"] is not None:
            chat_flow["waterfall_truncated"] = bool(int(cf["waterfall_truncated"]))

        bins = conn.execute(
            """
            SELECT hour, count
            FROM sb_dashboard_chat_flow_hour_bins
            WHERE date=? AND view=? AND scope=? AND window_days=?
            ORDER BY hour ASC
            """,
            (key.date, key.view, key.scope, key.window_days),
        ).fetchall()
        if bins:
            hour_bins = [0] * 24
            for r in bins:
                h = int(r["hour"])
                if 0 <= h < 24:
                    hour_bins[h] = max(0, int(r["count"]))
            chat_flow["hour_bins"] = hour_bins

        threads = conn.execute(
            """
            SELECT *
            FROM sb_dashboard_chat_flow_threads
            WHERE date=? AND view=? AND scope=? AND window_days=?
            ORDER BY idx ASC
            """,
            (key.date, key.view, key.scope, key.window_days),
        ).fetchall()
        if threads:
            out_threads: list[dict[str, Any]] = []
            for r in threads:
                t: dict[str, Any] = {"thread_id": str(r["thread_id"])}
                for f in (
                    "thread_key",
                    "thread_title",
                    "message_count",
                    "share",
                    "color_hex",
                    "color_index",
                    "thread_start_ts",
                    "thread_start_hour",
                ):
                    v = r[f]
                    if v is not None:
                        t[f] = v
                out_threads.append(t)
            chat_flow["threads"] = out_threads

        wf = conn.execute(
            """
            SELECT *
            FROM sb_dashboard_chat_flow_waterfall
            WHERE date=? AND view=? AND scope=? AND window_days=?
            ORDER BY idx ASC
            """,
            (key.date, key.view, key.scope, key.window_days),
        ).fetchall()
        if wf:
            items: list[dict[str, Any]] = []
            for r in wf:
                d: dict[str, Any] = {
                    "ts": str(r["ts"]),
                    "hour": int(r["hour"]),
                    "thread_id": str(r["thread_id"]),
                }
                for f in (
                    "role",
                    "thread_key",
                    "thread_title",
                    "thread_start_ts",
                    "thread_start_hour",
                    "gap_to_next_seconds",
                    "color_hex",
                    "color_index",
                ):
                    v = r[f]
                    if v is not None:
                        d[f] = v
                if r["switch"] is not None:
                    d["switch"] = bool(int(r["switch"]))
                items.append(d)
            chat_flow["waterfall"] = items

        payload["chat_flow"] = chat_flow

    ct_rows = conn.execute(
        """
        SELECT *
        FROM sb_dashboard_chat_threads
        WHERE date=? AND view=? AND scope=? AND window_days=?
        ORDER BY idx ASC
        """,
        (key.date, key.view, key.scope, key.window_days),
    ).fetchall()
    if ct_rows:
        threads_out: list[dict[str, Any]] = []
        for r in ct_rows:
            t: dict[str, Any] = {"thread_id": str(r["thread_id"])}
            for f in (
                "title",
                "title_resolved",
                "origin",
                "message_count",
                "first_ts",
                "last_ts",
                "first_user_preview",
            ):
                v = r[f]
                if v is not None:
                    t[f] = v
            for field in ("roles", "source_ids"):
                kv = conn.execute(
                    """
                    SELECT path, value_type, value_int, value_float, value_text
                    FROM sb_dashboard_chat_thread_kv
                    WHERE date=? AND view=? AND scope=? AND window_days=? AND thread_idx=? AND field=?
                    ORDER BY path ASC
                    """,
                    (key.date, key.view, key.scope, key.window_days, int(r["idx"]), field),
                ).fetchall()
                if kv:
                    flat = [(str(x["path"]), _row_to_value(str(x["value_type"]), x["value_int"], x["value_float"], x["value_text"])) for x in kv]
                    t[field] = _unflatten(flat)
            threads_out.append(t)
        payload["chat_threads"] = threads_out

    for section in ("summary", "tool_use_summary", "notes_meta_summary"):
        kv = conn.execute(
            """
            SELECT path, value_type, value_int, value_float, value_text
            FROM sb_dashboard_kv
            WHERE date=? AND view=? AND scope=? AND window_days=? AND section=?
            ORDER BY path ASC
            """,
            (key.date, key.view, key.scope, key.window_days, section),
        ).fetchall()
        if kv:
            flat = [(str(x["path"]), _row_to_value(str(x["value_type"]), x["value_int"], x["value_float"], x["value_text"])) for x in kv]
            payload[section] = _unflatten(flat)

    return payload


def upsert_itir_overlay_records(*, db_path: Path, records: list[dict[str, Any]]) -> None:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        for record in records:
            annotation_id = str(record.get("annotation_id") or "")
            if not annotation_id:
                continue
            conn.execute("DELETE FROM sb_itir_mission_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_itir_evidence_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_fuzzymodo_selector_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_fuzzymodo_reason_codes WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_fuzzymodo_artifact_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_casey_workspace_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_casey_operation_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_casey_build_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_corkysoft_object_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_corkysoft_provenance_refs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM sb_corkysoft_review_events WHERE annotation_id = ?", (annotation_id,))
            conn.execute(
                """
                INSERT OR REPLACE INTO sb_itir_overlays(
                  annotation_id, activity_event_id, sb_state_id, state_date,
                  observer_kind, status, confidence, provenance_json, note
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    annotation_id,
                    str(record.get("activity_event_id") or ""),
                    str(record.get("sb_state_id") or "") if record.get("sb_state_id") is not None else None,
                    str(record.get("state_date") or "") if record.get("state_date") is not None else None,
                    str(record.get("observer_kind") or "") if record.get("observer_kind") is not None else None,
                    str(record.get("status") or "") if record.get("status") is not None else None,
                    str(record.get("confidence") or "") if record.get("confidence") is not None else None,
                    json.dumps(record.get("provenance", {}), sort_keys=True),
                    str(record.get("note") or ""),
                ),
            )
            mission_refs = record.get("mission_refs") if isinstance(record.get("mission_refs"), list) else []
            for ref_order, payload in enumerate(mission_refs):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_itir_mission_refs(
                      annotation_id, ref_order, mission_id, node_kind, topic_label, ref_type, payload_json
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("mission_id") or ""),
                        str(payload.get("node_kind") or "") if payload.get("node_kind") is not None else None,
                        str(payload.get("topic_label") or "") if payload.get("topic_label") is not None else None,
                        str(payload.get("ref_type") or "") if payload.get("ref_type") is not None else None,
                        json.dumps(payload, sort_keys=True),
                    ),
                )
            evidence_refs = record.get("evidence_refs") if isinstance(record.get("evidence_refs"), list) else []
            for ref_order, payload in enumerate(evidence_refs):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_itir_evidence_refs(
                      annotation_id, ref_order, event_id, source_id, ref_kind, payload_json
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("event_id") or "") if payload.get("event_id") is not None else None,
                        str(payload.get("source_id") or "") if payload.get("source_id") is not None else None,
                        str(payload.get("ref_kind") or "") if payload.get("ref_kind") is not None else None,
                        json.dumps(payload, sort_keys=True),
                    ),
                )

            selector_refs = record.get("selector_refs") if isinstance(record.get("selector_refs"), list) else []
            for ref_order, payload in enumerate(selector_refs):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_fuzzymodo_selector_refs(
                      annotation_id, ref_order, selector_hash, decision_state, matched, policy_hash, replay_key, created_at
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("selector_hash") or ""),
                        str(payload.get("decision_state") or "") if payload.get("decision_state") is not None else None,
                        int(payload.get("matched")) if payload.get("matched") is not None else None,
                        str(payload.get("policy_hash") or "") if payload.get("policy_hash") is not None else None,
                        str(payload.get("replay_key") or "") if payload.get("replay_key") is not None else None,
                        str(payload.get("created_at") or "") if payload.get("created_at") is not None else None,
                    ),
                )

            reason_codes = record.get("reason_codes") if isinstance(record.get("reason_codes"), list) else []
            for ref_order, payload in enumerate(reason_codes):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_fuzzymodo_reason_codes(
                      annotation_id, ref_order, reason_code, detail
                    ) VALUES (?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("reason_code") or ""),
                        str(payload.get("detail") or "") if payload.get("detail") is not None else None,
                    ),
                )

            artifact_refs = record.get("artifact_refs") if isinstance(record.get("artifact_refs"), list) else []
            for ref_order, payload in enumerate(artifact_refs):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_fuzzymodo_artifact_refs(
                      annotation_id, ref_order, artifact_kind, artifact_locator, artifact_hash
                    ) VALUES (?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("artifact_kind") or ""),
                        str(payload.get("artifact_locator") or ""),
                        str(payload.get("artifact_hash") or "") if payload.get("artifact_hash") is not None else None,
                    ),
                )

            workspace_refs = record.get("workspace_refs") if isinstance(record.get("workspace_refs"), list) else []
            for ref_order, payload in enumerate(workspace_refs):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_casey_workspace_refs(
                      annotation_id, ref_order, ws_id, head_tree_id, selected_path_count, policy_tie_break, policy_prefer_author
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("ws_id") or ""),
                        str(payload.get("head_tree_id") or "") if payload.get("head_tree_id") is not None else None,
                        int(payload.get("selected_path_count")) if payload.get("selected_path_count") is not None else None,
                        str(payload.get("policy_tie_break") or "") if payload.get("policy_tie_break") is not None else None,
                        str(payload.get("policy_prefer_author") or "") if payload.get("policy_prefer_author") is not None else None,
                    ),
                )

            operation_refs = record.get("operation_refs") if isinstance(record.get("operation_refs"), list) else []
            for ref_order, payload in enumerate(operation_refs):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_casey_operation_refs(
                      annotation_id, ref_order, operation_kind, path, tree_id_before, tree_id_after,
                      chosen_fv_id, resolved_fv_id, receipt_hash, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("operation_kind") or ""),
                        str(payload.get("path") or "") if payload.get("path") is not None else None,
                        str(payload.get("tree_id_before") or "") if payload.get("tree_id_before") is not None else None,
                        str(payload.get("tree_id_after") or "") if payload.get("tree_id_after") is not None else None,
                        str(payload.get("chosen_fv_id") or "") if payload.get("chosen_fv_id") is not None else None,
                        str(payload.get("resolved_fv_id") or "") if payload.get("resolved_fv_id") is not None else None,
                        str(payload.get("receipt_hash") or "") if payload.get("receipt_hash") is not None else None,
                        str(payload.get("created_at") or "") if payload.get("created_at") is not None else None,
                    ),
                )

            build_refs = record.get("build_refs") if isinstance(record.get("build_refs"), list) else []
            for ref_order, payload in enumerate(build_refs):
                if not isinstance(payload, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO sb_casey_build_refs(
                      annotation_id, ref_order, build_id, tree_id, selection_digest, created_at
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        ref_order,
                        str(payload.get("build_id") or ""),
                        str(payload.get("tree_id") or ""),
                        str(payload.get("selection_digest") or ""),
                        str(payload.get("created_at") or "") if payload.get("created_at") is not None else None,
                    ),
                )

            if str(record.get("observer_kind") or "") == "corkysoft_review_event_v1":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sb_corkysoft_review_events(
                      annotation_id, event_id, event_family, event_time, source_system,
                      actor_ref, authority_class, correlation_key, summary, payload_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        annotation_id,
                        str(record.get("event_id") or ""),
                        str(record.get("event_family") or ""),
                        str(record.get("event_time") or ""),
                        str(record.get("source_system") or ""),
                        str(record.get("actor_ref") or ""),
                        str(record.get("authority_class") or ""),
                        str(record.get("correlation_key") or ""),
                        str(record.get("summary") or ""),
                        json.dumps(record.get("payload", {}), sort_keys=True),
                    ),
                )
                object_refs = record.get("object_refs") if isinstance(record.get("object_refs"), list) else []
                for ref_order, payload in enumerate(object_refs):
                    if not isinstance(payload, dict):
                        continue
                    ref_key = None
                    ref_value = None
                    if payload:
                        ref_key, ref_value = next(iter(payload.items()))
                    conn.execute(
                        """
                        INSERT INTO sb_corkysoft_object_refs(
                          annotation_id, ref_order, ref_key, ref_value, payload_json
                        ) VALUES (?,?,?,?,?)
                        """,
                        (
                            annotation_id,
                            ref_order,
                            str(ref_key) if ref_key is not None else None,
                            str(ref_value) if ref_value is not None else None,
                            json.dumps(payload, sort_keys=True),
                        ),
                    )
                provenance_refs = record.get("provenance_refs") if isinstance(record.get("provenance_refs"), list) else []
                for ref_order, payload in enumerate(provenance_refs):
                    if not isinstance(payload, dict):
                        continue
                    conn.execute(
                        """
                        INSERT INTO sb_corkysoft_provenance_refs(
                          annotation_id, ref_order, ref_kind, ref_uri, payload_json
                        ) VALUES (?,?,?,?,?)
                        """,
                        (
                            annotation_id,
                            ref_order,
                            str(payload.get("ref_kind") or "") if payload.get("ref_kind") is not None else None,
                            str(payload.get("ref_uri") or "") if payload.get("ref_uri") is not None else None,
                            json.dumps(payload, sort_keys=True),
                        ),
                    )
        conn.commit()


def load_itir_overlay_records(*, db_path: Path) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT annotation_id, activity_event_id, sb_state_id, state_date, observer_kind, status, confidence, provenance_json, note
            FROM sb_itir_overlays
            ORDER BY annotation_id
            """
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            annotation_id = str(row["annotation_id"])
            mission_refs = [
                json.loads(str(item["payload_json"]))
                for item in conn.execute(
                    "SELECT payload_json FROM sb_itir_mission_refs WHERE annotation_id = ? ORDER BY ref_order",
                    (annotation_id,),
                ).fetchall()
            ]
            evidence_refs = [
                json.loads(str(item["payload_json"]))
                for item in conn.execute(
                    "SELECT payload_json FROM sb_itir_evidence_refs WHERE annotation_id = ? ORDER BY ref_order",
                    (annotation_id,),
                ).fetchall()
            ]

            selector_refs = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ref_order, selector_hash, decision_state, matched, policy_hash, replay_key, created_at
                    FROM sb_fuzzymodo_selector_refs
                    WHERE annotation_id = ?
                    ORDER BY ref_order
                    """,
                    (annotation_id,),
                ).fetchall()
            ]
            reason_codes = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ref_order, reason_code, detail
                    FROM sb_fuzzymodo_reason_codes
                    WHERE annotation_id = ?
                    ORDER BY ref_order
                    """,
                    (annotation_id,),
                ).fetchall()
            ]
            artifact_refs = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ref_order, artifact_kind, artifact_locator, artifact_hash
                    FROM sb_fuzzymodo_artifact_refs
                    WHERE annotation_id = ?
                    ORDER BY ref_order
                    """,
                    (annotation_id,),
                ).fetchall()
            ]

            workspace_refs = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ref_order, ws_id, head_tree_id, selected_path_count, policy_tie_break, policy_prefer_author
                    FROM sb_casey_workspace_refs
                    WHERE annotation_id = ?
                    ORDER BY ref_order
                    """,
                    (annotation_id,),
                ).fetchall()
            ]
            operation_refs = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ref_order, operation_kind, path, tree_id_before, tree_id_after, chosen_fv_id, resolved_fv_id, receipt_hash, created_at
                    FROM sb_casey_operation_refs
                    WHERE annotation_id = ?
                    ORDER BY ref_order
                    """,
                    (annotation_id,),
                ).fetchall()
            ]
            build_refs = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ref_order, build_id, tree_id, selection_digest, created_at
                    FROM sb_casey_build_refs
                    WHERE annotation_id = ?
                    ORDER BY ref_order
                    """,
                    (annotation_id,),
                ).fetchall()
            ]

            corkysoft_event = conn.execute(
                """
                SELECT event_id, event_family, event_time, source_system, actor_ref,
                       authority_class, correlation_key, summary, payload_json
                FROM sb_corkysoft_review_events
                WHERE annotation_id = ?
                """,
                (annotation_id,),
            ).fetchone()
            object_refs = [
                json.loads(str(item["payload_json"]))
                for item in conn.execute(
                    "SELECT payload_json FROM sb_corkysoft_object_refs WHERE annotation_id = ? ORDER BY ref_order",
                    (annotation_id,),
                ).fetchall()
            ]
            provenance_refs = [
                json.loads(str(item["payload_json"]))
                for item in conn.execute(
                    "SELECT payload_json FROM sb_corkysoft_provenance_refs WHERE annotation_id = ? ORDER BY ref_order",
                    (annotation_id,),
                ).fetchall()
            ]

            out.append(
                {
                    "activity_event_id": str(row["activity_event_id"]),
                    "annotation_id": annotation_id,
                    "sb_state_id": str(row["sb_state_id"]) if row["sb_state_id"] is not None else None,
                    "state_date": str(row["state_date"]) if row["state_date"] is not None else None,
                    "observer_kind": str(row["observer_kind"]) if row["observer_kind"] is not None else None,
                    "status": str(row["status"]) if row["status"] is not None else None,
                    "confidence": str(row["confidence"]) if row["confidence"] is not None else None,
                    "provenance": json.loads(str(row["provenance_json"])),
                    "selector_refs": selector_refs,
                    "reason_codes": reason_codes,
                    "artifact_refs": artifact_refs,
                    "workspace_refs": workspace_refs,
                    "operation_refs": operation_refs,
                    "build_refs": build_refs,
                    "workspace_refs": workspace_refs,
                    "operation_refs": operation_refs,
                    "build_refs": build_refs,
                    "mission_refs": mission_refs,
                    "evidence_refs": evidence_refs,
                    "event_id": str(corkysoft_event["event_id"]) if corkysoft_event is not None else None,
                    "event_family": str(corkysoft_event["event_family"]) if corkysoft_event is not None else None,
                    "event_time": str(corkysoft_event["event_time"]) if corkysoft_event is not None else None,
                    "source_system": str(corkysoft_event["source_system"]) if corkysoft_event is not None else None,
                    "actor_ref": str(corkysoft_event["actor_ref"]) if corkysoft_event is not None else None,
                    "authority_class": str(corkysoft_event["authority_class"]) if corkysoft_event is not None else None,
                    "correlation_key": str(corkysoft_event["correlation_key"]) if corkysoft_event is not None else None,
                    "summary": str(corkysoft_event["summary"]) if corkysoft_event is not None else None,
                    "payload": json.loads(str(corkysoft_event["payload_json"])) if corkysoft_event is not None else {},
                    "object_refs": object_refs,
                    "provenance_refs": provenance_refs,
                    "note": str(row["note"] or ""),
                }
            )
        return out
