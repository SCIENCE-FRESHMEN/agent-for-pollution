# -*- coding: utf-8 -*-
"""Full-text extraction (first 15 pages, 90k char cap) for anammox/salinity candidates."""
import os, sys, json, re
import fitz

sys.stdout.reconfigure(encoding='utf-8')
SRC = r"C:\Users\25416\Desktop\agent for pollution\lit_workspace\literature\oa_pdf_20260926"
T3 = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txt3"
FT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txtfull"
os.makedirs(FT, exist_ok=True)

with open(r"C:\Users\25416\Desktop\agent for pollution\qa_gen\triage.json", encoding="utf-8") as f:
    tri = json.load(f)

candidates = set()
for r in tri:
    if r["anammox"] >= 1 or r["score"] >= 100:
        candidates.add(r["file"].replace(".txt", ".pdf"))
# also add anything whose t3 text mentions halophilic/osmoadaptation/compatible solute
for fn in sorted(os.listdir(T3)):
    with open(os.path.join(T3, fn), encoding="utf-8", errors="ignore") as f:
        t = f.read().lower()
    if any(k in t for k in ("osmoadaptation", "compatible solute", "halophilic", "osmolyte")):
        candidates.add(fn.replace(".txt", ".pdf"))

print("candidates:", len(candidates))
done, fail = 0, []
for i, fn in enumerate(sorted(candidates)):
    out = os.path.join(FT, fn.replace(".pdf", ".txt"))
    if os.path.exists(out):
        done += 1
        continue
    try:
        doc = fitz.open(os.path.join(SRC, fn))
        text = "\n".join(doc[j].get_text() for j in range(min(15, doc.page_count)))
        doc.close()
        text = text[:90000]
        with open(out, "w", encoding="utf-8", errors="ignore") as f:
            f.write(text)
        done += 1
    except Exception as e:
        fail.append((fn, str(e)[:60]))
    if (i + 1) % 50 == 0:
        print(f"...{i+1}/{len(candidates)}", flush=True)
print("extracted:", done, "failed:", len(fail))
for fn, e in fail[:20]:
    print("FAIL", fn, e)
