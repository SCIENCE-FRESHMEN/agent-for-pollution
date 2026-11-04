# -*- coding: utf-8 -*-
"""终局 QC：① OCR 件环境词频兜底筛 ② OCR 全量质量报告 ③ UI 指标修正"""
import os, sys, io, json, re, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
INC = os.path.join(BASE, "RAG", "产出", "RAG知识库", "env_increment")
ENV = os.path.join(BASE, "RAG", "产出", "环境工程专利")

# ① OCR 件环境兜底筛
ENVRE = re.compile(r"wastewater|sewage|sludge|denitrif|nitrif|anammox|bioreactor|water treatment|废水|污水|污泥|脱氮|硝化|反应器|水处理|盐碱|desalin", re.I)
recs = {r["pub"]: r for r in json.load(open(os.path.join(BASE, "analysis", "grounding_records_v2.json"), encoding="utf-8"))}
manifest = list(csv.DictReader(open(os.path.join(ENV, "环境工程专利总清单_v2.csv"), encoding="utf-8-sig")))
known = {r["公开号"] for r in manifest}
cands = []
for pub, r in recs.items():
    if r["source"] != "RapidOCR" or pub in known or r["verdict"] != "纳入":
        continue
    p = os.path.join(BASE, "txt", pub + "_OCR.txt")
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8", errors="ignore").read()
    n = len(ENVRE.findall(t))
    if n >= 5:
        cands.append((n, pub, r["title"][:60]))
cands.sort(reverse=True)
with open(os.path.join(BASE, "analysis", "env_ocr_candidates.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["环境词频", "公开号", "标题", "处置建议"])
    for n, pub, ti in cands:
        w.writerow([n, pub, ti, "人工复核（≥8 建议并入子库边缘层）"])
print("OCR 环境兜底候选:", len(cands), cands[:5])

# ② OCR 全量质量报告
prog = json.load(open(os.path.join(BASE, "ocr_batch_progress.json"), encoding="utf-8"))
with open(os.path.join(BASE, "analysis", "OCR质量报告_全量.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["公开号", "页数", "字符数", "低置信页", "耗时s", "备注"])
    for pub, v in sorted(prog.items()):
        m = re.match(r"lowconf_pages=(\d+);(\d+)s", v.get("info", ""))
        low, secs = (m.group(1), m.group(2)) if m else ("", "")
        w.writerow([pub, v["pages"], v["chars"], low, secs, ""])
tot_pages = sum(v["pages"] for v in prog.values())
tot_low = sum(int(re.match(r"lowconf_pages=(\d+)", v.get("info", "")).group(1)) for v in prog.values()
              if re.match(r"lowconf_pages=(\d+)", v.get("info", "")))
print(f"OCR 全量质量报告: {len(prog)} 份 | {tot_pages} 页 | 低置信页 {tot_low}")

# ③ UI 指标修正
p = os.path.join(BASE, "RAG", "产出", "RAG可视化界面", "gen_ui.py")
s = open(p, encoding="utf-8").read()
s = s.replace('"kb": {"chunks": 8103, "patents": 227, "formulation": 1934, "graph": "424×1009"}',
              '"kb": {"chunks": 10974, "patents": 327, "formulation": 2391, "graph": "559×1311"}')
s = s.replace('"patents": 32, "ocr": "3/3 纳入"', '"patents": 37, "ocr": "109 份全OCR"')
s = s.replace('"专利库(227)"', '"专利库(327)"')
s = s.replace("合规纳入专利（410 份筛选）", "合规纳入专利（410 份全部读取：文本层227+OCR100）")
open(p, "w", encoding="utf-8").write(s)
print("gen_ui metrics patched")
