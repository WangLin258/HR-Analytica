# -*- coding: utf-8 -*-
"""Frontend entrypoint for the complete Streamlit application."""

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
