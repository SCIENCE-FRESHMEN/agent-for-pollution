@echo off
REM ============================================================
REM  PKU Literature Toolkit - one-click entry
REM  1) check python + deps  2) run supervisor
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python not found. Install Python 3.9+ from python.org first.
    pause
    exit /b 1
)

python -c "import playwright,requests,openpyxl,numpy,PIL" >nul 2>nul
if errorlevel 1 (
    echo [..] Installing dependencies, please wait ...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [X] pip install failed. Check your network / pip mirror.
        pause
        exit /b 1
    )
)

findstr /c:"在这里填" config.json >nul 2>nul
if not errorlevel 1 (
    echo ==================================================
    echo  [X] config.json is not configured yet.
    echo      Open config.json with Notepad, fill in:
    echo        username / password / email
    echo      Then run this file again.
    echo ==================================================
    pause
    exit /b 1
)

echo [OK] Starting supervisor. A dedicated Chrome window will open.
echo      Follow console prompts to log in ONCE if asked.
python -X utf8 code\supervisor.py
pause
