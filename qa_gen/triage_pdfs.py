# -*- coding: utf-8 -*-
"""Triage all PDFs: extract first-3-page text, score relevance to anammox x salinity."""
import os, sys, re, json
import fitz

sys.stdout.reconfigure(encoding='utf-8')
SRC = r"C:\Users\25416\Desktop\agent for pollution\lit_workspace\literature\oa_pdf_20260926"
OUT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txt3"
os.makedirs(OUT, exist_ok=True)

KW = {
    "anammox": 10,
    "brocadia": 6, "kuenenia": 6, "scalindua": 8, "anammoxoglobus": 8, "jettenia": 6,
    "salinity": 3, "saline": 3, "halophilic": 4, "hypersaline": 4, "halotolerant": 4,
    "osmotic": 2, "osmoadaptation": 5, "osmolyte": 4,
    "compatible solute": 6, "ectoine": 6, "betaine": 4, "trehalose": 3, "glutamate": 1,
    "hydroxyectoine": 5, "di-myo-inositol phosphate": 4, "dip": 0,
    "nitrogen removal": 1, "reactor": 1, "nitrite": 2, "nitrate": 1,
}

rows = []
files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
for i, fn in enumerate(files):
    doi = fn[:-4].replace("_", "/")
    out_txt = os.path.join(OUT, fn[:-4] + ".txt")
    text = ""
    if os.path.exists(out_txt):
        with open(out_txt, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    else:
        try:
            doc = fitz.open(os.path.join(SRC, fn))
            npages = min(3, doc.page_count)
            text = "\n".join(doc[j].get_text() for j in range(npages))
            doc.close()
            with open(out_txt, "w", encoding="utf-8", errors="ignore") as f:
                f.write(text)
        except Exception as e:
            text = ""
    low = text.lower()
    scores = {}
    for k, w in KW.items():
        c = low.count(k)
        if c:
            scores[k] = c
    total = sum(w * min(c, 30) for k, c in scores.items() for w in [KW[k]])
    anammox = low.count("anammox")
    rows.append({
        "file": fn, "doi": doi, "chars": len(text),
        "anammox": anammox, "score": total,
        "top_kw": ";".join(f"{k}:{v}" for k, v in sorted(scores.items(), key=lambda x: -x[1])[:8]),
    })
    if (i + 1) % 100 == 0:
        print(f"...{i+1}/{len(files)}", flush=True)

rows.sort(key=lambda r: -r["score"])
with open(os.path.join(r"C:\Users\25416\Desktop\agent for pollution\qa_gen"), "triage.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)

core = [r for r in rows if r["anammox"] >= 3]
print(f"total={len(rows)}  anammox>=3: {len(core)}")
print("\nTOP 60 by score:")
print(f"{'file':58s} {'amx':>4s} {'score':>6s}  top_kw")
for r in rows[:60]:
    print(f"{r['file'][:58]:58s} {r['anammox']:4d} {r['score']:6d}  {r['top_kw'][:80]}")
