# build_exe.spec  ← สร้างไฟล์นี้ไว้ใน root โปรเจกต์

import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

# ─── รวม streamlit และ dependencies ───────────────────────────────────────
datas = []
binaries = []
hiddenimports = []

# Streamlit + altair + plotly + pandas (เพิ่มตาม package ที่ใช้จริง)
for pkg in ["streamlit", "altair", "plotly", "pandas", "pyarrow",
            "openpyxl", "xlrd", "pydeck"]:
    d, b, h = collect_all(pkg)
    datas    += d
    binaries += b
    hiddenimports += h

# รวมไฟล์ assets ของโปรเจกต์
datas += [
    ("app.py",         "."),
    ("config.py",      "."),
    ("components.py",  "."),
    ("styles.py",      "."),
    ("et_pipeline.py", "."),
    ("run_app.py",     "."),
    ("logo",           "logo"),
    ("views",          "views"),
]

# ─── Analysis ──────────────────────────────────────────────────────────────
a = Analysis(
    ["desktop.py"],           # entry point
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        "streamlit.web.cli",
        "streamlit.runtime.scriptrunner",
        "pywebview",
        "pywebview.platforms.winforms",  # Windows
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CreditMonitorDashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,         # ← ซ่อน console window
    icon=None,             # ← ใส่ path .ico ถ้ามี เช่น "logo/icon.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CreditMonitorDashboard",
)