@echo off
setlocal
set "HERMES_HOME=%LOCALAPPDATA%\hermes"
set "PYTHONPATH=%~dp0.."
set "HERMES=%USERPROFILE%\bin\hermes.cmd"
set "PROJECT=%~dp0"
set "LOG=%~dp0\live-demo-restart.log"

echo [%date% %time%] Starting Hermes Companion live demo > "%LOG%"
echo Stopping stale gateway... >> "%LOG%"
call "%HERMES%" gateway stop >> "%LOG%" 2>&1
timeout /t 3 /nobreak >nul

echo Installing and enabling companion while gateway is stopped... >> "%LOG%"
python "%PROJECT%\plugin\install.py" >> "%LOG%" 2>&1

echo Starting fresh gateway... >> "%LOG%"
call "%HERMES%" gateway start >> "%LOG%" 2>&1
timeout /t 8 /nobreak >nul

echo Launching The Alpha And live overlay... >> "%LOG%"
start "Hermes Companion - The Alpha And" /min cmd.exe /c "set HERMES_HOME=%HERMES_HOME%&& set PYTHONPATH=%PYTHONPATH%&& cd /d %~dp0..&& python -m hermes_companion live >> \"%LOG%\" 2>&1"
timeout /t 4 /nobreak >nul

echo Triggering a real 8-second Hermes terminal tool call... >> "%LOG%"
call "%HERMES%" chat -q "Use the terminal tool exactly once to run: sleep 8 && echo alpha_live_demo_complete. Then reply with exactly alpha_live_demo_complete." --toolsets terminal --quiet >> "%LOG%" 2>&1

echo [%date% %time%] Demo task complete. Overlay remains running. >> "%LOG%"
endlocal
