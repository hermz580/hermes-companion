@echo off
rem ============================================================
rem  Hermes Companion - Multi-Companion Launcher
rem  Lets you choose between ALL companions:
rem    pet    - the original round green pet
rem    samurai - tall lanky ronin with swords
rem    astro   - black astro boy with LED eyes (DEFAULT)
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

echo.
echo  Hermes Companion - Choose Your Pet
echo  ===================================
echo  [1] Original Round Pet (green)
echo  [2] Samurai (tall ronin)
echo  [3] Astro Boy (black, LED eyes)
echo  [4] Default: Astro Boy
echo.
set /p CHOICE=Select (1-4, default=4): 

set "COMP=astro"
if "%CHOICE%"=="1" set "COMP=pet"
if "%CHOICE%"=="2" set "COMP=samurai"
if "%CHOICE%"=="3" set "COMP=astro"

echo Starting companion: %COMP%
"%PY%" -m hermes_companion live --companion %COMP% --scale 0.85 --relay 127.0.0.1:49000 %*
endlocal
