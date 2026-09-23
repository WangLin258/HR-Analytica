# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata


ROOT = Path.cwd()

datas = []
binaries = []
hiddenimports = [
    "multipart",
    "multipart.multipart",
    "multipart.decoders",
]

for package in ("uvicorn", "openpyxl", "xlrd"):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

for package in (
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "pandas",
    "numpy",
    "openpyxl",
    "xlrd",
):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass

try:
    datas += copy_metadata("python-multipart")
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
        "matplotlib",
        "plotly",
        "pyarrow",
        "fpdf",
        "PIL",
        "lxml",
        "tkinter",
        "pytest",
        "_pytest",
        "IPython",
        "jupyter",
        "notebook",
        "nbformat",
        "nbconvert",
        "scipy",
        "sklearn",
        "numba",
        "sqlalchemy",
        "boto3",
        "websockets",
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