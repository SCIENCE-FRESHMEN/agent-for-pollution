# -*- coding: utf-8 -*-
"""Export reading table for the 221 compliant patents + fix missing record + stats."""
import os, sys, io, csv, json
from collections import Counter, defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import openpyxl

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")

with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = json.load(f)

# fix: CN102770542A failed to read -> unverifiable row
if not any(r["pub"] == "CN102770542A" for r in recs):
    recs.append({"pub": "CN102770542A", "chars": 0, "phrase_count": 0, "zh_term_count": 0,
                 "criterion": "", "compatible_count": 0, "solute_count": 0,
                 "verdict": "无法校验(文件读取失败)", "title": "", "assignee": "", "applicant_extra": "",
                 "priority": "", "filing": "", "publication": "", "inventor": "", "country": "CN",
                 "solutes": "", "themes": "", "ipc_cpc": "", "snippets": []})
with open(os.path.join(AN, "grounding_records.json"), "w", encoding="utf-8") as f:
    json.dump(recs, f, ensure_ascii=False)

# full detail csv (all 410)
with open(os.path.join(AN, "compliance.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=[k for k in recs[0] if k != "snippets"], extrasaction="ignore")
    w.writeheader()
    for r in recs:
        w.writerow({k: v for k, v in r.items() if k != "snippets"})

# sha256 from download status for provenance
sha = {}
p = os.path.join(BASE, "patent_pdf_download_status.csv")
if os.path.exists(p):
    with open(p, encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            sha[row["publication_number"]] = row.get("sha256", "")
with open(os.path.join(AN, "sha256_index.json"), "w", encoding="utf-8") as f:
    json.dump(sha, f)

passing = [r for r in recs if r["verdict"] == "纳入"]

def year(r):
    for k in ("publication", "filing", "priority"):
        v = (r.get(k) or "")[:4]
        if v.isdigit():
            return v
    return "?"

def clean_assignee(a):
    a = (a or "").strip()
    return a if a else "（元数据缺失）"

# ---------- reading table (markdown) ----------
lines = ["| # | 公开号 | 国 | 年 | 申请人 | 标题 | 校验依据 | 检出溶质 | 短语次数 |",
         "|---|--------|----|----|--------|------|----------|----------|----------|"]
for i, r in enumerate(sorted(passing, key=lambda x: (x["country"], x["pub"])), 1):
    crit = {"EN完整词组命中": "EN", "中文等价术语命中(相容性溶质)": "ZH", "EN词组+中文术语均命中": "EN+ZH"}.get(r["criterion"], "EU")
    sol = r["solutes"].replace("四氢嘧啶/tetrahydropyrimidine(中文语境)", "THP").replace("betaine(unspecified)", "betaine").replace("glycine betaine", "GB").replace("di-myo-inositol-phosphate", "DIP").replace("hydroxyectoine", "Hect").replace("mannosylglycerol", "MG").replace("glucosylglycerol", "GG").replace("dimsqrt", "DGP")
    title = (r["title"] or "（元数据缺失）").replace("|", "/")[:90]
    lines.append(f"| {i} | {r['pub']} | {r['country']} | {year(r)} | {clean_assignee(r['assignee'])[:40]} | {title} | {crit} | {sol[:60]} | {r['phrase_count'] + r['zh_term_count']} |")
with open(os.path.join(AN, "review_table.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# ---------- stats ----------
yc = Counter(year(r) for r in passing)
print("PASS-YEAR:", dict(sorted(yc.items())))
ac = Counter(clean_assignee(r["assignee"]) for r in passing)
print("\nTOP-APPLICANT:")
for a, n in ac.most_common(25):
    print(f"  {n:3d}  {a}")
ipc = Counter()
for r in passing:
    for c in r["ipc_cpc"].split(";"):
        if c:
            ipc[c.split(" ")[0][:4]] += 1
print("\nTOP-IPC4:")
for c, n in ipc.most_common(20):
    print(f"  {n:3d}  {c}")
# excluded detail
print("\nEXCLUDED-BY-CRITERION:")
for k, n in Counter((r["verdict"], r["criterion"]) for r in recs if r["verdict"] == "剔除").most_common():
    print("  ", k, n)
unv = [r["pub"] for r in recs if r["verdict"].startswith("无法校验")]
print("\nUNVERIFIABLE count:", len(unv))
print("\nSINGLE-WORD-ONLY:")
for r in recs:
    if r["verdict"] == "剔除" and "仅单词" in r["criterion"]:
        print("  ", r["pub"], "|", (r["title"] or "")[:70])
