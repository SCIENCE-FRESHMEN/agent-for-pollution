# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
FT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txtfull"
AMX = ["anammox", "brocadia", "kuenenia", "scalindua", "anammoxoglobus", "jettenia"]
SALT = ["salinity", "saline", "salt", "halophilic", "hypersaline", "halotolerant",
        "osmotic", "osmoadaptation", "osmolyte", "compatible solute"]
SOL = ["ectoine", "hydroxyectoine", "betaine", "trehalose", "glutamate", "di-myo-inositol",
       "mannosylglycerate"]
rows = []
for fn in sorted(os.listdir(FT)):
    with open(os.path.join(FT, fn), encoding="utf-8", errors="ignore") as f:
        low = f.read().lower()
    amx = sum(low.count(k) for k in AMX)
    salt = sum(low.count(k) for k in SALT)
    sol = sum(low.count(k) for k in SOL)
    if amx >= 2 or salt >= 15:
        rows.append((amx, salt, sol, fn[:-4].replace("_", "/")))
rows.sort(key=lambda r: -(r[0] + r[1] + r[2]))
print(f"{'amx':>4} {'salt':>5} {'sol':>4}  doi")
for amx, salt, sol, doi in rows:
    flag = " <== core" if amx >= 3 and salt >= 5 else ""
    print(f"{amx:4d} {salt:5d} {sol:4d}  {doi}{flag}")
