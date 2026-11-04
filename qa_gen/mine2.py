# -*- coding: utf-8 -*-
"""Digest v2: detailed passages for anammox-salinity core + solute-mechanism papers."""
import os, sys, re

sys.stdout.reconfigure(encoding='utf-8')
FT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txtfull"
OUT_A = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\digest_core.txt"

CORE = [
    "10.1016_j.jare.2023.06.015", "10.1016_j.cej.2022.136712", "10.1016_j.ese.2024.100406",
    "10.1038_s41598-019-45620-2", "10.1038_s41396-020-00850-5", "10.1038_s41396-021-01031-8",
    "10.1021_acs.est.2c01104", "10.1021_acs.est.4c01417", "10.1038_s41522-022-00308-w",
    "10.1021_acssuschemeng.0c08036", "10.1021_acs.est.5c09128", "10.1016_j.ese.2025.100542",
    "10.1074_jbc.M113.470567", "10.1074_jbc.RA120.012722", "10.1016_j.csbj.2021.01.030",
    "10.1128_AEM.01728-18", "10.1128_mbio.00092-22", "10.1093_femsre_fuaf020",
    "10.1128_msystems.01050-23", "10.1016_j.watres.2020.115855", "10.1038_srep24825",
    "10.1016_j.ese.2022.100211", "10.1016_j.watres.2023.119620", "10.1021_acs.est.6c05759",
    "10.1021_acs.est.2c02081", "10.1016_j.watres.2023.120824", "10.1016_j.watres.2025.123663",
    "10.1016_j.cej.2021.132772",
]
AMX_GENOMICS = [
    "10.1038_s41467-020-16016-y", "10.1038_ncomms15416", "10.1038_s41467-024-54805-x",
    "10.1038_s41396-023-01388-y", "10.1038_s41467-024-52364-9", "10.1038_s41598-022-26069-2",
    "10.1038_srep40173", "10.1038_s41545-024-00385-8", "10.1038_srep28327",
    "10.1038_s41598-020-72577-4",
]
PASS_KEY = re.compile(
    r"(salinit|saline|salt|halophil|hypersalin|osmotic|osmoadapt|osmolyt|compatible solut|"
    r"ectoine|betaine|trehalose|NaCl|glutamat|plasmolysis|water activity)", re.I)
NUM = re.compile(r"(?:\d+(?:\.\d+)?)\s*(?:%|g\s*L|g/L|M\b)", re.I)

def sentences(text):
    text = re.sub(r"\s+", " ", text)
    return re.split(r"(?<=[.;])\s+(?=[A-Z0-9])", text)

def passages(text, maxp=18):
    sents = sentences(text)
    hits, seen = [], set()
    for i, s in enumerate(sents):
        if PASS_KEY.search(s):
            seg = s
            if i + 1 < len(sents) and PASS_KEY.search(sents[i + 1]):
                seg = seg + " " + sents[i + 1]
            seg = seg[:700]
            if seg in seen:
                continue
            seen.add(seg)
            hits.append(seg)
    hits.sort(key=lambda s: (NUM.search(s) is not None,
                             any(k in s.lower() for k in ("scalindua", "kuenenia", "brocadia", "ectoine", "betaine", "trehalose"))),
              reverse=True)
    return hits[:maxp]

with open(OUT_A, "w", encoding="utf-8", errors="ignore") as f:
    for stem in CORE:
        path = os.path.join(FT, stem + ".txt")
        if not os.path.exists(path):
            f.write(f"\n{'='*100}\n### {stem.replace('_','/')}  [MISSING]\n")
            continue
        with open(path, encoding="utf-8", errors="ignore") as g:
            text = g.read()
        low = text.lower()
        f.write(f"\n{'='*100}\n### {stem.replace('_','/')}\n")
        f.write(f"HEAD: {re.sub(r'[s]+', ' ', text[:800])}\n")
        for s in passages(text):
            f.write(f"- {s}\n")

    f.write(f"\n\n{'#'*100}\n# GENOMICS/STRAIN PAPERS (heads + strain/salt lines)\n{'#'*100}\n")
    for stem in AMX_GENOMICS:
        path = os.path.join(FT, stem + ".txt")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as g:
            text = g.read()
        f.write(f"\n{'='*100}\n### {stem.replace('_','/')}\n")
        f.write(f"HEAD: {re.sub(r'[s]+', ' ', text[:900])}\n")
        sents = sentences(text)
        n = 0
        for s in sents:
            if n >= 6:
                break
            if PASS_KEY.search(s) and ("brocadia" in s.lower() or "scalindua" in s.lower()
                                      or "kuenenia" in s.lower() or "salin" in s.lower()):
                f.write(f"- {s[:500]}\n")
                n += 1
print("digest_core size:", os.path.getsize(OUT_A))
