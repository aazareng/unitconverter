@echo off
rem ---------------------------------------------------------------------
rem  Build UnitConverter.exe (the C# port) -> dist\UnitConverter.exe
rem
rem  Uses the C# compiler that is part of Windows itself (.NET Framework
rem  4.x, present on every Windows 10/11 machine), so nothing needs to be
rem  installed. The result is a ~30 KB exe that needs no runtime shipped
rem  alongside it. Compare: the PyInstaller build is ~9 MB.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    echo [!] csc.exe not found. .NET Framework 4.x should be part of Windows;
    echo     enable it under "Turn Windows features on or off".
    exit /b 1
)

if not exist dist mkdir dist

"%CSC%" -nologo -optimize+ -target:winexe -codepage:65001 ^
    -win32manifest:UnitConverter.manifest ^
    -r:System.Windows.Forms.dll -r:System.Drawing.dll ^
    -out:dist\UnitConverter.exe UnitConverter.cs
if errorlevel 1 (
    echo [!] Build failed.
    exit /b 1
)

for %%F in ("dist\UnitConverter.exe") do echo [+] Done: %%~fF  ^(%%~zF bytes^)
endlocal
