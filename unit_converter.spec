# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for the Unit Converter.

Build it with build.bat, or directly:

    pyinstaller --noconfirm --clean unit_converter.spec

Set UC_ONEDIR=1 to get a folder build (small exe + DLLs beside it) instead
of a single file. Onedir starts noticeably faster, because a onefile exe
unpacks itself into %TEMP% on every launch.
"""

import os

NAME = "unit_converter"
ONEDIR = os.environ.get("UC_ONEDIR", "") not in ("", "0")

# An icon is picked up automatically if you drop one next to this file.
ICON = "unit_converter.ico" if os.path.exists("unit_converter.ico") else None

# The app imports only configparser, sys, pathlib, ctypes and tkinter, so
# nothing below is reachable at runtime. Worth roughly 1 MB.
# If a build ever dies with ModuleNotFoundError, empty this list first --
# it is the most likely culprit.
EXCLUDES = [
    # Heavyweights. No-ops in a clean venv, but they save you from a 40 MB
    # exe if you ever build with the system/Anaconda Python by mistake.
    "numpy", "pandas", "PIL", "matplotlib", "scipy", "setuptools", "pip",
    # Stdlib this GUI never touches.
    "unittest", "doctest", "pydoc", "pdb", "test", "tkinter.test",
    "email", "http", "xml", "xmlrpc", "sqlite3", "multiprocessing", "asyncio",
]

# Another ~400 KB, but these are likelier to be pulled in behind your back by
# a PyInstaller runtime hook. Add them only if you will actually launch the
# result and confirm it still opens:
#     "logging", "socket", "ssl", "urllib", "bz2", "lzma", "decimal",

# UPX mangles these and the result crashes on startup, so never pack them.
UPX_EXCLUDE = [
    "vcruntime140.dll", "vcruntime140_1.dll", "python3.dll",
    "ucrtbase.dll", "msvcp140.dll",
]

a = Analysis(
    ["unit_converter.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

if ONEDIR:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,          # GUI app: no console window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=UPX_EXCLUDE,
        name=NAME,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=UPX_EXCLUDE,
        runtime_tmpdir=None,
        console=False,          # GUI app: no console window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
    )
