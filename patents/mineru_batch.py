# -*- coding: utf-8 -*-
"""MinerU 远程批驱动：提交全部扫描件(--remote standard)，轮询完成，导出 markdown 至 txt/<pub>_mineru.md
checkpoint: mineru_jobs.json {pub: {job, doc, status}}
"""
import os, sys, io, csv, json, re, time, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
MINERU = os.path.join(BASE, "..", ".rc_venv", "Scripts", "mineru.exe")
MINERU = os.path.abspath(MINERU)
JOBS = os.path.join(BASE, "mineru_jobs.json")

def scans():
    rows = list(csv.DictReader(open(os.path.join(BASE, "extract_manifest.csv"), encoding="utf-8-sig")))
    low = [r["file"][:-4] for r in rows if int(r["chars"] or 0) < 200]
    man = {r["file"][:-4]: r for r in rows}
    if "CN102770542A" not in low and "read:" in (man.get("CN102770542A", {}).get("error") or ""):
        low.append("CN102770542A")
    return sorted(set(low))

def run(args, timeout=240):
    try:
        r = subprocess.run([MINERU] + args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="ignore")
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return -1, "timeout"

jobs = json.load(open(JOBS, encoding="utf-8")) if os.path.exists(JOBS) else {}
todo = [p for p in scans() if p not in jobs]
print(f"[mineru] to submit: {len(todo)}", flush=True)
t0 = time.time()
for i, pub in enumerate(todo, 1):
    code, out = run(["parse", os.path.join(BASE, "pdf", pub + ".pdf"), "--pages", "all", "--remote",
                     "-f", "markdown", "-o", os.path.join(BASE, "mineru_out", pub), "--no-wait"], timeout=180)
    m = re.search(r"解析任务 ID:\s*(\d+)", out)
    jobs[pub] = {"job": m.group(1) if m else None, "status": "submitted" if m else f"submit_fail:{out[:60]}"}
    json.dump(jobs, open(JOBS, "w", encoding="utf-8"), ensure_ascii=False)
    if i % 10 == 0 or i == len(todo):
        print(f"[mineru] submitted {i}/{len(todo)} elapsed={time.time()-t0:.0f}s", flush=True)

# 轮询导出
print("[mineru] polling...", flush=True)
deadline = time.time() + 3.5 * 3600
while time.time() < deadline:
    pending = [p for p, j in jobs.items() if j.get("status") not in ("exported", "failed")]
    if not pending:
        break
    code, out = run(["list", "parses"], timeout=120)
    for pub in pending:
        j = jobs[pub]
        if j.get("status") == "exported":
            continue
        jid = j.get("job")
        if not jid:
            continue
        if re.search(rf"解析 {jid}:\s*done", out):
            # doc id = sha prefix；从 show 里取
            code2, out2 = run(["show", "parse", jid], timeout=120)
            msha = re.search(r"SHA-256.{2,}([0-9a-f]{8,})", out2.replace("│", " ").replace("├", " ").replace("└", " "))
            if msha:
                doc = msha.group(1)[:8]
                code3, out3 = run(["read", f"doc:{doc}", "-f", "markdown", "-o",
                                   os.path.join(BASE, "txt", pub + "_mineru.md"), "--limit", "200000"], timeout=180)
                if code3 == 0 and os.path.exists(os.path.join(BASE, "txt", pub + "_mineru.md")):
                    j["status"] = "exported"; j["doc"] = doc
                else:
                    j["status"] = f"export_fail:{out3[:60]}"
            else:
                j["status"] = "no_sha"
    json.dump(jobs, open(JOBS, "w", encoding="utf-8"), ensure_ascii=False)
    done = sum(1 for j in jobs.values() if j.get("status") == "exported")
    print(f"[mineru] exported={done}/{len(jobs)} elapsed={time.time()-t0:.0f}s", flush=True)
    time.sleep(120)
print("[mineru] POLLING END", flush=True)
