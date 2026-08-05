# -*- coding: utf-8 -*-
"""HR Analytica FastAPI endpoint: POST /api/analyze"""

import io
import os
import time
from collections import defaultdict
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import API_LIMITS
from analysis_engine import (
    read_file,
    clean_data,
    detect_column_types,
    basic_stats,
    recruit_metrics,
    recruit_cross_stats,
    find_channel_column,
    find_job_column,
)

app = FastAPI(title="HR Analytica API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8501", "http://127.0.0.1", "http://127.0.0.1:8501"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

API_KEY = os.environ.get("HR_ANALYTICA_API_KEY", "")
MAX_BYTES = int(API_LIMITS["max_file_size_mb"]) * 1024 * 1024
RATE_LIMIT = int(API_LIMITS["rate_limit_per_minute"])
_rate_hits: dict = defaultdict(list)


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    group_col: Optional[str] = None,
    value_col: Optional[str] = None,
    request: Request = None,
    x_api_key: Optional[str] = Header(default=None),
):
    """Accept CSV/Excel and return JSON statistics summary."""
    client = request.client.host if request and request.client else "unknown"
    now = time.time()
    _rate_hits[client] = [t for t in _rate_hits[client] if now - t < 60]
    if len(_rate_hits[client]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="请求频率超过限制（每分钟最多5次）")
    _rate_hits[client].append(now)

    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="无效的 API Key")

    raw = b""
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        raw += chunk
        if len(raw) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="文件超过大小限制（10MB）")
    name = file.filename or "upload"
    tmp_name = name if name.lower().endswith((".csv", ".xlsx", ".xls")) else f"{name}.csv"
    uploaded = type("UP", (), {"name": tmp_name, "seek": lambda self, p: None})()

    # read_file expects an object with .name and .seek; wrap bytes in BytesIO
    bio = io.BytesIO(raw)
    bio.name = tmp_name
    df, src, sheets = read_file(bio)
    df, report, removed, dup = clean_data(df)
    cat, num, dates, types, ids = detect_column_types(df)

    gc = group_col or (cat[0] if cat else None)
    vc = value_col or (num[0] if num else None)
    stats = None
    if gc and vc and gc in df.columns and vc in df.columns:
        stats = basic_stats(df, gc, vc).reset_index().to_dict(orient="records")

    channel_col = find_channel_column(df)
    job_col = find_job_column(df)
    recruit = None
    if channel_col and ("简历筛选结果" in df.columns or "简历数" in df.columns):
        m = recruit_metrics(df)
        recruit = m.to_dict(orient="records")

    return {
        "source": src,
        "sheets": sheets,
        "rows": len(df),
        "columns": list(df.columns),
        "column_types": types,
        "clean_report": report,
        "removed_rows": removed,
        "duplicates": dup,
        "group_stats": stats,
        "recruit_metrics": recruit,
        "channel_column": channel_col,
        "job_column": job_col,
    }
