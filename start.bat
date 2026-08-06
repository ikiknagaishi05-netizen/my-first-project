@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  出勤簿・勤務形態一覧表 作成支援アプリ
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [エラー] Python が見つかりません。
    echo Python公式サイト(https://www.python.org/downloads/)からインストールしてください。
    echo インストール時に「Add python.exe to PATH」に必ずチェックを入れてください。
    echo.
    pause
    exit /b 1
)

if not exist venv (
    echo 初回起動のため、準備をします(数分かかります)...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo アプリを起動します。ブラウザが自動的に開きます。
echo 終了するには、このウィンドウを閉じてください。
echo.

streamlit run app.py

pause
