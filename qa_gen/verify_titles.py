# -*- coding: utf-8 -*-
"""核对我引用的每个DOI对应PDF的真实标题。"""
import os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
T3 = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txt3"
DOIS = ["10.1021_acs.est.2c01104","10.1128_mbio.00092-22","10.1016_j.watres.2020.115855",
"10.1021_acs.est.4c01417","10.1038_s41396-021-01031-8","10.1038_s41396-020-00850-5",
"10.1093_femsre_fuaf020","10.1016_j.ese.2025.100542","10.1016_j.csbj.2021.01.030",
"10.1038_srep24825","10.1016_j.cej.2022.136712","10.1016_j.ese.2024.100406",
"10.1038_s41598-019-45620-2","10.1074_jbc.M113.470567","10.1074_jbc.RA120.012722",
"10.1021_acs.est.6c05759","10.1021_acs.est.2c02081","10.1038_s41522-022-00308-w",
"10.1016_j.jare.2023.06.015"]
for stem in DOIS:
    p = os.path.join(T3, stem + ".txt")
    with open(p, encoding="utf-8", errors="ignore") as f:
        t = f.read(1200)
    t = re.sub(r"\s+", " ", t)
    print("=" * 100)
    print(stem.replace("_", "/"))
    print(t[:550])
