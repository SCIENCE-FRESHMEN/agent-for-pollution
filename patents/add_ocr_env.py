# -*- coding: utf-8 -*-
"""OCR 新发现 4 件环境专利并入子库 + 全链重跑 + 提取投加剂量"""
import os, sys, io, shutil, csv, json, re, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = r"C:\Users\25416\Desktop\agent for pollution"
PY = os.path.join(ROOT, ".rc_venv", "Scripts", "python.exe")
PAT = os.path.join(ROOT, "patents")
ENV = os.path.join(PAT, "RAG", "产出", "环境工程专利")
INC = os.path.join(PAT, "RAG", "产出", "RAG知识库", "env_increment")

NEW = [
 ("CN102517306B", "01e_OCR新增_环境核心", "四氢嘧啶合成酶基因/重组工程菌——耐盐性高，处理高盐废水无需驯化（基因工程产溶质菌×高盐废水，环境词频90）"),
 ("CN106148422A", "01e_OCR新增_环境核心", "餐厨垃圾厌氧发酵投加甜菜碱复合剂提高耐盐与产气（投加型·厌氧消化）"),
 ("CN106047942A", "01e_OCR新增_环境核心", "餐厨垃圾厌氧发酵添加四氢嘧啶提高耐盐与产气（投加型·剂量案例）"),
 ("CN101173237A", "01c_已入库PDF_沼气资源化边缘", "嗜盐菌生物挤奶高渗废液循环再利用（资源化）"),
]
d = os.path.join(ENV, "01e_OCR新增_环境核心")
os.makedirs(d, exist_ok=True)
for pub, cls, why in NEW:
    shutil.copy(os.path.join(PAT, "pdf", pub + ".pdf"), os.path.join(d, pub + ".pdf"))

rows = list(csv.DictReader(open(os.path.join(ENV, "环境工程专利总清单_v2.csv"), encoding="utf-8-sig")))
fields = list(rows[0].keys())
have = {r["公开号"] for r in rows}
meta = {r["pub"]: r for r in csv.DictReader(open(os.path.join(PAT, "RAG", "产出", "RAG知识库", "metadata_index.csv"), encoding="utf-8-sig"))}
for pub, cls, why in NEW:
    if pub in have:
        for r in rows:
            if r["公开号"] == pub:
                r["子库分类"] = cls; r["裁定理由"] = why
        continue
    m = meta.get(pub, {})
    row = {k: "" for k in fields}
    row.update({"子库分类": cls, "公开号": pub, "公开年": (m.get("publication") or m.get("filing") or "")[:4],
                "国别": m.get("country", ""), "申请人": m.get("assignee", ""), "标题": m.get("title", ""),
                "裁定理由": why, "合规状态": "纳入(OCR口径)", "校验依据": m.get("compliance_criterion", ""),
                "PDF状态": "有(已RapidOCR识别,文本见05_OCR文本/)"})
    rows.append(row)
with open(os.path.join(ENV, "环境工程专利总清单_v2.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(rows)
print("总清单 v2 rows:", len(rows))

# 剂量摘录（新证据对素材）
for pub, kws in (("CN106047942A", ["四氢嘧啶", "投加", "g/L", "g"]), ("CN106148422A", ["甜菜碱", "投加", "复合剂"]), ("CN102517306B", ["无需驯化", "高盐废水"])):
    t = re.sub(r"\s+", " ", open(os.path.join(PAT, "txt", pub + "_OCR.txt"), encoding="utf-8", errors="ignore").read())
    print("=" * 20, pub)
    for kw in kws[:2]:
        for m in list(re.finditer(kw, t))[:3]:
            print(f"  [{kw}] …{t[max(0,m.start()-90):m.start()+130]}…")

# 重跑增量层链
for script in ("task2v2_build.py", "task3_gold_merge.py", "task3_eval_v2.py"):
    r = subprocess.run([PY, os.path.join(INC, script)], capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
    out = (r.stdout or "") + (r.stderr or "")
    print(f"--- {script} rc={r.returncode}")
    print("\n".join(out.strip().splitlines()[-8:]))
r = subprocess.run([PY, os.path.join(PAT, "RAG", "产出", "RAG可视化界面", "gen_ui.py")], capture_output=True, text=True, encoding="utf-8", errors="ignore")
print("--- gen_ui:", (r.stdout or r.stderr).strip()[-80:])
