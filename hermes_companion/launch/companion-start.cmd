@echo off
rem ============================================================
rem  Hermes Companion - Start the Alpha (one double-click)
rem
rem  1. Binds the Alpha to the session Hermes is running RIGHT NOW
rem     (an explicit action by you; the id is printed below).
rem  2. Starts the visible overlay with grab + relay.
rem
rem  The companion only ever displays evidence from the session it is
rem  bound to, so run this whenever you start a new chat.
rem
rem  Flags:  --no-bind   keep the existing binding
rem          --no-relay  start without fleet sync
rem          --scale N   override sprite scale
rem  The relay token is exported via the environment, never on the
rem  command line, so it cannot be read from the process list.
rem ============================================================
setlocal
set "HERMES_HOME=%LOCALAPPDATA%\hermes"
set "PYTHONPATH=%~dp0..\.."
set "PYDIR=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts"
rem pythonw runs the overlay with no console window; the pet should never
rem leave a terminal sitting on the desktop. Fall back to python if absent.
if exist "%PYDIR%\pythonw.exe" (set "PY=%PYDIR%\pythonw.exe") else (set "PY=%PYDIR%\python.exe")
set "TOKEN_FILE=%LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt"

set "DO_BIND=1"
set "USE_RELAY=--relay 127.0.0.1:49000"
set "SCALE_ARG="
set "PET_ARGS="

:parse_args
if "%~1"=="" goto args_done
if "%~1"=="--no-bind" set "DO_BIND=0"
if "%~1"=="--no-relay" set "USE_RELAY="
if "%~1"=="--scale" shift & set "SCALE_ARG=--scale %~1"
set "PET_ARGS=%PET_ARGS% %~1"
shift
goto parse_args

:args_done

if "%DO_BIND%"=="1" (
  echo Binding the Alpha to the current session...
  "%PY%" -m hermes_companion bind
  if errorlevel 1 (
    echo.
    echo Could not determine the current session.
    echo Start a chat first, then run this again.
    exit /b 1
  )
  echo.
)

if not "%USE_RELAY%"=="" (
  if not exist "%TOKEN_FILE%" (
    echo Token file missing. Start the relay once via companion-relay.cmd to generate it.
    exit /b 1
  )
  set /p HERMES_COMPANION_TOKEN=<"%TOKEN_FILE%"
)

echo Starting the Alpha...
rem Capture the pet's own decision log. Without this the windowless overlay's
rem FOLLOWING / FOLLOW SWITCH / EVENT lines go nowhere, so a silently silent
rem companion and a working one look identical.
if not exist "%LOCALAPPDATA%\hermes\companion" mkdir "%LOCALAPPDATA%\hermes\companion"
start "Hermes Companion Pet" "%PY%" -m hermes_companion live --grab %USE_RELAY% %SCALE_ARG% > "%LOCALAPPDATA%\hermes\companion\pet-live.out.log" 2>&1
endlocal
