# -*- coding: utf-8 -*-
"""Debug the 78 excluded patents: fuzzy re-check for extraction artifacts / CJK variants."""
import os, sys, io, json, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
TXT = os.path.join(BASE, "txt")
AN = os.path.join(BASE, "analysis")

with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = json.load(f)
excluded = [r for r in recs if r["verdict"] == "剔除"]

def norm(t):
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("\u00ad", "")
    t = re.sub(r"[-‐‑–]+\s*\n\s*", "", t)
    return t.lower()

ZH_TERM = ("相容性溶质", "相容溶质", "兼容性溶质", "兼容溶质",
           "相容性溶質", "相容溶質", "兼容性溶質", "兼容溶質",   # 繁体(日文/繁中)
           "相容性溶質", "親和性溶質", "適応溶質", "适应溶质")     # 常见日文译法

for r in excluded:
    pub = r["pub"]
    p = os.path.join(TXT, pub + ".txt")
    with open(p, encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    t = norm(raw)
    despaced = re.sub(r"\s+", "", t)
    # remove ALL non-letters between letters to catch extraction noise inside the phrase
    fuzzy = re.sub(r"[^a-z]", "", t)
    hits = {}
    m = re.search(r"compat\w{0,12}", t)
    hits["compat_ctx"] = t[m.start():m.start() + 60] if m else ""
    m2 = re.search(r"solute\w{0,8}", t)
    hits["solute_ctx"] = t[m2.start():m2.start() + 60] if m2 else ""
    zh_hits = [w for w in ZH_TERM if w in despaced]
    en_exact = "compatible solute" in t or "compatiblesolute" in despaced
    en_fuzzy = "compatiblesolute" in fuzzy or "compatibles olutes" in fuzzy
    # near-phrase: compatible within 30 chars before solute
    near = False
    for mm in re.finditer(r"solute", t):
        ctx = t[max(0, mm.start() - 40):mm.start()]
        if "compatible" in ctx:
            near = True
            break
    flag = "CHECK" if (zh_hits or en_fuzzy or near or (not en_exact and ("compatible" in t and "solute" in t))) else "ok"
    print(f"{flag} | {pub} | ENexact={en_exact} | fuzzy={en_fuzzy} | near={near} | ZH={zh_hits} | lang_chars: cn={len(re.findall(r'[\u4e00-\u9fff]', t))} jp_kana={len(re.findall(r'[\u3040-\u30ff]', t))} ko={len(re.findall(r'[\uac00-\ud7af]', t))} cyr={len(re.findall(r'[\u0400-\u04ff]', t))}")
    if hits["compat_ctx"]:
        print(f"      compat@: {hits['compat_ctx']}")
    if hits["solute_ctx"]:
        print(f"      solute@: {hits['solute_ctx']}")
