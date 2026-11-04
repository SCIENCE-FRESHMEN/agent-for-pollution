# -*- coding: utf-8 -*-
"""Verify phrase-hit contexts for suspicious (off-domain) passing patents."""
import os, sys, io, re, unicodedata, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
TXT = os.path.join(BASE, "txt")
AN = os.path.join(BASE, "analysis")

with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = {r["pub"]: r for r in json.load(f)}

suspects = ["US3046198A", "US3991759A", "US5151335A", "US5166010A", "US5175068A",
            "US5238761A", "US6022643A", "US6120941A", "US6352798B1", "US7516788B2",
            "US7557485B1", "US9683448B2", "US10016375B2", "US20180043618A1",
            "US20180030482A1", "US20100291652A1", "US20210017613A1", "EP3559246B1",
            "US20020157138A1", "US20060005282A1", "US11051464B2", "US8481026B1",
            "US9499582B2", "JP5956225B2", "CN110381917A", "US20200032224A1",
            "US20040097543A1", "US20130217085A1", "CN112176002A", "US20060005282A1"]

def norm(t):
    t = unicodedata.normalize("NFKC", t).replace("\u00ad", "")
    t = re.sub(r"[-‐‑–]+\s*\n\s*", "", t)
    return t.lower()

for pub in suspects:
    r = recs.get(pub)
    p = os.path.join(TXT, pub + ".txt")
    if not os.path.exists(p):
        print("==", pub, "NO TXT"); continue
    raw = open(p, encoding="utf-8", errors="ignore").read()
    t = norm(raw)
    despaced = re.sub(r"\s+", "", t)
    n_strict = len(re.findall(r"compatible solute", t))
    print("=" * 22, pub, f"| strict_single-spaced={n_strict} | title={((r or {}).get('title') or '')[:55]}")
    shown = 0
    for m in re.finditer(r"compatiblesolute", despaced):
        # map back approximately to spaced text by scanning
        i = despaced[:m.start()].count("") - 0  # approximate; easier: show despaced context
        print("   DESPACED-HIT ...", despaced[max(0, m.start() - 55):m.start() + 65], "...")
        shown += 1
        if shown >= 3:
            break
    for m in list(re.finditer(r"compatible solute", t))[:3]:
        print("   SPACED-HIT ...", t[max(0, m.start() - 60):m.start() + 70], "...")
