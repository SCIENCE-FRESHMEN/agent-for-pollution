# -*- coding: utf-8 -*-
"""Re-rank from cached txt3 files."""
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OUT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txt3"
KW = {
    "anammox": 10,
    "brocadia": 6, "kuenenia": 6, "scalindua": 8, "anammoxoglobus": 8, "jettenia": 6,
    "salinity": 3, "saline": 3, "halophilic": 4, "hypersaline": 4, "halotolerant": 4,
    "osmotic": 2, "osmoadaptation": 5, "osmolyte": 4,
    "compatible solute": 6, "ectoine": 6, "betaine": 4, "trehalose": 3, "glutamate": 1,
    "hydroxyectoine": 5,
    "nitrogen removal": 1, "nitrite": 2,
}
rows = []
for fn in sorted(os.listdir(OUT)):
    if not fn.endswith(".txt"):
        continue
    with open(os.path.join(OUT, fn), "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    low = text.lower()
    scores = {k: low.count(k) for k in KW if low.count(k)}
    total = sum(w * min(c, 30) for k, c in scores.items() for w in [KW[k]])
    rows.append({"file": fn, "doi": fn[:-4].replace("_", "/"),
                 "anammox": low.count("anammox"), "score": total,
                 "top_kw": ";".join(f"{k}:{v}" for k, v in sorted(scores.items(), key=lambda x: -x[1])[:8])})
rows.sort(key=lambda r: -r["score"])
with open(r"C:\Users\25416\Desktop\agent for pollution\qa_gen\triage.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print("scored:", len(rows))
print(f"{'file':58s} {'amx':>4s} {'score':>6s}  top_kw")
for r in rows[:70]:
    print(f"{r['file'][:58]:58s} {r['anammox']:4d} {r['score']:6d}  {r['top_kw'][:80]}")
