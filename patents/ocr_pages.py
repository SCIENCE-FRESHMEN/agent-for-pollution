# -*- coding: utf-8 -*-
import os, sys, io, csv, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
recs = json.load(open(os.path.join(BASE, "analysis", "grounding_records.json"), encoding="utf-8"))
done = {"CN108658243A", "WO2005014488A1", "CN106365887A"}
mani = {r["file"][:-4]: r for r in csv.DictReader(open(os.path.join(BASE, "extract_manifest.csv"), encoding="utf-8-sig"))}
todo = [r["pub"] for r in recs if r["verdict"].startswith("无法校验") and r["pub"] not in done]
total_pages = sum(int(mani.get(p, {}).get("pages") or 0) for p in todo)
print("scan PDFs to OCR:", len(todo), "| total pages:", total_pages)
print("est @3.8s/page:", round(total_pages * 3.8 / 3600, 1), "h | @1.2s/page(4进程):", round(total_pages * 1.2 / 3600, 1), "h")
by = {}
for p in todo:
    by[p[:2]] = by.get(p[:2], 0) + 1
print("by country:", dict(sorted(by.items(), key=lambda x: -x[1])))
json.dump(todo, open(os.path.join(BASE, "ocr_todo.json"), "w"))
