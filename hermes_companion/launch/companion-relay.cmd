@echo off
rem ============================================================
rem  Hermes Companion - LAN Relay launcher
rem  Runs the ONE relay for the fleet (desktop = always-on box).
rem  Token: read from %LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt
rem         (created on first run; share this file with the laptop)
rem  The token is exported as HERMES_COMPANION_TOKEN, never passed on the
rem  command line, so it cannot be read out of the process command line.
rem  Log:   %LOCALAPPDATA%\hermes\companion\relay.log
rem ============================================================
setlocal
set "HERMES_HOME=%LOCALAPPDATA%\hermes"
set "PYTHONPATH=%~dp0..\.."
set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
set "TOKEN_FILE=%LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt"
set "LOG=%HERMES_HOME%\companion\relay.log"

if not exist "%LOCALAPPDATA%\hermes\secrets\" mkdir "%LOCALAPPDATA%\hermes\secrets"
if not exist "%TOKEN_FILE%" (
  "%PY%" -c "import secrets,os; open(os.path.expandvars(r'%TOKEN_FILE%'),'w').write(secrets.token_hex(16))"
)
set /p HERMES_COMPANION_TOKEN=<"%TOKEN_FILE%"

echo [%date% %time%] Companion relay starting on port 49000 >> "%LOG%"
"%PY%" -m hermes_companion relay --host 0.0.0.0 --port 49000 >> "%LOG%" 2>&1
endlocal
