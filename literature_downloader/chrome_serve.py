# -*- coding: utf-8 -*-
"""启动真实 Chrome（已登录 profile + CDP），并作为后台任务常驻。"""
import subprocess, time, sys, io, json, urllib.request, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# 路径均可经环境变量覆盖（见 config.example.env）
CHROME = os.environ.get("CHROME_BIN", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE = os.environ.get("CHROME_PROFILE", r"D:\Compatible_solute_project\browser_profile_authorized")
PORT = int(os.environ.get("CDP_PORT", "9222"))

cmd = [
    CHROME,
    f"--user-data-dir={PROFILE}",
    f"--remote-debugging-port={PORT}",
    "--remote-allow-origins=*",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
    "--disable-features=Translate",
    "--start-maximized",
    # 本机必须直连（Clash 系统代理会把出版社流量送到海外出口）且禁用扩展
    # （McAfee WebAdvisor 等会造成间歇性 ERR_BLOCKED_BY_CLIENT）
    "--proxy-server=direct://",
    "--proxy-bypass-list=<-loopback>",
    "--disable-extensions",
]

print("launching real Chrome (authorized profile), detached", flush=True)
p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, close_fds=True)
print("chrome pid:", p.pid, flush=True)

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ready = False
for i in range(60):
    time.sleep(1)
    try:
        with opener.open(f"http://127.0.0.1:{PORT}/json/version", timeout=3) as r:
            info = json.loads(r.read().decode("utf-8", "replace"))
        print("CDP READY:", info.get("Browser"), flush=True)
        print("WS:", info.get("webSocketDebuggerUrl"), flush=True)
        ready = True
        break
    except Exception as e:
        if i % 10 == 0:
            print(f"  waiting {i}s ...", flush=True)

if not ready:
    print("CDP NOT READY", flush=True)
    sys.exit(1)

# 常驻：每 10s 打印一次心跳，保持后台任务存活
print("=== Chrome session live, keeping alive ===", flush=True)
n = 0
while True:
    time.sleep(10)
    n += 1
    if p.poll() is not None:
        print("chrome exited, code:", p.returncode, flush=True)
        break
    if n % 30 == 0:
        print(f"heartbeat {n*10}s alive", flush=True)
