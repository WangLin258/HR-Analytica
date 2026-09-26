# -*- coding: utf-8 -*-
"""HR Analytica lightweight desktop API."""

import io
import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import API_LIMITS, BASE_DIR, DB_PATH
from .database import ensure_database, load_recent_history, save_history
from .salary_core import (
    basic_stats,
    calc_penetration,
    check_internal_fairness,
    clean_data,
    detect_column_types,
    find_performance_columns,
    gen_salary_advice,
    gen_summary,
    pick_salary_column,
    read_file,
)


app = FastAPI(title="HR Analytica Desktop API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BYTES = int(API_LIMITS["max_file_size_mb"]) * 1024 * 1024
LOGGER = logging.getLogger("hr_analytica_api")


def _configure_logging() -> None:
    if LOGGER.handlers:
        return
    LOGGER.setLevel(logging.INFO)
    handler = logging.FileHandler(str(BASE_DIR / "api.log"), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    LOGGER.addHandler(handler)


_configure_logging()


def _convert_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _convert_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_convert_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _jsonify(value: Any) -> Any:
    return json.loads(json.dumps(_convert_json_value(value), ensure_ascii=False))


@app.get("/api/health")
def health():
    try:
        ensure_database()
        status = "ok"
    except Exception as exc:
        status = f"error: {exc}"
    LOGGER.info("GET /api/health -> %s", status)
    return {"status": status, "database": DB_PATH, "time": datetime.now().isoformat()}


@app.get("/api/history")
def history(limit: int = 20):
    ensure_database()
    records = load_recent_history(max(1, min(int(limit), 200)))
    for record in records:
        try:
            record["stats_summary"] = json.loads(record.get("stats_summary") or "[]")
        except Exception:
            record["stats_summary"] = []
    LOGGER.info("GET /api/history -> %s records", len(records))
    return _jsonify(records)


@app.post("/api/analyze_salary")
async def analyze_salary(
    file: UploadFile = File(...),
    group_col: Optional[str] = Form(default=None),
    value_col: Optional[str] = Form(default=None),
):
    started = time.time()
    filename = file.filename or "upload.xlsx"
    LOGGER.info("POST /api/analyze_salary start file=%s", filename)

    raw = b""
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        raw += chunk
        if len(raw) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过大小限制：{API_LIMITS['max_file_size_mb']}MB",
            )

    name = filename if filename.lower().endswith((".csv", ".xlsx", ".xls")) else f"{filename}.csv"
    bio = io.BytesIO(raw)
    bio.name = name

    try:
        df, source, sheets = read_file(bio)
        df, clean_report, removed_rows, duplicates = clean_data(df)
    except Exception as exc:
        LOGGER.exception("analyze_salary read/clean failed")
        raise HTTPException(status_code=400, detail=f"文件读取失败：{exc}") from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="清洗后没有可分析的数据")

    categorical, numeric, dates, column_types, identifiers = detect_column_types(df)
    group = group_col or ("部门" if "部门" in df.columns else (categorical[0] if categorical else None))
    value = value_col or pick_salary_column(df, numeric)

    if group not in df.columns or value not in df.columns:
        raise HTTPException(status_code=422, detail="未找到有效的分组列或薪资列")

    stats = basic_stats(df, group, value)
    if stats.empty:
        raise HTTPException(status_code=422, detail="分组后没有有效的薪资统计结果")

    numeric_values = pd.to_numeric(df[value], errors="coerce").dropna()
    if numeric_values.empty:
        raise HTTPException(status_code=422, detail="薪资列没有有效数值")

    overall_mean = float(numeric_values.mean())
    penetration = calc_penetration(stats, overall_mean)
    performance_columns = find_performance_columns(df)
    correlation = None
    fairness_info = None
    if performance_columns:
        correlation, fairness_info = check_internal_fairness(df, value, performance_columns[0])

    summary = gen_summary(stats, df, group, value)
    advice = gen_salary_advice(penetration, correlation, fairness_info, value)
    text_report = "\n\n".join(part for part in [summary, advice] if part)

    history_id = None
    try:
        history_id = save_history(
            page_type="salary",
            filename=filename,
            row_count=len(df),
            filter_config={"group_col": group, "value_col": value},
            stats_summary=stats.reset_index().to_dict(orient="records"),
            text_report=text_report,
        )
    except Exception:
        LOGGER.exception("analyze_salary history save failed")

    LOGGER.info(
        "POST /api/analyze_salary done rows=%s elapsed=%.2fs history_id=%s",
        len(df),
        time.time() - started,
        history_id,
    )

    return _jsonify(
        {
            "history_id": history_id,
            "filename": filename,
            "source": source,
            "sheets": sheets,
            "rows": len(df),
            "columns": list(df.columns),
            "column_types": column_types,
            "clean_report": clean_report,
            "removed_rows": removed_rows,
            "duplicates": duplicates,
            "group_col": group,
            "value_col": value,
            "overall_mean": overall_mean,
            "group_stats": stats.reset_index().to_dict(orient="records"),
            "penetration": penetration.reset_index().to_dict(orient="records"),
            "fairness": {
                "correlation": correlation,
                "performance_column": fairness_info[0] if fairness_info else None,
                "top_performers_underpaid": fairness_info[1] if fairness_info else None,
                "top_performers": fairness_info[2] if fairness_info else None,
            },
            "summary": summary,
            "advice": advice,
        }
    )