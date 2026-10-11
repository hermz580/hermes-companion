@echo off
REM One-click: installs Hermes Companion into .venv (first run only) and
REM starts Nyamekra, the All-Doing Crow, on your desktop. No Hermes install needed.
REM
REM   Start-Companion.cmd                              Nyamekra
REM   Start-Companion.cmd herald                       Herald (winged messenger)
REM   Start-Companion.cmd nia                          Nia (storyteller)
REM   Start-Companion.cmd samurai / astro
REM   Start-Companion.cmd --palette fire --size large  Nyamekra with options
REM   Start-Companion.cmd nia --palette indigo         any companion + options
REM   Start-Companion.cmd live                         Nyamekra driven by your real Hermes
REM   Start-Companion.cmd live nia                     any companion, live
REM   Start-Companion.cmd --reduced-motion --high-contrast   accessibility
REM   Start-Companion.cmd doctor                       check this PC can run it
REM   Start-Companion.cmd home                         open Companion Home (all settings)
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ---- install (repeats until it has fully succeeded once) --------------------
if not exist ".venv\installed.ok" (
    echo Setting up Hermes Companion, one moment...
    if not exist ".venv\Scripts\python.exe" (
        py -3 -m venv .venv 2>nul || python -m venv .venv
    )
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo Python 3.10 or newer is required. Get it from https://www.python.org/downloads/
        echo During install, tick "Add python.exe to PATH". Then run this again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
    if errorlevel 1 (
        echo Your Python is older than 3.10. Install a newer one from python.org, delete the .venv folder, and run this again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -e .
    if errorlevel 1 (
        echo.
        echo Install failed. Check your internet connection and run this again.
        pause
        exit /b 1
    )
    echo ok> ".venv\installed.ok"
)

REM ---- what to run -------------------------------------------------------------
set "FIRST=%~1"
if /i "%FIRST%"=="doctor" (
    ".venv\Scripts\python.exe" -m hermes_companion doctor
    pause
    exit /b %ERRORLEVEL%
)
if /i "%FIRST%"=="home" (
    start "" ".venv\Scripts\pythonw.exe" -m hermes_companion home
    exit /b 0
)
set "MODE=play"
if /i "%FIRST%"=="live" (
    set "MODE=live"
    shift
)
set "WHO=nyamekra"
set "NEXT=%~1"
if defined NEXT if not "!NEXT:~0,1!"=="-" (
    set "WHO=%NEXT%"
    shift
)
set "REST="
:collect
if "%~1"=="" goto run
set "REST=!REST! %1"
shift
goto collect

:run
if "%MODE%"=="live" (
    echo Connecting %WHO% to Hermes. Close this window to stop it.
    if not exist ".venv\live.ok" (
        ".venv\Scripts\python.exe" hermes_companion\plugin\install.py
        if not errorlevel 1 echo ok> ".venv\live.ok"
    )
    ".venv\Scripts\python.exe" -m hermes_companion live --companion %WHO% --follow %REST%
) else (
    echo Starting %WHO%. Close this window to stop it.
    ".venv\Scripts\python.exe" -m hermes_companion play --companion %WHO% %REST%
)
if errorlevel 1 (
    echo.
    echo Something went wrong. Run "Start-Companion.cmd doctor" and send the output.
    pause
)
