# -*- coding: utf-8 -*-
"""
无人值守看门狗：
1) 保活真实 Chrome（CDP 9222，已登录 profile），挂了自动拉起
2) 分块调用 downloader_v4.py，崩溃/卡死自动重启
3) 主队列跑完后，自动汇总失败项做补跑（最多 2 轮）
4) 全程写日志 logs/v4_supervisor.log
"""
import sys, io, os, csv, json, time, subprocess, urllib.request, re
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# 路径均可经环境变量覆盖（见 config.example.env）
PY = os.environ.get("PY_BIN", r"D:\anaconda\python.exe")
ROOT = Path(os.environ.get("LIT_ROOT", r"D:\Compatible_solute_project"))
LIT = ROOT / "literature"
OUT = LIT / "authorized_pdf_v2"
LOG = ROOT / "logs" / "authorized_browser_download_v2.csv"
SLOG = ROOT / "logs" / "v4_supervisor.log"
BASE = Path(os.environ.get("WORKSPACE", r"C:\Users\17965\WorkBuddy\2026-09-16-19-38-28"))
DL = BASE / "downloader_v4.py"
CHROME = os.environ.get("CHROME_BIN", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE = ROOT / "browser_profile_authorized"
CDP = os.environ.get("CDP_HTTP", "http://127.0.0.1:9222")
CHUNK = 400
# 保守节奏：30-45s/篇、每 40 篇休息 5 分钟、连续 3 篇失败即熔断
# 自适应档位：被封一次就降一档（放慢），连续跑顺则回升一档
PACE_LEVELS = [(15, 23), (35, 50), (70, 100), (120, 170)]
PACE_LEVELS_DESC = ["15-23s", "35-50s", "70-100s", "120-170s"]
# 起始档位可用环境变量覆盖（刚被封过就从 L1 起步更稳妥）
pace_level = int(os.environ.get("PACE_START", "1"))

def pace_args(level):
    lo, hi = PACE_LEVELS[min(level, len(PACE_LEVELS) - 1)]
    return ["--pause-min", str(lo), "--pause-max", str(hi),
            "--rest-every", "40", "--rest-sec", "300",
            "--max-consec-fail", "8"]

# 触发熔断后的冷却时间（秒）：歇够再自动续跑，不再直接停车
COOLDOWN = 1200
# 连续 3 次熔断 = 配额基本耗尽（此时重启浏览器也没用，是 IP 级），需要长休
QUOTA_REST = 3 * 3600

def w(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        with SLOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def chrome_alive():
    try:
        with opener().open(CDP + "/json/version", timeout=4) as r:
            return json.loads(r.read().decode()).get("Browser")
    except Exception:
        return None

def kill_chrome():
    """强制关闭 Chrome（清理被封的会话，重启后可能拿到新的 clearance）。"""
    w("强制关闭 Chrome ...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                       capture_output=True, timeout=90, shell=True)
    except Exception as e:
        w(f"  taskkill 异常: {e!r}")
    for i in range(20):
        time.sleep(2)
        if not chrome_alive():
            w(f"  Chrome 已关闭（{i*2}s）")
            return True
    w("  Chrome 仍在运行")
    return False

def restart_chrome_hard():
    kill_chrome()
    time.sleep(10)
    return start_chrome()

def start_chrome():
    if chrome_alive():
        return True
    w("Chrome 未运行，启动真实浏览器（已登录 profile）...")
    cmd = [CHROME, f"--user-data-dir={PROFILE}", "--remote-debugging-port=9222",
           "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
           "--disable-popup-blocking", "--disable-features=Translate", "--start-maximized",
           "--disable-extensions",
           "--proxy-server=direct://", "--proxy-bypass-list=<-loopback>"]
    DETACHED, NEWGROUP = 0x00000008, 0x00000200
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL,
                         creationflags=DETACHED | NEWGROUP, close_fds=True)
    except Exception as e:
        w(f"Chrome 启动失败: {e!r}")
        return False
    for i in range(60):
        time.sleep(1)
        if chrome_alive():
            w(f"Chrome 就绪: {chrome_alive()}")
            return True
    w("Chrome 启动超时")
    return False

def log_rows():
    if not LOG.exists():
        return 0
    try:
        with LOG.open(encoding="utf-8-sig", newline="") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0

def run_chunk(tag, queue=None, limit=CHUNK, level=0):
    args = [PY, str(DL), "--limit", str(limit), "--tag", tag] + pace_args(level)
    if queue:
        args += ["--queue", str(queue)]
    w(f"启动批次 {tag} (limit={limit}{', queue=' + str(queue) if queue else ''})")
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    last = log_rows()
    stall_since = time.time()
    out_lines = []
    picked = -1
    n_ok = 0
    while p.poll() is None:
        time.sleep(20)
        try:
            line = p.stdout.readline()
            if line:
                out_lines.append(line.rstrip())
                if len(out_lines) > 200:
                    out_lines.pop(0)
                # 逐行落盘，便于排查（熔断/异常不再黑箱）
                w("   dl| " + line.rstrip()[:150])
        except Exception:
            pass
        n = log_rows()
        if n > last:
            last = n
            stall_since = time.time()
        if line and "picked=" in line:
            try:
                picked = int(re.search(r"picked=(\d+)", line).group(1))
            except Exception:
                pass
        # 熔断联动：下载器判定再次被限速，看门狗必须一起停，绝不能重启硬顶
        if line and "触发熔断" in line:
            w("!! 检测到熔断（疑似再次被限速），看门狗整体停车")
            try: p.kill()
            except Exception: pass
            return "breaker", picked, n_ok
        elif time.time() - stall_since > 600:
            w(f"!! {tag} 停滞 10 分钟无新日志，重启批次")
            p.kill()
            time.sleep(2)
            start_chrome()
            return "stalled", picked, n_ok
        if not chrome_alive():
            w("!! Chrome 掉线，重启浏览器并重启批次")
            try: p.kill()
            except Exception: pass
            start_chrome()
            return "chrome_down"
    try:
        rest = p.stdout.read()
        if rest:
            out_lines += rest.splitlines()[-30:]
    except Exception:
        pass
    for l in out_lines:
        m = re.search(r"picked=(\d+)", l)
        if m:
            picked = int(m.group(1))
        m2 = re.search(r"^\s*downloaded:\s*(\d+)", l)
        if m2:
            n_ok = int(m2.group(1))
    # 熔断联动：下载器判定再次被限速，看门狗必须一起停，绝不能重启硬顶
    if any("触发熔断" in l for l in out_lines):
        w("!! 检测到熔断（疑似再次被限速），看门狗整体停车")
        try: p.kill()
        except Exception: pass
        return "breaker", picked, n_ok
    tail = [l for l in out_lines if l.strip()][-4:]
    for l in tail:
        w("   | " + l[:150])
    w(f"批次 {tag} 结束，picked={picked}，日志行数 {log_rows()}")
    return "done", picked, n_ok

def build_retry_csv(path, tag):
    """把日志中失败且本地仍无 PDF 的 DOI 汇总成重试队列。"""
    stems = {p.stem.lower() for p in LIT.rglob("*.pdf")}
    def sn(d): return re.sub(r'[<>:"/\\|?*]', "_", d).lower()
    seen, rows = set(), []
    if LOG.exists():
        with LOG.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                doi = (r.get("DOI") or "").strip()
                st = (r.get("状态") or "").strip()
                if not doi or doi in seen:
                    continue
                if st in ("downloaded", "skipped_exists"):
                    continue
                if sn(doi) in stems:
                    continue
                seen.add(doi)
                rows.append((doi, (r.get("标题") or "").strip(), (r.get("出版商") or "").strip()))
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["DOI", "Title", "Publisher"])
        for r in rows:
            wr.writerow(r)
    w(f"重试队列 {tag}: {len(rows)} 条 -> {path}")
    return len(rows)

def main():
    global pace_level
    delay = int(os.environ.get("INITIAL_DELAY", "0"))
    w("=" * 60)
    w("看门狗启动")
    if delay > 0:
        w(f"按计划先静默 {delay//3600} 小时 {(delay%3600)//60} 分钟，让 IP 配额恢复")
        time.sleep(delay)
        w("静默结束，开始下载")
    if not start_chrome():
        w("无法启动 Chrome，退出")
        return
    round_no = 0
    main_empty = False
    consec_breaker = 0
    while True:
        round_no += 1
        w(f"当前节奏档位 L{pace_level} ({PACE_LEVELS_DESC[min(pace_level,3)]}/篇)")
        res, picked, n_ok = run_chunk(f"auto_r{round_no}", level=pace_level)
        if res == "breaker":
            consec_breaker += 1
            w(f"熔断（连续第 {consec_breaker} 次），冷却 {COOLDOWN//60} 分钟")
            time.sleep(COOLDOWN)
            if consec_breaker >= 3:
                w(f"连续 3 次熔断 → 判定配额耗尽，长休 {QUOTA_REST//3600} 小时")
                time.sleep(QUOTA_REST)
                w("长休结束，重启浏览器换新会话后再跑")
                if restart_chrome_hard():
                    w("浏览器已重启，恢复下载")
                else:
                    w("浏览器重启失败，继续尝试")
                consec_breaker = 0
                # 长休后给一次机会回到较快的档位
                if pace_level > 1:
                    pace_level -= 1
                    w(f"回探档位 → L{pace_level} ({PACE_LEVELS_DESC[pace_level]}/篇)")
            else:
                w("冷却结束，恢复下载")
            # 被封说明太快，降一档
            if pace_level < len(PACE_LEVELS) - 1:
                pace_level += 1
                w(f"自适应降速 → 档位 L{pace_level} ({PACE_LEVELS_DESC[pace_level]}/篇)")
            continue
        if res == "done":
            consec_breaker = 0
            # 跑顺了则回升一档，但下限锁在 L1：
            # 实测 L0(15-23s) 连续下 24 篇就会被封，不再自动回到该档
            if n_ok >= 30 and pace_level > 1:
                pace_level -= 1
                w(f"运行顺畅，回升档位 → L{pace_level} ({PACE_LEVELS_DESC[pace_level]}/篇)")
        if res in ("stalled", "chrome_down"):
            time.sleep(15)
            continue
        if picked == 0:
            w("主队列已跑空（picked=0）")
            main_empty = True
            break
        if round_no > 400:
            w("达到轮次上限，停止。")
            break
        time.sleep(10)

    # 失败项补跑 3 轮（每轮前重建重试队列）
    for i in (1, 2, 3):
        n = build_retry_csv(BASE / f"retry_p{i}.csv", f"retry{i}")
        if n == 0:
            w("无剩余失败项，全部完成。")
            break
        for attempt in range(3):
            res, _, _ = run_chunk(f"retry{i}", queue=BASE / f"retry_p{i}.csv",
                                  limit=n, level=pace_level)
            if res == "breaker":
                w(f"补跑阶段熔断，冷却 {COOLDOWN//60} 分钟后重试")
                time.sleep(COOLDOWN)
                continue
            if res != "stalled":
                break
            time.sleep(20)

    w("=" * 60)
    w(f"全部结束。日志总行 {log_rows()}，目录 PDF {len(list(OUT.glob('*.pdf')))}")

if __name__ == "__main__":
    main()
