@echo off
cd /d "%~dp0"

echo ============================================
echo  Attendance / Work-pattern App
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo Please install Python from https://www.python.org/downloads/
    echo During setup, make sure to check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

if not exist venv (
    echo First run: setting up now, this can take a few minutes...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting the app. A browser window will open automatically.
echo To stop, just close this window.
echo.

streamlit run app.py

pause
