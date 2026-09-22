# -*- coding: utf-8 -*-
"""Standalone backend process entrypoint used by the desktop shell."""

import multiprocessing
import os
import sys
from pathlib import Path

import uvicorn

from backend.main import app


def _redirect_output() -> None:
    if not getattr(sys, "frozen", False):
        return
    base_dir = Path(os.environ.get("HR_ANALYTICA_HOME") or Path(sys.executable).parent)
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        stream = open(base_dir / "backend-process.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = stream
        sys.stderr = stream
    except Exception:
        pass


def main() -> None:
    _redirect_output()
    port = int(os.environ.get("HR_ANALYTICA_API_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

