# -*- coding: utf-8 -*-
"""Generate human-readable knowledge-base MD grouped by primary theme,
with per-patent entries carrying verbatim phrase-context excerpts."""
import os, sys, io, json, csv, re
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")
OUT = os.path.join(BASE, "产出", "RAG知识库")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = {r["pub"]: r for r in json.load(f)}
rows = list(csv.DictReader(open(os.path.join(OUT, "metadata_index.csv"), encoding="utf-8-sig")))

by_theme = defaultdict(list)
for row in rows:
    by_theme[row["primary_theme"]].append(row)

def esc(s):
    return (s or "").replace("|", "/").replace("\n", " ")

def year(row):
    for k in ("publication", "filing", "priority"):
        v = (row.get(k) or "")[:4]
        if v.isdigit():
            return v
    return "?"

L = []
L.append("# 相容性溶质（compatible solute）专利 RAG 知识库 · 可读版")
L.append("")
L.append("**语料**：`patents/pdf/` 410 份中经全文合规校验纳入的 227 份（方法与剔除名单见《合规校验与知识库质量自检报告.md》）。")
L.append("**组织**：第一维度=科学主题（下文一级分组）；第二维度=专利个体（组内逐件条目）。机器可读形态为同目录 `chunks.jsonl`（7900+ 自包含切片）与 `theme_digest_chunks.jsonl`（主题索引切片）。")
L.append("**内容约束**：每件条目的「原文摘录」为 pypdf 规范化文本的逐字片段（仅合并断行、统一空白），未做任何改写；片段外的解释一律不添加。所附元数据来自项目著录台账（compatible_solute_patents.xlsx，检索源 Google Patents，检索日 2026-09-14）与 PDF 全文提取。")
L.append("")
L.append("---")

for theme in sorted(by_theme, key=lambda k: -len(by_theme[k])):
    members = sorted(by_theme[theme], key=lambda r: r["pub"])
    L.append(f"\n# 主题：{theme}（{len(members)} 件）\n")
    L.append("| 公开号 | 年 | 国 | 申请人 | 标题 |")
    L.append("|---|---|---|---|---|")
    for r in members:
        L.append(f"| {r['pub']} | {year(r)} | {r['country']} | {esc(r['assignee'])[:28]} | {esc(r['title'])[:60]} |")
    L.append("")
    for r in members:
        rec = recs.get(r["pub"], {})
        L.append(f"## {r['pub']} — {esc(r['title']) or '（元数据缺失）'}")
        L.append(f"- 申请人/权利人：{esc(r['assignee']) or '（缺失）'}｜公开日：{r['publication'] or '（缺失）'}｜申请日：{r['filing'] or '（缺失）'}｜国别：{r['country']}")
        L.append(f"- IPC/CPC（正文提取，可能不全）：{r['ipc_cpc'] or '（未提取到）'}")
        L.append(f"- 合规校验：{r['compliance_criterion']}｜检出溶质标签：{r['solutes'] or '（无）'}｜主分类：{r['primary_theme']}（关键词初筛）")
        snips = rec.get("snippets") or []
        if snips:
            L.append("- 原文摘录（短语上下文，逐字）：")
            for s in snips[:3]:
                txt = s["text"].replace("\n", " ")
                if len(txt) > 460:
                    txt = txt[:460] + "…"
                L.append(f"  - 「…{txt}…」")
        else:
            L.append("- 原文摘录：（该专利正文中未定位到词组上下文窗口，或为中文等价术语命中且窗口未抽取）")
        L.append(f"- 源文件：`{r['source_pdf']}`｜SHA256：{r['sha256_pdf'][:16]}…")
        L.append("")

with open(os.path.join(OUT, "RAG知识库_可读版.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("readable MD written:", len(L), "lines |", sum(len(v) for v in by_theme.values()), "patents")
