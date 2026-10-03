@echo off
REM Lets you type "hermes-companion ..." inside this folder (uses .venv).
REM Run Start-Companion.cmd once first so .venv exists.
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Run Start-Companion.cmd once first to set things up.
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -m hermes_companion %*
