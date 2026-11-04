# -*- coding: utf-8 -*-
import os, sys, io, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
TXT = os.path.join(BASE, "txt")
targets = ["JP2005521709A", "EP1125583A1", "EP3482755A1", "EP0915167B1", "EP3806819B1",
           "ES2321486T3", "US20170166638A1", "EP2303847B1", "JP5773509B2", "DE102008039734A1"]
def norm(t):
    t = unicodedata.normalize("NFKC", t).replace("\u00ad", "")
    t = re.sub(r"[-‐‑–]+\s*\n\s*", "", t)
    return t.lower()
for pub in targets:
    p = os.path.join(TXT, pub + ".txt")
    if not os.path.exists(p):
        print(pub, "NO TXT"); continue
    raw = open(p, encoding="utf-8", errors="ignore").read()
    t = norm(raw)
    despaced = re.sub(r"\s+", "", t)
    print("=" * 25, pub, "=" * 25)
    for pat, label in [(r"compat\S{0,15}", "compat"), (r"溶質", "溶質"), (r"溶质", "溶质")]:
        ms = list(re.finditer(pat, t))[:3]
        for m in ms:
            print(f"  [{label}] ...{t[max(0,m.start()-90):m.start()+90]}...".replace("\n", " "))
    print("  exact_in_despaced:", "compatiblesolute" in despaced)
    print("  kana:", len(re.findall(r"[\u3040-\u30ff]", t)), "| han:", len(re.findall(r"[\u4e00-\u9fff]", t)))
