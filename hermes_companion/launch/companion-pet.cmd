@echo off
rem ============================================================
rem  Hermes Companion - Pet launcher (daily use)
rem  Starts The Alpha And overlay WITH grab enabled, auto-joined
rem  to the local relay (127.0.0.1:49000) so desktop + laptop
rem  pets animate the same events and move together.
rem  Requires the relay to be running (companion-relay.cmd / auto-start).
rem  The relay token is exported as HERMES_COMPANION_TOKEN, never passed
rem  on the command line, so it cannot be read from the process list.
rem ============================================================
setlocal
set "HERMES_HOME=%LOCALAPPDATA%\hermes"
set "PYTHONPATH=%~dp0..\.."
set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
set "TOKEN_FILE=%LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt"

if not exist "%TOKEN_FILE%" (
  echo Token file missing. Start the relay once via companion-relay.cmd to generate it.
  exit /b 1
)
set /p HERMES_COMPANION_TOKEN=<"%TOKEN_FILE%"

start "Hermes Companion Pet" "%PY%" -m hermes_companion live --grab --relay 127.0.0.1:49000 %*
endlocal
