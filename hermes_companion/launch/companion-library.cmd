@echo off
setlocal
rem Local library only: no relay, sensing, agent launch, or live pet changes.
for %%I in ("%~dp0..\..") do set "PYTHONPATH=%%~fI"
set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Hermes Python was not found at "%PY%".
  echo Run python -m hermes_companion.renderer.companion_library from the repository parent instead.
  exit /b 1
)
"%PY%" -m hermes_companion.renderer.companion_library %*
exit /b %ERRORLEVEL%
