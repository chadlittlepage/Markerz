# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Markerz v2 (pywebview) standalone macOS app."""

import os

block_cipher = None

a = Analysis(
    ["src/markerz/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/markerz/web", "markerz/web"),
    ],
    hiddenimports=[
        "markerz",
        "markerz.cli",
        "markerz.launch",
        "markerz.markers",
        "markerz.resolve_connection",
        "markerz.timecode",
        "markerz.importers",
        "markerz.importers.csv_edl",
        "markerz.importers.frameio_edl",
        "markerz.importers.standard_edl",
        "webview",
        "webview.platforms.cocoa",
        "bottle",
        "proxy_tools",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
        "PySide6",
        "PyQt5",
        "PyQt6",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="markerz",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name="markerz",
)

app = BUNDLE(
    coll,
    name="Markerz.app",
    icon=None,
    bundle_identifier="com.chadlittlepage.markerz",
    info_plist={
        "CFBundleName": "Markerz",
        "CFBundleDisplayName": "Markerz",
        "CFBundleShortVersionString": "0.2.1",
        "CFBundleVersion": "0.2.1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSBackgroundOnly": False,
    },
)
