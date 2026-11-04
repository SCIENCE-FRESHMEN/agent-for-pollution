# -*- coding: utf-8 -*-
"""全语料收尾批：路径修正 + 2 件边缘环境件并入 + 配方库/图谱/增量层/评测/UI 重跑"""
import os, sys, io, shutil, csv, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = r"C:\Users\25416\Desktop\agent for pollution"
PY = os.path.join(ROOT, ".rc_venv", "Scripts", "python.exe")
PAT = os.path.join(ROOT, "patents")
NEWAUTH = os.path.join(PAT, "RAG", "产出", "RAG知识库")
OLDAUTH = os.path.join(PAT, "产出", "RAG知识库")
ENV = os.path.join(PAT, "RAG", "产出", "环境工程专利")

def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for a, b in pairs:
        s = s.replace(a, b)
    open(path, "w", encoding="utf-8").write(s)
    print("patched", os.path.basename(path))

# 1) 路径指向权威库（RAG\产出）
patch(os.path.join(ENV, "..", "RAG知识库", "env_increment", "task2v2_build.py"), [])  # noop keep
patch(os.path.join(PAT, "产出", "scripts", "task1_formulation.py"), [
    ('KB = os.path.join(BASE, "产出", "RAG知识库", "chunks.jsonl")',
     'KB = os.path.join(BASE, "RAG", "产出", "RAG知识库", "chunks.jsonl")'),
    ('OUT = os.path.join(BASE, "产出", "formulation_database.csv")',
     'OUT = os.path.join(BASE, "RAG", "产出", "formulation_database.csv")')])
patch(os.path.join(PAT, "产出", "scripts", "task3_graph.py"), [
    ('META = os.path.join(OUTD, "RAG知识库", "metadata_index.csv")',
     'META = os.path.join(BASE, "RAG", "产出", "RAG知识库", "metadata_index.csv")'),
    ('FORM = os.path.join(OUTD, "formulation_database.csv")',
     'FORM = os.path.join(BASE, "RAG", "产出", "formulation_database.csv")'),
    ('OUTD = os.path.join(BASE, "产出")', 'OUTD = os.path.join(BASE, "RAG", "产出")')])

# 2) 两件边缘环境件并入（01d）+ 总清单 v2
d01d = os.path.join(ENV, "01d_已入库PDF_盐碱农业边缘")
os.makedirs(d01d, exist_ok=True)
for pub in ("CN116267891B", "CN117694054A"):
    shutil.copy(os.path.join(PAT, "pdf", pub + ".pdf"), os.path.join(d01d, pub + ".pdf"))
rows = list(csv.DictReader(open(os.path.join(ENV, "环境工程专利总清单.csv"), encoding="utf-8-sig")))
fields = list(rows[0].keys())
meta = {r["pub"]: r for r in csv.DictReader(open(os.path.join(PAT, "RAG", "产出", "RAG知识库", "metadata_index.csv"), encoding="utf-8-sig"))}
have = {r["公开号"] for r in rows}
for pub, why in (("CN117694054A", "盐碱地设施栽培种植方法（全语料重筛新增·边缘）"),
                 ("CN116267891B", "昆虫病原线虫保护剂（全语料重筛新增·边缘）")):
    if pub in have:
        continue
    m = meta.get(pub, {})
    row = {k: "" for k in fields}
    row.update({"子库分类": "01d_已入库PDF_盐碱农业边缘", "公开号": pub,
                "公开年": (m.get("publication") or "")[:4], "国别": m.get("country", ""),
                "申请人": m.get("assignee", ""), "标题": m.get("title", ""), "裁定理由": why,
                "合规状态": "纳入", "校验依据": m.get("compliance_criterion", ""),
                "PDF状态": "有(PDF已入子库)"})
    rows.append(row)
with open(os.path.join(ENV, "环境工程专利总清单_v2.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(rows)
print("总清单 v2 rows:", len(rows))

# 3) 重跑：配方库 → 图谱 → 增量层 → 金标 → 评测 → UI
for script, cwd in (
    (os.path.join(PAT, "产出", "scripts", "task1_formulation.py"), None),
    (os.path.join(PAT, "产出", "scripts", "task3_graph.py"), None),
    (os.path.join(NEWAUTH, "env_increment", "task2v2_build.py"), None),
    (os.path.join(NEWAUTH, "env_increment", "task3_gold_merge.py"), None),
    (os.path.join(NEWAUTH, "env_increment", "task3_eval_v2.py"), None),
    (os.path.join(PAT, "RAG", "产出", "RAG可视化界面", "gen_ui.py"), None),
):
    r = subprocess.run([PY, script], capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
    out = (r.stdout or "") + (r.stderr or "")
    print(f"--- {os.path.basename(script)} rc={r.returncode}")
    print("\n".join(out.strip().splitlines()[-6:]))
