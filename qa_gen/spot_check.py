# -*- coding: utf-8 -*-
import os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
T3 = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txt3"
FT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txtfull"

def head(stem, src, n=600):
    p = os.path.join(src, stem + ".txt")
    if not os.path.exists(p):
        return f"[{stem}] MISSING in {os.path.basename(src)}"
    with open(p, encoding="utf-8", errors="ignore") as f:
        t = re.sub(r"\s+", " ", f.read(n))
    return t

for stem in ["10.1016_j.cej.2021.132772"]:
    print("===T3===", head(stem, T3, 900), "\n")

# search full texts for bank-cited refs & SAD/GB anammox paper
import glob
KEYS = ["watres.2026.126010", "es.3c07324", "Glycine Betaine and Ectoine", "simultaneous anammox and denitri",
        "SAD process", "dimethylglycine"]
hits = {k: [] for k in KEYS}
for p in glob.glob(os.path.join(FT, "*.txt")):
    with open(p, encoding="utf-8", errors="ignore") as f:
        t = f.read()
    for k in KEYS:
        if k.lower() in t.lower():
            hits[k].append(os.path.basename(p).replace(".txt", "").replace("_", "/"))
for k, v in hits.items():
    print(f"KEY '{k}':", v[:8])

# spot check 4 saline-anammox candidate papers
for stem in ["10.1016_j.ceb.2023.102170", "10.1016_j.jenvman.2025.124858",
             "10.1016_j.jwpe.2024.105689", "10.5004_dwt.2020.24791", "10.1021_acs.est.7b02567"]:
    print("\n===", stem.replace("_", "/"), "===")
    print(head(stem, FT, 700))
