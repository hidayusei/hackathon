@echo off
setlocal
cd /d "%~dp0"

set "DESKMATE_PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%DESKMATE_PYTHON%" (
    echo DeskMate virtual environment was not found.
    echo Run the project setup first, then try again.
    pause
    exit /b 1
)

if "%~1"=="" (
    "%DESKMATE_PYTHON%" -m deskmate --demo
) else (
    "%DESKMATE_PYTHON%" -m deskmate %*
)

set "DESKMATE_EXIT=%ERRORLEVEL%"
if not "%DESKMATE_EXIT%"=="0" pause
exit /b %DESKMATE_EXIT%
