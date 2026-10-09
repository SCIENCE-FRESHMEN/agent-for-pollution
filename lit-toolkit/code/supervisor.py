# -*- coding: utf-8 -*-
"""总控（看门狗）：登录 → 反复跑 sweeper → 会话失效自动重登 → 限速自动冷却 → 完成【下载报告.md】
用法：python code/supervisor.py     （或双击 开始下载.cmd）
"""
import csv, os, sys, time, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import out_utf8, load_config, queue_path, RunLog, LOGS, ROOT, DL
out_utf8()
log = RunLog()
import chrome_ctl

PY = sys.executable
TL = Path(__file__).resolve().parent
FLOG = LOGS / "sweeper_log.csv"

def log_rows():
    try:
        with open(FLOG, encoding="utf-8-sig", errors="replace") as f:
            return [r for r in csv.reader(f) if r and r[0] != "序号" and len(r) >= 4]
    except Exception:
        return []

def count_disk():
    n = 0
    for _ in DL.rglob("*.pdf"):
        n += 1
    return n

def run(cmd, timeout=None, cwd=TL):
    return subprocess.run([PY, "-X", "utf8"] + cmd, cwd=cwd, timeout=timeout)

def main():
    cfg = load_config()
    qp = queue_path(cfg)
    n_queue = sum(1 for r in csv.DictReader(open(qp, encoding="utf-8-sig", newline=""))
                  if (r.get("DOI") or r.get("doi") or "").strip())
    log(f"=== 工具包启动 | 机构: {cfg['institution_zh']} | 队列 {qp.name}: {n_queue} 篇 ===")

    # 环境自检
    try:
        import playwright, requests, openpyxl, numpy, PIL  # noqa
    except ImportError as e:
        raise SystemExit(f"[环境] 缺少依赖: {e.name}。请先执行: pip install -r requirements.txt")
    chrome_ctl.ensure_chrome(cfg, log)

    # 登录（自动 → 人工兜底；其他出版社一次性人工清单）
    run(["auth.py"], timeout=3600, cwd=TL)

    blk_limit = int(cfg.get("block_streak_relogin", 12))
    fnp_limit = int(cfg.get("fnp_streak_cooldown", 5))
    cooldown = int(cfg.get("cooldown_minutes", 25)) * 60

    rnd = 0
    while True:
        rnd += 1
        rows = log_rows()
        done = len(rows)
        log(f"=== 第 {rnd} 轮 | 已处理 {done}/{n_queue} | 磁盘 {count_disk()} 篇 ===")
        if done >= n_queue:
            break
        proc = subprocess.Popen([PY, "-X", "utf8", str(TL / "sweeper.py"), str(qp)],
                                cwd=str(TL), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        streak_blk = streak_fnp = 0
        last_n = done
        while proc.poll() is None:
            time.sleep(60)
            rows = log_rows()
            n = len(rows)
            for r in rows[last_n:]:
                st = r[3]
                if st.startswith("blocked:no-view-pdf-entry"):
                    streak_blk += 1
                    streak_fnp = 0
                elif st.startswith("failed_no_pdf"):
                    streak_fnp += 1
                    streak_blk = 0
                elif st.startswith("downloaded"):
                    streak_blk = streak_fnp = 0
            last_n = n
            log(f"  进度 {n}/{n_queue}（blk串={streak_blk} fnp串={streak_fnp}）")
            if n >= n_queue:
                break
            if streak_blk >= blk_limit:
                log("!! 连续无权限 → 机构会话疑似失效，停车重登")
                kill_sweeper()
                break
            if streak_fnp >= fnp_limit:
                log("!! 连续限速 → 冷却")
                kill_sweeper()
                break
        kill_sweeper()  # 无论哪种退出都确保 sweeper 停干净
        if last_n >= n_queue:
            break
        # 故障处理
        if streak_blk >= blk_limit:
            time.sleep(120)
            run(["auth.py"], timeout=3600, cwd=TL)
        elif streak_fnp >= fnp_limit:
            log(f"冷却 {cfg.get('cooldown_minutes', 25)} 分钟 ...")
            time.sleep(cooldown)
        if not chrome_ctl.cdp_alive():
            chrome_ctl.ensure_chrome(cfg, log)

    log("=== 队列消费完毕，生成报告 ===")
    run(["report.py"], timeout=600, cwd=TL)
    log(f"=== 完成！PDF 共 {count_disk()} 篇，位于 downloads/ 文件夹 ===")

def kill_sweeper():
    subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*sweeper.py*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
        capture_output=True)
    time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("已手动停止。再次运行会自动跳过已下载文献，从断点继续。")
