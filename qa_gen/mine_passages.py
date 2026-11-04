# -*- coding: utf-8 -*-
"""Mine salinity/anammox passages from full texts; produce tiered digests."""
import os, sys, re, json

sys.stdout.reconfigure(encoding='utf-8')
FT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txtfull"
OUT_A = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\digest_tierA.txt"
OUT_B = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\digest_tierB.txt"

AMX = ["anammox", "brocadia", "kuenenia", "scalindua", "anammoxoglobus", "jettenia", "candidatus"]
SALT = ["salinity", "saline", "salt", "halophilic", "hypersaline", "halotolerant",
        "osmotic", "osmoadaptation", "osmolyte", "compatible solute", "osmoadapt"]
SOL = ["ectoine", "hydroxyectoine", "betaine", "trehalose", "glutamate", "di-myo-inositol",
       "mannosylglycerate", "solute"]
NUM_SALT = re.compile(r"(?:\d+(?:\.\d+)?)\s*(?:%|g\s*L|gL|g/L|M\b|wt)", re.I)

def sentences(text):
    text = re.sub(r"\s+", " ", text)
    return re.split(r"(?<=[.;])\s+(?=[A-Z0-9])", text)

def score_text(low):
    amx = sum(low.count(k) for k in AMX)
    salt = sum(low.count(k) for k in SALT)
    sol = sum(low.count(k) for k in SOL)
    return amx, salt, sol

papers = []
for fn in sorted(os.listdir(FT)):
    with open(os.path.join(FT, fn), encoding="utf-8", errors="ignore") as f:
        text = f.read()
    low = text.lower()
    amx, salt, sol = score_text(low)
    papers.append({"fn": fn, "doi": fn[:-4].replace("_", "/"), "text": text, "low": low,
                   "amx": amx, "salt": salt, "sol": sol})

# core score: anammox context salinity papers rank first
for p in papers:
    p["core"] = p["amx"] * 2 + min(p["salt"], 120) + p["sol"] * 2
papers.sort(key=lambda p: -p["core"])

tierA = [p for p in papers if p["amx"] >= 5 and p["salt"] >= 10]
tierB = [p for p in papers if p not in tierA]
print("tierA:", len(tierA))

PASS_KEY = re.compile(
    r"(salinit|saline|salt|halophil|hypersalin|osmotic|osmoadapt|osmolyt|compatible solut|"
    r"ectoine|betaine|trehalose|NaCl)", re.I)

def passages(text, maxp=14):
    sents = sentences(text)
    hits = []
    for i, s in enumerate(sents):
        if PASS_KEY.search(s):
            seg = s
            if i + 1 < len(sents) and PASS_KEY.search(sents[i + 1]):
                seg = seg + " " + sents[i + 1]
            if len(seg) > 600:
                seg = seg[:600]
            hits.append(seg)
    # dedupe similar, prioritize ones with numbers or strain names
    hits = list(dict.fromkeys(hits))
    hits.sort(key=lambda s: (NUM_SALT.search(s) is not None,
                             any(k in s.lower() for k in ("scalindua", "kuenenia", "brocadia"))),
              reverse=True)
    return hits[:maxp]

with open(OUT_A, "w", encoding="utf-8", errors="ignore") as f:
    for p in tierA:
        f.write(f"\n{'='*100}\n### {p['doi']}  [amx={p['amx']} salt={p['salt']} sol={p['sol']}]\n")
        head = re.sub(r"\s+", " ", p["text"][:700])
        f.write(f"HEAD: {head}\n")
        for s in passages(p["text"]):
            f.write(f"- {s}\n")

with open(OUT_B, "w", encoding="utf-8", errors="ignore") as f:
    for p in tierB:
        head = re.sub(r"\s+", " ", p["text"][:260])
        f.write(f"{p['doi']} [amx={p['amx']} salt={p['salt']} sol={p['sol']}] {head}\n")

print("digestA size:", os.path.getsize(OUT_A), " digestB size:", os.path.getsize(OUT_B))
