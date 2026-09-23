# -*- coding: utf-8 -*-
"""SQLite access layer for the lightweight desktop backend."""

import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG, DB_PATH


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                page_type TEXT,
                filename TEXT,
                row_count INTEGER,
                filter_config TEXT,
                stats_summary TEXT,
                text_report TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id INTEGER,
                image_type TEXT,
                image_data BLOB,
                FOREIGN KEY(history_id) REFERENCES analysis_history(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def ensure_database() -> None:
    db_file = Path(DB_PATH)
    if not db_file.exists():
        legacy = Path(__file__).resolve().parent.parent / "hr_analytica.db"
        try:
            if legacy.exists():
                db_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy, db_file)
        except Exception:
            pass
    init_db()


def save_history(
    page_type: str,
    filename: str,
    row_count: int,
    filter_config: dict,
    stats_summary: Any,
    text_report: str,
) -> int:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "INSERT INTO analysis_history "
            "(timestamp, page_type, filename, row_count, filter_config, stats_summary, text_report) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                page_type,
                filename,
                int(row_count),
                json.dumps(filter_config, ensure_ascii=False, default=str),
                json.dumps(stats_summary, ensure_ascii=False, default=str),
                text_report or "",
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_report_image(history_id: int, image_type: str, image_data: bytes) -> None:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO report_images (history_id, image_type, image_data) VALUES (?,?,?)",
            (int(history_id), image_type, sqlite3.Binary(image_data)),
        )
        conn.commit()
    finally:
        conn.close()


def load_recent_history(limit: int = 10) -> list:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM analysis_history ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_history_images(history_id: int) -> list:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT image_type, image_data FROM report_images WHERE history_id=? ORDER BY id",
            (int(history_id),),
        ).fetchall()
        return [(row[0], bytes(row[1])) for row in rows]
    finally:
        conn.close()


def cleanup_old_history(days: Optional[int] = None) -> None:
    ensure_database()
    if days is None:
        days = int(CONFIG.get("max_history_days", 90))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "DELETE FROM report_images WHERE history_id NOT IN "
            "(SELECT id FROM analysis_history WHERE timestamp >= ?)",
            (cutoff,),
        )
        conn.execute("DELETE FROM analysis_history WHERE timestamp <= ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()


def save_user_pref(key: str, value: Any) -> None:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO user_prefs(key, value) VALUES (?,?)",
            (key, str(value)),
        )
        conn.commit()
    finally:
        conn.close()


def load_user_pref(key: str, default: Any = None) -> Any:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT value FROM user_prefs WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
    finally:
        conn.close()

