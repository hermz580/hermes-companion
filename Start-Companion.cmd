@echo off
REM One-click: installs Hermes Companion into .venv (first run only) and
REM starts a curious samurai on your desktop. No Hermes install needed.
REM   Start-Companion.cmd            samurai
REM   Start-Companion.cmd astro      astro
setlocal
cd /d "%~dp0"
set "WHO=%~1"
if "%WHO%"=="" set "WHO=samurai"

if not exist ".venv\Scripts\python.exe" (
    echo Setting up Python environment, one moment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo Python 3.10+ is required: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -e .
)

echo Starting %WHO%. Close this window to stop it.
".venv\Scripts\python.exe" -m hermes_companion play --companion %WHO%
