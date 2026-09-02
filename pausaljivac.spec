# -*- mode: python ; coding: utf-8 -*-
# Builds a onedir (folder, not single-file) distribution: PyInstaller's
# onefile mode re-extracts everything to a temp dir on every launch, which
# makes it much harder to drop in extra native libraries (see the Windows
# GTK / macOS Homebrew dylib handling in .github/workflows/build.yml) and
# is slower to start. A folder you unzip and run from is a fine trade-off
# for a small friends-and-family app.
import sys

block_cipher = None

datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("schema.sql", "."),
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "blueprints.dashboard",
        "blueprints.clients",
        "blueprints.invoices",
        "blueprints.documents",
        "blueprints.tax",
        "blueprints.settings",
        "blueprints.inflow_form",
        "blueprints.reports",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Pausaljivac",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # first release: keep a console so friends can screenshot errors
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
    name="Pausaljivac",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Pausaljivac.app",
        icon=None,
        bundle_identifier="rs.pausaljivac.app",
        info_plist={"NSHighResolutionCapable": "True"},
    )
