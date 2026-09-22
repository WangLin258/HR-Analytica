# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


ROOT = Path.cwd()

datas = []
binaries = []
hiddenimports = []

for package in (
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "anyio",
    "multipart",
    "pandas",
    "numpy",
    "matplotlib",
    "openpyxl",
    "fpdf",
    "plotly",
    "requests",
):
    try:
        package_datas, package_binaries, package_hidden = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hidden
    except Exception:
        pass

for package in (
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "pandas",
    "numpy",
    "matplotlib",
    "openpyxl",
    "fpdf",
    "plotly",
    "requests",
):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass


a = Analysis(
    ["backend/server_entry.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "_pytest",
        "tkinter",
        "IPython",
        "jupyter",
        "notebook",
        "nbformat",
        "nbconvert",
        "sphinx",
        "docutils",
        "pydoc_data",
        "matplotlib.tests",
        "pandas.tests",
        "numpy.tests",
        "plotly.tests",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HR_Analytica_Backend",
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HR_Analytica_Backend",
)