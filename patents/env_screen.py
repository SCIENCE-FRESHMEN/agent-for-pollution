# -*- coding: utf-8 -*-
"""Screen ALL 410 patents for environmental-engineering relevance (two-pass: propose)."""
import os, sys, io, csv, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import openpyxl

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")

# metadata for ALL candidates (incl. scans & excluded)
wb = openpyxl.load_workbook(os.path.join(BASE, "compatible_solute_patents.xlsx"), read_only=True, data_only=True)
ws = wb["专利候选清单"]
header = None
meta = {}
for i, row in enumerate(ws.iter_rows(values_only=True)):
    vals = ["" if c is None else str(c) for c in row]
    if i == 0:
        header = vals; continue
    if not vals or not vals[0].strip():
        continue
    rec = dict(zip(header, vals))
    meta[vals[0].strip()] = rec
for extra_pub in ("CN110381917A", "WO2007097653A2", "WO2017093463A1"):
    meta.setdefault(extra_pub, {"标题": "", "检索摘要片段": "", "申请人/权利人": "", "公开日": "", "申请日": "", "优先权日": ""})
meta["CN110381917A"].update({"标题": "相容性溶质的用途", "申请人/权利人": "默克专利股份有限公司"})

recs = json.load(open(os.path.join(AN, "grounding_records.json"), encoding="utf-8"))
grecs = {r["pub"]: r for r in recs}

ENV_GROUPS = {
    "废水处理": r"废水|污水|水处理|wastewater|sewage|water treatment|effluent|排水处理",
    "脱氮/脱氮工艺": r"脱氮|反硝化|硝化|anammox|厌氧氨氧化|denitrif|nitrif|nitrogen removal|总氮",
    "反应器/污泥": r"反应器|污泥|生物膜|活性污泥|bioreactor|sludge|\bSBR\b|\bMBR\b|reactor",
    "盐碱地/土壤/脱盐": r"盐碱|土壤改良|desalin|脱盐|saline[- ]alkali|soil conditioner|次生盐渍",
    "厌氧消化/沼气": r"沼气|厌氧消化|biogas|anaerobic digestion|甲烷生产|甲烷菌|产甲烷",
    "菌剂/生物强化/促进剂": r"菌剂|生物强化|bioaugmentation|促进剂|promoter|生物修复|bioremediation|halophile.{0,12}cultur|嗜盐菌.{0,8}培养",
    "污染治理其他": r"污染|污染物|remediation|降解.{0,6}(有机物|污染物)|硝基苯|seawater|海水|船舶废水",
}
TEXT_ENV = r"废水|污水|脱氮|反硝化|anammox|硝化|污泥|反应器|盐碱|土壤|沼气|厌氧消化|生物强化|菌剂|生物膜|wastewater|denitrif|sludge|saline|bioremediation"

rows = []
for pub in sorted(set(list(meta.keys()) + list(grecs.keys()))):
    g = grecs.get(pub, {})
    m = meta.get(pub, {})
    title = m.get("标题", "") or g.get("title", "")
    snip = m.get("检索摘要片段", "")
    applicant = m.get("申请人/权利人", "") or g.get("assignee", "")
    verdict = g.get("verdict", "不在台账" if pub not in grecs else "")
    blob = f"{title} {snip} {applicant}"
    hits = [name for name, pat in ENV_GROUPS.items() if re.search(pat, blob, re.I)]
    text_hits = ""
    if g.get("chars", 0) and g["chars"] >= 200:
        txt = open(os.path.join(BASE, "txt", pub + ".txt"), encoding="utf-8", errors="ignore").read()
        n = len(re.findall(TEXT_ENV, txt, re.I))
        th = [x for x in (g.get("themes") or "").split(";") if x]
        if "废水/环境工程" in th:
            hits.append("文本层主题:废水/环境工程")
        if n >= 3 and not hits:
            hits.append(f"全文环境词频{n}")
    if hits:
        rows.append((pub, verdict, g.get("country", ""), ";".join(sorted(set(hits))), applicant[:30], title[:60]))

for r in sorted(rows, key=lambda x: x[1]):
    print(" | ".join(str(x) for x in r))
print("\nTOTAL candidates:", len(rows))
from collections import Counter
print("by verdict:", dict(Counter(r[1] for r in rows)))
