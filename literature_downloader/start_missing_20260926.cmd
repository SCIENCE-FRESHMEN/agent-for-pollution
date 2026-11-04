@echo off
REM ============================================================
REM  2026-09-26 文献缺口全自动下载（需先在弹出的 Chrome 里登录机构）
REM  双击运行即可：它会打开已登录的下载专用 Chrome（如已开着会复用），
REM  然后启动看门狗 supervisor 自动把 missing_20260926.csv 队列跑完。
REM ============================================================
cd /d "C:\Users\25416\Desktop\agent for pollution\literature_downloader"

set LIT_ROOT=C:\Users\25416\Desktop\agent for pollution\lit_workspace
set LIT_OUT=%LIT_ROOT%\literature\authorized_pdf_v2
set LIT_DIR=%LIT_ROOT%\literature
set LIT_LOG=%LIT_ROOT%\logs\authorized_browser_download_v2.csv
set LIT_STATE=%LIT_ROOT%\logs\v4_runner_state.json
set CHROME_BIN=C:\Program Files\Google\Chrome\Application\chrome.exe
set CHROME_PROFILE=C:\Users\25416\Desktop\agent for pollution\lit_workspace\browser_profile_authorized
set CDP_PORT=9222
set CDP_HTTP=http://127.0.0.1:9222
set QUEUE_PATH=C:\Users\25416\Desktop\agent for pollution\literature_downloader\missing_20260926.csv

REM 1) 确保 Chrome(CDP) 在跑：探测 9222，没有就拉起
python -c "import urllib.request,sys;urllib.request.urlopen('http://127.0.0.1:9222/json/version',timeout=3)" >nul 2>&1
if errorlevel 1 (
    echo Chrome CDP not running - launching...
    start "" python chrome_serve.py
    timeout /t 12 /nobreak >nul
)

echo.
echo ==========================================================
echo  如果浏览器窗口里还未登录机构，请现在在该 Chrome 里完成
echo  学校图书馆/机构登录一次，然后回到这里按任意键继续。
echo ==========================================================
pause

REM 2) 启动看门狗：分块跑队列、被封自动冷却、失败自动补跑
python supervisor.py
