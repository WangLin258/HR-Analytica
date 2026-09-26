# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


ROOT = Path.cwd()


def _without_tests(module_names):
    return [name for name in module_names if "test" not in name.lower()]


datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "ui_components.py"), "."),
    (str(ROOT / "analysis_engine.py"), "."),
    (str(ROOT / "config.py"), "."),
    (str(ROOT / "auth.py"), "."),
    (str(ROOT / "style.css"), "."),
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "backend"), "backend"),
    (str(ROOT / "薪酬分析样例.csv"), "."),
    (str(ROOT / "薪酬设计全套数据表.xlsx"), "."),
    (str(ROOT / "招聘分析样例.csv"), "."),
    (str(ROOT / "招聘分析样例.xlsx"), "."),
    (str(ROOT / ".streamlit" / "config.toml"), ".streamlit"),
]

for _pkg in ("streamlit", "plotly", "altair", "matplotlib"):
    try:
        datas += collect_data_files(_pkg)
    except Exception:
        pass

for _pkg in (
    "streamlit",
    "altair",
    "plotly",
    "pandas",
    "openpyxl",
    "fpdf",
    "matplotlib",
):
    try:
        datas += copy_metadata(_pkg)
    except Exception:
        pass

hiddenimports = [
    "auth",
    "tkinter",
    "tkinter.ttk",
    "requests",
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.runtime.scriptrunner_utils.script_run_context",
    "streamlit.components.v1.components",
    "plotly.express",
    "plotly.graph_objects",
]

for _pkg in (
    "streamlit",
    "plotly",
    "altair",
    "pandas",
    "openpyxl",
    "fpdf",
    "matplotlib",
    "requests",
):
    try:
        hiddenimports += _without_tests(collect_submodules(_pkg))
    except Exception:
        pass


a = Analysis(
    ["launcher.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HR_Analysis_Assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
