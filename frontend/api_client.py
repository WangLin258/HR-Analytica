# -*- coding: utf-8 -*-
"""HTTP client used by the Streamlit frontend when API mode is enabled."""

from typing import Optional

import requests


def analyze_salary(
    base_url: str,
    filename: str,
    raw: bytes,
    group_col: Optional[str] = None,
    value_col: Optional[str] = None,
) -> dict:
    url = base_url.rstrip("/") + "/api/analyze_salary"
    data = {}
    if group_col:
        data["group_col"] = group_col
    if value_col:
        data["value_col"] = value_col
    response = requests.post(
        url,
        files={"file": (filename, raw)},
        data=data,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def fetch_history(base_url: str, limit: int = 20) -> list:
    url = base_url.rstrip("/") + f"/api/history?limit={int(limit)}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def health(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/health"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
