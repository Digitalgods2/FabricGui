@echo off
REM Fabric GUI - Quick Start Script
REM First run: Creates venv and installs dependencies
REM Subsequent runs: Just activates venv and runs the app

cd /d "c:\Users\gosmo\OneDrive\Desktop\Code\Fabricgui"

REM Check if venv exists, create if not
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment!
        pause
        exit /b 1
    )
    
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies!
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

echo Starting Fabric GUI...
python fabricgui.py

REM Keep window open if app crashes
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
