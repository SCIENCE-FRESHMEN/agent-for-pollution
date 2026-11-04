# -*- coding: utf-8 -*-
"""Manual adjudication + regenerate exports."""
import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")

with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = json.load(f)

ADJ = {
    "JP5773509B2": {
        "verdict": "纳入", "criterion": "人工裁定:日文变体术语(適合性の溶質/相溶性(compatible)の溶質)",
        "note": "硅酸盐稳定组合物专利；原文以'適合性の溶質'指称相容性溶质，实施例使用三甲基甘氨酸(甜菜碱)5%+尿素10%+甘油20%"},
}
for r in recs:
    if r["pub"] in ADJ:
        r.update(ADJ[r["pub"]])
        r["title"] = r.get("title") or "Stabilized bioavailable soluble silicate solution"
        r["solutes"] = r.get("solutes") or "betaine(unspecified)"

with open(os.path.join(AN, "grounding_records.json"), "w", encoding="utf-8") as f:
    json.dump(recs, f, ensure_ascii=False)
print("adjudicated:", [r["pub"] for r in recs if "人工裁定" in r.get("criterion", "")])

# total size of pass corpus
passing = [r for r in recs if r["verdict"] == "纳入"]
print("PASS:", len(passing), "total chars:", sum(r["chars"] for r in passing))
