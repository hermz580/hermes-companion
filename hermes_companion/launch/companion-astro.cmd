@echo off
rem ============================================================
rem  Hermes Companion - Astro Boy launcher
rem  Starts the BLACK ASTRO BOY overlay with LED eyes,
rem  chrome limbs, and futuristic HUD aesthetic.
rem  Default companion: astro (change with --companion)
rem  Supports: --grab, --relay, --scale, --companion
rem  The relay token is exported as HERMES_COMPANION_TOKEN, never passed
rem  on the command line, so it cannot be read from the process list.
rem ============================================================
setlocal
set "HERMES_HOME=%LOCALAPPDATA%\hermes"
set "PYTHONPATH=%~dp0..\.."
set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
set "TOKEN_FILE=%LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt"
set "DEFAULT_COMPANION=astro"
set "DEFAULT_SCALE=0.85"

rem Parse args
set "COMPANION=%DEFAULT_COMPANION%"
set "SCALE=%DEFAULT_SCALE%"
set "GRAB_FLAG="
set "RELAY_TARGET=127.0.0.1:49000"

:parse_args
if "%~1"=="" goto args_done
if "%~1"=="--grab" set "GRAB_FLAG=--grab"
if "%~1"=="--relay" shift & set "RELAY_TARGET=%~1"
if "%~1"=="--scale" shift & set "SCALE=%~1"
if "%~1"=="--companion" shift & set "COMPANION=%~1"
shift
goto parse_args

:args_done
if not exist "%TOKEN_FILE%" (
  echo Token file missing. Start the relay once via companion-relay.cmd to generate it.
  exit /b 1
)
set /p HERMES_COMPANION_TOKEN=<"%TOKEN_FILE%"

if "%GRAB_FLAG%"=="" (
  start "Hermes Companion Astro Boy" "%PY%" -m hermes_companion live --companion %COMPANION% --scale %SCALE% --relay %RELAY_TARGET% %*
) else (
  start "Hermes Companion Astro Boy" "%PY%" -m hermes_companion live --companion %COMPANION% --scale %SCALE% --grab --relay %RELAY_TARGET% %*
)
endlocal
