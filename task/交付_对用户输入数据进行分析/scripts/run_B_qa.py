# -*- coding: utf-8 -*-
"""B 项独立 QA：直接回读输出文件核验，并从源 TSV 独立重数抽查基因组。"""
import io
import json
import re
import sys
import collections
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WS = Path(r"C:\Users\25416\Desktop\agent for pollution")
OUT = WS / "task" / "交付_剩余任务_20261020" / "B_丰度与环境条件"
PREV = WS / "task" / "交付_Nitrogen_CompSul_20261014"
stats = json.loads((WS / "task" / "交付_剩余任务_20261020" / "scripts" / "stats_B.json").read_text(encoding="utf-8"))

checks = []
def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(("PASS " if ok else "FAIL "), name, detail)

# 1. 结构与行数
t1 = OUT / "1_基因组清单与注释丰度统计.tsv"
t2 = OUT / "2_环境条件信息框架.tsv"
with open(t1, encoding="utf-8-sig") as fh:
    h1 = fh.readline().rstrip("\n").split("\t")
    r1 = [l.rstrip("\n").split("\t") for l in fh]
with open(t2, encoding="utf-8-sig") as fh:
    h2 = fh.readline().rstrip("\n").split("\t")
    r2 = [l.rstrip("\n").split("\t") for l in fh]
check("表1行数=stats.union", len(r1) == stats["totals"]["distinct_genomes_union"], f"{len(r1)} vs {stats['totals']['distinct_genomes_union']}")
check("表2行数=表1行数", len(r2) == len(r1))
check("表1列数=18", all(len(r) == len(h1) for r in r1))
check("表2列数=12", all(len(r) == len(h2) for r in r2))
check("genome_id 无空值", all(r[0].strip() for r in r1) and all(r[0].strip() for r in r2))
check("表1与表2基因组集合一致", {r[0] for r in r1} == {r[0] for r in r2})

# 2. 行数对账（从输出文件直接累加，独立于扫描代码路径）
col = h1.index
nit = sum(int(r[col("氮循环_命中行数")]) for r in r1)
tr = sum(int(r[col("转运_命中行数")]) for r in r1)
se = sum(int(r[col("合成_env_记录数")]) for r in r1)
sx = sum(int(r[col("合成_ench_记录数")]) for r in r1)
check("氮循环命中行数累加=552808", nit == 552_808, str(nit))
check("转运命中行数累加=1184624", tr == 1_184_624, str(tr))
check("合成env累加=79000", se == 79_000, str(se))
check("合成ench累加=33475", sx == 33_475, str(sx))

# 3. 缺失标注计数（表2 每个元数据列都应为全缺失）
for cname in ["盐度", "pH", "温度", "地理位置", "采样时间", "培养条件"]:
    n_miss = sum(1 for r in r2 if r[h2.index(cname)].startswith("[缺失]"))
    check(f"表2[{cname}]全缺失标注", n_miss == len(r2), f"{n_miss}/{len(r2)}")

# 4. 抽查3个基因组：从源TSV独立重数
BIN_RE = re.compile(r"^(.*_bin\d+)_\d+(?:_\d+)?$")
TAIL_RE = re.compile(r"^(.+)_(\d+)_(\d+)$")
def parse(q):
    m = BIN_RE.match(q)
    if m: return m.group(1)
    m = TAIL_RE.match(q)
    if m: return m.group(1)
    return q

spots = {"zrnmc_2022_w_bin94": None, "xcd_2021_s_bin658": None, "ABH_460": None}
for label, path in [("nitrogen", PREV / "1Nitrogen" / "氮循环KO命中行_env_ench合并.tsv"),
                    ("transport", PREV / "2CompSul" / "相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv")]:
    cnt = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as fh:
        fh.readline()
        for line in fh:
            g = parse(line.split("\t", 1)[0])
            if g in spots:
                cnt[(g, label)] += 1
    for gg in spots:
        rows = cnt[(gg, label)]
        trow = next(r for r in r1 if r[0] == gg)
        expect = int(trow[col("氮循环_命中行数") if label == "nitrogen" else col("转运_命中行数")])
        check(f"抽查{gg}[{label}]", rows == expect, f"重数{rows} vs 表{expect}")

# 5. env/ench 零混杂
srcs = collections.Counter(r[col("source_file")] for r in r1)
check("无 env+ench 混杂基因组", srcs.get("env+ench", 0) == 0, str(dict(srcs)))

n_fail = sum(1 for _, ok, _ in checks if not ok)
report = "\n".join(f"[{'PASS' if ok else 'FAIL'}] {n} {d}" for n, ok, d in checks)
(WS / "task" / "交付_剩余任务_20261020" / "scripts" / "QA_B报告.txt").write_text(
    f"B项QA共{len(checks)}项，失败{n_fail}项\n\n{report}\n", encoding="utf-8")
print(f"\nQA done: {len(checks)} checks, {n_fail} failed")
