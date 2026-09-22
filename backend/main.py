# -*- coding: utf-8 -*-
"""Backend service entrypoint: uvicorn backend.main:app"""

from .api import app


__all__ = ["app"]
