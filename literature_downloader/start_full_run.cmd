@echo off
REM ============================================================
REM Full-run launcher (2026-09-29). ASCII only to avoid cmd codepage bugs.
REM Queue = remaining_workbuddy.csv (2790 papers, strict Excel order)
REM Runs in its own window; log: _task_logs\supervisor_console.log
REM ============================================================
set LIT_ROOT=C:\Users\25416\Desktop\agent for pollution\lit_workspace
set LIT_OUT=%LIT_ROOT%\literature\authorized_pdf_v2
set LIT_DIR=%LIT_ROOT%\literature
set LIT_LOG=%LIT_ROOT%\logs\authorized_browser_download_v2.csv
set LIT_STATE=%LIT_ROOT%\logs\v4_runner_state.json
set CHROME_BIN=C:\Program Files\Google\Chrome\Application\chrome.exe
set CHROME_PROFILE=C:\Users\25416\Desktop\agent for pollution\lit_workspace\browser_profile_authorized
set CDP_PORT=9222
set CDP_HTTP=http://127.0.0.1:9222
set QUEUE_PATH=C:\Users\25416\Desktop\agent for pollution\literature_downloader\remaining_workbuddy.csv
set WORKSPACE=C:\Users\25416\Desktop\agent for pollution\literature_downloader
set PY_BIN=D:\anaconda3\python.exe
cd /d "C:\Users\25416\Desktop\agent for pollution\literature_downloader"

"D:\anaconda3\python.exe" -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:9222/json/version',timeout=3)" >nul 2>&1
if errorlevel 1 (
    echo Chrome CDP not running - launching...
    start "" "D:\anaconda3\python.exe" chrome_serve.py
    ping -n 16 127.0.0.1 >nul
)

echo [%date% %time%] supervisor starting, queue=remaining_workbuddy.csv (2790)
"D:\anaconda3\python.exe" supervisor.py
