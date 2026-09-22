# -*- coding: utf-8 -*-
"""HR Analytica Phase 1 FastAPI service."""

import io
import json
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .analysis_engine import (
    clean_data,
    detect_column_types,
    find_performance_columns,
    gen_summary,
    gen_salary_advice,
    basic_stats,
    calc_penetration,
    check_internal_fairness,
    read_file,
)
from .config import API_LIMITS, BASE_DIR, DB_PATH
from .database import ensure_database, load_recent_history, save_history


app = FastAPI(title="HR Analytica Phase1 API", version="0.1.0")
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
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    LOGGER.addHandler(handler)


_configure_logging()


def _pick_salary_column(df, numeric_columns):
    keywords = [
        "实发工资",
        "月薪",
        "基本工资",
        "薪资",
        "薪酬",
        "底薪",
        "salary",
        "wage",
        "income",
        "pay",
    ]
    for col in numeric_columns:
        name = str(col).lower().replace(" ", "").replace("_", "").replace("-", "")
        if any(key.lower() in name for key in keywords):
            return col
    return numeric_columns[0] if numeric_columns else None


def _jsonify(value) -> dict:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@app.get("/api/health")
def health():
    """Return backend health status."""
    try:
        ensure_database()
        status = "ok"
    except Exception as exc:  # pragma: no cover - defensive health check
        status = f"error: {exc}"
    LOGGER.info("GET /api/health -> %s", status)
    return {"status": status, "database": DB_PATH, "time": datetime.now().isoformat()}


@app.get("/api/history")
def history(limit: int = 20):
    """Return recent salary analysis history."""
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
    """Accept a salary CSV/Excel and return analysis summary."""
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

    cat_cols, num_cols, date_cols, col_types, id_cols = detect_column_types(df)

    gc = group_col or ("部门" if "部门" in df.columns else (cat_cols[0] if cat_cols else None))
    vc = value_col or _pick_salary_column(df, num_cols)

    if gc not in df.columns or vc not in df.columns:
        raise HTTPException(status_code=422, detail="未找到有效的分组列或薪资列")

    stats = basic_stats(df, gc, vc)
    if stats.empty:
        raise HTTPException(status_code=422, detail="分组后没有有效的薪资统计结果")

    overall_mean = float(df[vc].mean())
    pen_df = calc_penetration(stats, overall_mean)
    perf_candidates = find_performance_columns(df)
    fair_r = None
    fair_info = None
    advice = ""
    if perf_candidates:
        fair_r, fair_info = check_internal_fairness(df, vc, perf_candidates[0])
    summary = gen_summary(stats, df, gc, vc)
    advice = gen_salary_advice(pen_df, fair_r, fair_info, vc)
    text_report = "\n\n".join([summary, advice])

    history_id = None
    try:
        ensure_database()
        history_id = save_history(
            page_type="salary",
            filename=filename,
            row_count=len(df),
            filter_config={"group_col": gc, "value_col": vc},
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
            "column_types": col_types,
            "clean_report": clean_report,
            "removed_rows": removed_rows,
            "duplicates": duplicates,
            "group_col": gc,
            "value_col": vc,
            "overall_mean": overall_mean,
            "group_stats": stats.reset_index().to_dict(orient="records"),
            "penetration": pen_df.reset_index().to_dict(orient="records"),
            "fairness": {
                "correlation": fair_r,
                "performance_column": fair_info[0] if fair_info else None,
                "top_performers_underpaid": fair_info[1] if fair_info else None,
                "top_performers": fair_info[2] if fair_info else None,
            },
            "summary": summary,
            "advice": advice,
        }
    )
