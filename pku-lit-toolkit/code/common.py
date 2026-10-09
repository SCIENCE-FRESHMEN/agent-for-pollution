# -*- coding: utf-8 -*-
"""公共工具：包根路径、配置加载、DOI 文件名、日志"""
import io, sys, json, re, csv, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOGS = ROOT / "logs"
DL = ROOT / "downloads"
STAGING = ROOT / "logs" / "staging"

def out_utf8():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

def load_config():
    cfg = json.load(open(ROOT / "config.json", encoding="utf-8"))
    for k in ("institution_zh", "username"):
        v = str(cfg.get(k, "")).strip()
        if not v or "在这里填" in v:
            raise SystemExit("[配置] 请先编辑 config.json，填好机构名称、账号 再运行。")
    return cfg

def queue_path(cfg):
    p = Path(cfg["queue"])
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        raise SystemExit(f"[配置] 队列文件不存在: {p}")
    return p

def sn(doi):
    return re.sub(r'[<>:"/\\|?*]', "_", doi).lower()

def safe_dir(name):
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', " ", str(name)).strip().rstrip(".")
    return (re.sub(r"\s+", " ", s)[:80]) or "Unknown"

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")

class RunLog:
    """logs/run.log 追加 + 控制台同步"""
    def __init__(self):
        LOGS.mkdir(parents=True, exist_ok=True)
    def __call__(self, *a):
        line = time.strftime("[%H:%M:%S] ") + " ".join(str(x) for x in a)
        print(line, flush=True)
        with open(LOGS / "run.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

def append_csv(path, header, row):
    new = not Path(path).exists()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerow(row)

def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}

def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False)
