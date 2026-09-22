# -*- coding: utf-8 -*-
"""SQLite access layer for HR Analytica backend."""

import shutil
from pathlib import Path

from .analysis_engine import (
    init_db,
    save_history,
    save_report_image,
    load_recent_history,
    get_history_images,
    cleanup_old_history,
    save_user_pref,
    load_user_pref,
)
from .config import BASE_DIR, DB_PATH


def ensure_database() -> None:
    """Copy legacy history once, then create current backend tables."""
    db_file = Path(DB_PATH)
    if not db_file.exists():
        legacy = BASE_DIR.parent / "hr_analytica.db"
        try:
            if legacy.exists():
                db_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy, db_file)
        except Exception:
            pass
    init_db()


__all__ = [
    "ensure_database",
    "init_db",
    "save_history",
    "save_report_image",
    "load_recent_history",
    "get_history_images",
    "cleanup_old_history",
    "save_user_pref",
    "load_user_pref",
]
