# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"C:\Users\25416\Desktop\agent for pollution\patents\产出\RAG知识库\chunks_with_tables.jsonl"
n = tc = bad = 0
sample = None
for line in open(p, encoding="utf-8"):
    n += 1
    try:
        c = json.loads(line)
        if c.get("chunk_type") == "table":
            tc += 1
            if sample is None:
                sample = c
    except Exception:
        bad += 1
print("lines", n, "| table_chunks", tc, "| bad_json", bad)
if sample:
    print("SAMPLE:", sample["chunk_id"], "| page", sample["page_number"], "| patents_in_tables:", end=" ")
pats = set()
for line in open(p, encoding="utf-8"):
    c = json.loads(line)
    if c.get("chunk_type") == "table":
        pats.add(c["patent_id"])
print(len(pats))
