@echo off
REM Canonical test command for hermes_companion.
REM
REM   run-tests.cmd                                  full suite
REM   run-tests.cmd tests\test_pet_rows.py -q        pass flags through
REM
REM Picks the first interpreter that ACTUALLY has pytest. The interpreter first
REM on PATH is often a venv that does not (a Hermes venv, for instance), and an
REM earlier version of this script both picked that one and returned 0 anyway -
REM a test command that reports success while running nothing.
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PYEXE="
for %%C in ("%LOCALAPPDATA%\Programs\Python\Python313\python.exe" python py) do (
    if not defined PYEXE (
        %%~C -c "import pytest" >nul 2>&1 && set "PYEXE=%%~C"
    )
)

if not defined PYEXE (
    echo run-tests: no interpreter with pytest found. 1>&2
    echo   tried: %LOCALAPPDATA%\Programs\Python\Python313\python.exe, python, py 1>&2
    echo   fix:   python -m pip install pytest 1>&2
    exit /b 2
)

"%PYEXE%" -m pytest %*
exit /b %ERRORLEVEL%
