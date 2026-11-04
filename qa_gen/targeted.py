# -*- coding: utf-8 -*-
"""Targeted fact extraction for question writing."""
import os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
FT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\txtfull"

def grab(stem, pats, ctx=350, maxhit=6):
    p = os.path.join(FT, stem + ".txt")
    with open(p, encoding="utf-8", errors="ignore") as f:
        t = re.sub(r"\s+", " ", f.read())
    print("\n" + "=" * 90 + "\n### " + stem.replace("_", "/"))
    for pat in pats:
        n = 0
        for m in re.finditer(pat, t, re.I):
            s = max(0, m.start() - ctx // 2)
            print("  ...", t[s:s + ctx].strip()[:ctx], "\n")
            n += 1
            if n >= maxhit:
                break
        if n == 0:
            print(f"  [no hit: {pat}]")

grab("10.1038_s41545-025-00549-0",
     [r"SAD process", r"salin", r"anammox.{0,80}(salin|salt)", r"glycine betaine"],
     ctx=400, maxhit=4)
grab("10.1016_j.watres.2023.120824",
     [r"SANIA", r"salin", r"sulphide.{0,60}anammox|anammox.{0,60}sulphide"],
     ctx=350, maxhit=3)
grab("10.1038_s41396-021-01031-8",
     [r"maintenance (?:energy|power)", r"0\.030|0\.010|0\.019", r"2\.5% salinity|2\.8% salinity",
      r"doubling time", r"kJ|mmol.{0,20}h..1.{0,40}mol"],
     ctx=380, maxhit=3)
grab("10.1016_j.cej.2022.136712",
     [r"salt-in", r"freezing", r"toilet", r"glutamate, glutamine, proline|glutamine, proline"],
     ctx=380, maxhit=3)
grab("10.1021_acs.est.6c05759",
     [r"energetically favou?r", r"ProVWX", r"choline"],
     ctx=330, maxhit=2)
