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

# What is actually in the 13 MB exe, measured from the uploaded build
# (sizes are bytes INSIDE the exe, i.e. after its zlib compression):
#
#     python314.dll   2.72 MB      tcl86t.dll     0.89 MB
#     libcrypto-3.dll 2.14 MB  <-- tk86t.dll      0.73 MB
#     PYZ.pyz         1.86 MB      ucrtbase.dll   0.52 MB
#     libssl-3.dll    0.49 MB  <--
#
# OpenSSL alone is 2.6 MB -- a fifth of the exe -- and a unit converter has
# no use for TLS. It gets dragged in by the _ssl and _hashlib extension
# modules, so excluding those two drops both DLLs. hashlib itself still
# imports fine afterwards: it falls back to the built-in _md5/_sha1/_sha2.
#
# The app imports only configparser, sys, pathlib, ctypes and tkinter, so
# nothing below is reachable at runtime.
# If a build dies with ModuleNotFoundError, empty this list first -- it is
# the most likely culprit.
EXCLUDES = [
    # --- the big win: ~2.6 MB of OpenSSL ---
    "_ssl", "ssl", "_hashlib",
    # --- compression/maths extensions nothing here touches (~0.6 MB) ---
    # decimal and lzma/bz2 have pure-Python or optional fallbacks, so
    # dropping the C extensions cannot break an import.
    "_zstd", "_lzma", "_bz2", "_decimal",
    # --- heavyweights: no-ops in a clean venv, but they save you from a
    #     40 MB exe if you ever build with the system/Anaconda Python ---
    "numpy", "pandas", "PIL", "matplotlib", "scipy", "setuptools", "pip",
    # --- stdlib this GUI never touches ---
    "unittest", "doctest", "pydoc", "pdb", "test", "tkinter.test",
    "email", "http", "urllib", "xml", "xmlrpc", "sqlite3",
    "multiprocessing", "asyncio", "socket", "select",
]

# Measured at 0.34 MB in-exe, but unicodedata is imported by more of the
# stdlib than you would expect. Add it only if you will launch the result
# and confirm the window still opens:  "unicodedata",

# Tcl ships a timezone database and translated message catalogs. The app
# never calls [clock] and never shows a localised Tk dialog, so this is
# ~0.35 MB in-exe (1.4 MB raw) of pure dead weight. Set UC_NOTRIM=1 to
# keep them if anything looks off.
TRIM_DATA = ("tcl/tzdata/", "tcl/msgs/", "tk/msgs/", "tk/demos/", "tk/images/")

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

if not os.environ.get("UC_NOTRIM"):
    _kept, _dropped = [], 0
    for _entry in a.datas:
        _dest = _entry[0].replace("\\", "/").lower() + "/"
        if any(_pat in _dest for _pat in TRIM_DATA):
            try:
                _dropped += os.path.getsize(_entry[1])
            except OSError:
                pass
            continue
        _kept.append(_entry)
    print(f"[spec] trimmed {len(a.datas) - len(_kept)} Tcl/Tk data files "
          f"({_dropped / 1e6:.2f} MB raw) -- set UC_NOTRIM=1 to keep them")
    a.datas = _kept

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
