@echo off
REM Double-click once: sets things up (first run only) and puts a
REM "Hermes Companion" icon on your desktop that opens Companion Home.
cd /d "%~dp0"
call "%~dp0Start-Companion.cmd" shortcut
if not errorlevel 1 timeout /t 5 >nul
