# -*- coding: utf-8 -*-
"""Centralized configuration for HR Analytica."""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).resolve().parent
else:
    _BASE_DIR = Path(__file__).resolve().parent

BASE_DIR = Path(os.environ.get("HR_ANALYTICA_HOME") or _BASE_DIR)
DB_PATH = str(BASE_DIR / "hr_data.db")
APP_PORT = 8501
LOG_FILE = str(BASE_DIR / "app_errors.log")

PAGE_NAMES = ["首页", "薪酬分析", "招聘分析", "历史报告"]
SAMPLE_FILES = {
    "salary_csv": "薪酬分析样例.csv",
    "salary_excel": "薪酬设计全套数据表.xlsx",
    "recruit_csv": "招聘分析样例.csv",
    "recruit_excel": "招聘分析样例.xlsx",
}

CONFIG = {
    "sample_rows": 50000,
    "date_threshold": 0.7,
    "numeric_threshold": 0.85,
    "history_limit": 5,
    "chart_dpi": 120,
    "pdf_chart_dpi": 150,
    "ranking_top_n": 15,
    "large_threshold": 100000,
    "sample_frac": 0.3,
    "chunk_rows": 10000,
    "max_history_days": 90,
}

API_LIMITS = {
    "max_file_size_mb": 10,
    "rate_limit_per_minute": 5,
}
