# -*- coding: utf-8 -*-
"""Final corpus adjudication: homonym exclusions + CN110381917A metadata patch + regen."""
import os, sys, io, json, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")

with open(os.path.join(AN, "grounding_records.json"), encoding="utf-8") as f:
    recs = json.load(f)

HOMONYM = {
    "US3046198A": "blood-compatible solute protein（血液相容溶质蛋白，材料学义）",
    "US3991759A": "biologically compatible solute（=生物相容性溶质，干眼NaCl，非极端菌渗透调溶质概念）",
    "US5151335A": "电解液用语 a compatible solute（Li盐，电化学义）",
    "US5166010A": "电解液用语 a compatible solute（电化学义）",
    "US5175068A": "电解液用语 a compatible solute（电化学义）",
    "US5238761A": "电解液用语 a compatible solute（电化学义）",
    "US6022643A": "电解液用语 a compatible solute such as LiI/LiBr（电池义）",
    "US6120941A": "电解液用语 a compatible solute such as LiI/LiBr（电池义）",
    "US6352798B1": "电解液用语 a compatible solute such as LiI/LiBr（电池义）",
    "US7516788B2": "compatible solute fluid（油井示踪提取液，采矿义）",
    "US7557485B1": "compatible solute compounds（离子导电电解质，电化学义）",
    "US9683448B2": "compatible solute and solvent（热障涂层浸渍，材料学义）",
    "US20180043618A1": "compatible solute（3D打印包埋材料，塑料/金属/玻璃，材料学义）",
}
patched = 0
for r in recs:
    if r["pub"] in HOMONYM:
        r["verdict"] = "剔除"
        r["criterion"] = "同形异义剔除(词组命中但非相容性溶质概念): " + HOMONYM[r["pub"]]
        patched += 1
    if r["pub"] == "CN110381917A":
        r["title"] = "相容性溶质的用途"
        r["assignee"] = "默克专利股份有限公司(Merck Patent GmbH)"
        r["filing"] = "2018-03-05"
        r["priority"] = "2017-03-06(EP17159311.4)"
        r["country"] = "CN"

with open(os.path.join(AN, "grounding_records.json"), "w", encoding="utf-8") as f:
    json.dump(recs, f, ensure_ascii=False)
print("homonym-excluded:", patched)

# regen compliance.csv
with open(os.path.join(AN, "compliance.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=[k for k in recs[0] if k != "snippets"], extrasaction="ignore")
    w.writeheader()
    for r in recs:
        w.writerow({k: v for k, v in r.items() if k != "snippets"})

from collections import Counter
passing = [r for r in recs if r["verdict"] == "纳入"]
print("FINAL PASS:", len(passing))
print("FINAL verdicts:", dict(Counter(r["verdict"] for r in recs)))
print("PASS total chars:", sum(r["chars"] for r in passing))

# regen review table
def year(r):
    for k in ("publication", "filing", "priority"):
        v = (r.get(k) or "")[:4]
        if v.isdigit():
            return v
    return "?"
lines = ["| # | 公开号 | 国 | 年 | 申请人 | 标题 | 校验依据 | 检出溶质 | 命中次数 |",
         "|---|--------|----|----|--------|------|----------|----------|----------|"]
for i, r in enumerate(sorted(passing, key=lambda x: (x["country"], x["pub"])), 1):
    crit = {"EN完整词组命中": "EN", "中文等价术语命中(相容性溶质)": "ZH", "EN词组+中文术语均命中": "EN+ZH"}.get(r["criterion"], "EU/裁定")
    sol = (r["solutes"] or "").replace("四氢嘧啶/tetrahydropyrimidine(中文语境)", "THP").replace("betaine(unspecified)", "betaine").replace("glycine betaine", "GB").replace("di-myo-inositol-phosphate", "DIP").replace("hydroxyectoine", "Hect").replace("mannosylglycerol", "MG").replace("glucosylglycerol", "GG").replace("dimsqrt", "DGP")
    title = (r["title"] or "（元数据缺失）").replace("|", "/")[:85]
    lines.append(f"| {i} | {r['pub']} | {r['country']} | {year(r)} | {(r['assignee'] or '（元数据缺失）')[:38]} | {title} | {crit} | {sol[:55]} | {r['phrase_count'] + r['zh_term_count']} |")
with open(os.path.join(AN, "review_table.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("review_table regenerated")
