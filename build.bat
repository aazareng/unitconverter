@echo off
rem ---------------------------------------------------------------------
rem  Build unit_converter.exe with PyInstaller.
rem
rem    build.bat            single-file exe  -> dist\unit_converter.exe
rem    build.bat onedir     folder build     -> dist\unit_converter\
rem
rem  Everything happens in a throwaway venv (build-env\) so that whatever
rem  is installed in your main Python cannot leak into the bundle -- that
rem  is the single biggest cause of a bloated exe.
rem
rem  UPX roughly halves the result. Drop upx.exe in a folder named upx\
rem  beside this script, or set UPX_DIR, and it is used automatically.
rem  Heads up: UPX-packed exes are a common antivirus false positive.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

if /i "%~1"=="onedir" (
    set "UC_ONEDIR=1"
    echo [*] Folder build ^(faster startup^).
) else (
    set "UC_ONEDIR="
    echo [*] Single-file build.
)

rem --- locate a Python -------------------------------------------------
set "PY_CMD="
py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [!] No Python found. Install it from python.org and tick
    echo     "Add python.exe to PATH", then re-run this script.
    exit /b 1
)
echo [*] Using: %PY_CMD%

rem --- throwaway build venv --------------------------------------------
if not exist "build-env\Scripts\python.exe" (
    echo [*] Creating build-env\ ...
    %PY_CMD% -m venv build-env || (
        echo [!] Could not create the virtual environment.
        exit /b 1
    )
)
set "VENV_PY=build-env\Scripts\python.exe"

echo [*] Installing PyInstaller ...
"%VENV_PY%" -m pip install --upgrade --quiet pip || exit /b 1
"%VENV_PY%" -m pip install --upgrade --quiet pyinstaller || (
    echo [!] pip could not install PyInstaller. Check your connection/proxy.
    exit /b 1
)

rem --- optional UPX ----------------------------------------------------
set "UPX_ARG="
if not defined UPX_DIR if exist "upx\upx.exe" set "UPX_DIR=upx"
if defined UPX_DIR (
    if exist "%UPX_DIR%\upx.exe" (
        set "UPX_ARG=--upx-dir=%UPX_DIR%"
        echo [*] UPX found in %UPX_DIR% -- compressing.
    ) else (
        echo [!] UPX_DIR=%UPX_DIR% has no upx.exe -- building uncompressed.
    )
) else (
    echo [*] No UPX ^(optional^) -- building uncompressed.
)

rem --- build -----------------------------------------------------------
echo [*] Building ...
"%VENV_PY%" -m PyInstaller --noconfirm --clean %UPX_ARG% unit_converter.spec || (
    echo [!] Build failed. See the PyInstaller output above.
    exit /b 1
)

echo.
if defined UC_ONEDIR (
    echo [+] Done: dist\unit_converter\unit_converter.exe
    echo     Ship the whole dist\unit_converter\ folder ^(zip it^).
) else (
    for %%F in ("dist\unit_converter.exe") do echo [+] Done: %%~fF  ^(%%~zF bytes^)
    echo     Single portable file. unit_converter.ini is created beside it
    echo     on first run if you want custom units.
)
echo.
echo [*] Launch it once now to confirm it opens before you hand it out.
endlocal
