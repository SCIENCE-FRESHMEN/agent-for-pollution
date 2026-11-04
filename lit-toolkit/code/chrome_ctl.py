# -*- coding: utf-8 -*-
"""专用 Chrome 启动/重启/状态检查（CDP 9222）"""
import os, time, json, subprocess, urllib.request
from pathlib import Path

PORT = 9222
CDP = f"http://127.0.0.1:{PORT}"
# 专用 profile 放在工具包内，与同学生日常用的 Chrome 完全隔离
def profile_dir():
    return Path(__file__).resolve().parents[1] / "logs" / "chrome_profile"

def cdp_alive(timeout=4):
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=timeout)
        return True
    except Exception:
        return False

def kill_toolkit_chrome():
    """只杀本工具包启动的 Chrome（按专用 profile 识别），不影响日常浏览器"""
    marker = str(profile_dir())
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
          f"Where-Object {{ $_.CommandLine -like '*{marker}*' }} | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    time.sleep(2)

def launch_chrome(cfg, log=print):
    chrome = cfg.get("chrome_path") or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not Path(chrome).exists():
        raise SystemExit(f"[Chrome] 找不到 Chrome: {chrome}，请在 config.json 的 chrome_path 修改。")
    profile_dir().mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome,
        f"--user-data-dir={profile_dir()}",
        f"--remote-debugging-port={PORT}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--disable-features=Translate",
        "--start-maximized",
        "--disable-extensions",
    ]
    log("[chrome] 启动专用 Chrome ...")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, close_fds=True)
    for _ in range(40):
        time.sleep(1)
        if cdp_alive(2):
            log("[chrome] CDP 就绪")
            return True
    log("[chrome] CDP 未就绪")
    return False

def ensure_chrome(cfg, log=print):
    if cdp_alive():
        return True
    kill_toolkit_chrome()
    return launch_chrome(cfg, log)
