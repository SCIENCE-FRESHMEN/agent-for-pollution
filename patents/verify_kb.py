# -*- coding: utf-8 -*-
"""KB integrity check + export excluded/unverifiable lists."""
import os, sys, io, json, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")
OUT = os.path.join(BASE, "产出", "RAG知识库")

with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = json.load(f)
passing = {r["pub"] for r in recs if r["verdict"] == "纳入"}

n = 0
bad = 0
pubs = set()
sections = {}
info_classes = {}
zero_hit = 0
with open(os.path.join(OUT, "chunks.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        n += 1
        try:
            c = json.loads(line)
        except Exception:
            bad += 1
            continue
        pubs.add(c["pub"])
        sections[c["section"]] = sections.get(c["section"], 0) + 1
        info_classes[c["info_class"]] = info_classes.get(c["info_class"], 0) + 1
        if c.get("term_hits", 0) == 0:
            zero_hit += 1
print("chunks:", n, "| bad json:", bad, "| distinct pubs:", len(pubs))
print("all pubs in passing set:", pubs <= passing)
print("sections:", sections)
print("info_classes:", info_classes)
print("zero-term-hit chunks:", zero_hit)

# export excluded + unverifiable
with open(os.path.join(AN, "excluded_and_unverifiable.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["公开号", "类别", "原因", "标题"])
    for r in recs:
        if r["verdict"] == "剔除":
            w.writerow([r["pub"], "剔除", r["criterion"], r["title"]])
        elif r["verdict"].startswith("无法校验"):
            w.writerow([r["pub"], "无法校验", r["verdict"], r["title"]])
print("exported excluded_and_unverifiable.csv")
