# -*- coding: utf-8 -*-
"""Dump verbatim phrase-context snippets for representative patents (for review writing)."""
import os, sys, io, json, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")
with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = {r["pub"]: r for r in json.load(f)}

KEYS = {
 # 废水/环境
 "CN111717982A": None, "CN119977155A": None, "CN115651870A": None, "CN117285158A": None,
 "CN120247279A": None, "CN117466434A": None, "US7815801B2": None, "KR20160063208A": None,
 "CN114249432A": None, "CN118956681B": None, "CN119351484A": None, "CN116332375A": None,
 # 生产制造
 "EP4379060A1": None, "EP2743350A1": None, "DE4427617B4": None, "CN111304106B": None,
 "CN116218928A": None, "EP4424809A1": None, "CN118006704A": None, "CN116987650A": None,
 "EP3652323B1": None, "CN112266362B": None, "CN118791434A": None,
 # 医药/制剂/稳定
 "US20200030214A1": None, "US20090068673A1": None, "JP2023526200A": None, "HK1199071B": None,
 "EP1125583A1": None, "CN108685759B": None, "CN114214315B": None, "CN116195578B": None,
 "US20160106747A1": None,
 # 农业/植物
 "US20120117686A1": None, "US20040091900A1": None, "EP0818138B1": None, "CN115991996A": None,
 "CN119855497A": None,
 # 化妆品
 "CN109771427A": None, "US20090227523A1": None, "US20040097543A1": None, "JP2005521709A": None,
}

def norm(t):
    t = unicodedata.normalize("NFKC", t).replace("\u00ad", "")
    t = re.sub(r"[-‐‑–]+\s*\n\s*", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    return t

for pub in KEYS:
    r = recs.get(pub)
    if not r:
        print("=====", pub, "NOT IN RECORDS"); continue
    p = os.path.join(BASE, "txt", pub + ".txt")
    raw = open(p, encoding="utf-8", errors="ignore").read()
    t = norm(raw)
    low = t.lower()
    despaced = re.sub(r"\s+", "", low)
    print("=" * 90)
    print(f"[{pub}] {r['title'][:70]} | {r['assignee'][:40]}")
    shown = 0
    for needle in ("相容性溶质", "相溶性溶質", "compatible solute", "kompatible solute"):
        for m in re.finditer(needle, low):
            a, b = max(0, m.start() - 150), min(len(t), m.end() + 200)
            print("   >>", t[a:b].replace("\n", " "))
            shown += 1
            if shown >= 3:
                break
        if shown >= 3:
            break
    if shown == 0:
        for m in re.finditer(r"相容.{0,3}溶质|kompatibl\w*\s+solut\w*|solutos?\s+compatibles?|solutés?\s+compatibles?", low):
            a, b = max(0, m.start() - 150), min(len(t), m.end() + 200)
            print("   >>", t[a:b].replace("\n", " "))
            shown += 1
            if shown >= 3:
                break
