@echo off
rem ============================================================
rem  Hermes Companion - Astro Boy standalone launcher
rem  Starts the black astro boy WITHOUT relay (local only)
rem  Just the pet, no fleet sync. Great for testing.
rem  No relay means no token is read or exported at all.
rem ============================================================
setlocal
set "HERMES_HOME=%LOCALAPPDATA%\hermes"
set "PYTHONPATH=%~dp0..\.."
set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
set "DEFAULT_COMPANION=astro"
set "DEFAULT_SCALE=0.85"

set "COMPANION=%DEFAULT_COMPANION%"
set "SCALE=%DEFAULT_SCALE%"
set "GRAB_FLAG="

:parse_args
if "%~1"=="" goto args_done
if "%~1"=="--grab" set "GRAB_FLAG=--grab"
if "%~1"=="--scale" shift & set "SCALE=%~1"
if "%~1"=="--companion" shift & set "COMPANION=%~1"
shift
goto parse_args

:args_done
start "Hermes Companion Astro Boy" "%PY%" -m hermes_companion live --companion %COMPANION% --scale %SCALE% %GRAB_FLAG% %*
endlocal
