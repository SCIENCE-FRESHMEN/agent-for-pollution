# -*- coding: utf-8 -*-
"""revised 交付 QA（v3）：版本断言 + A 新旧一致 + 三场景摘要 + D 对账 + E 完整性。"""
import io
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\25416\Desktop\agent for pollution\ThetaVerse\src")
DELIV = Path(r"C:\Users\25416\Desktop\agent for pollution\task\交付_模拟验证与三场景接入_20261023_revised")

checks = []
def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(("PASS " if ok else "FAIL "), name, ("| " + detail if detail else ""))

# 版本
import thetaverse as tv
check("thetaverse 版本 = 0.3.0", getattr(tv, "__version__", "") == "0.3.0", str(getattr(tv, "__version__", "?")))

# A
A = DELIV / "A_模拟验证"
m = json.loads((A / "validation_metrics_030.json").read_text(encoding="utf-8"))
old = json.loads(Path(r"C:\Users\25416\Desktop\agent for pollution\task\交付_模拟验证与三场景接入_20261020\A_模拟验证\validation_metrics.json").read_text(encoding="utf-8"))
check("A V1 召回与 10-20 一致", m["V1"]["recall"] == old["V1_gene_layer"]["gene_recall"], f'{m["V1"]["recall"]}')
check("A V1 精确率一致", m["V1"]["precision"] == old["V1_gene_layer"]["gene_precision"])
check("A V2 正确/误配一致", m["V2"]["correct"] == old["V2_protein_layer"]["correct_source"]
      and m["V2"]["wrong"] == old["V2_protein_layer"]["wrong_source"] == 0)
check("A 预测数一致", m["predicted"] == old["V2_protein_layer"]["predicted_total"])
check("A caller 走适配层且有记录", "pyrodigal" in m["gene_caller"], m["gene_caller"][:60])
check("A FAA 非空", (A / "mock_pyrodigal.faa").stat().st_size > 10000)

# B
B = DELIV / "B_三场景接入" / "运行演示"
times = {}
for sc in ["mag", "16s", "taxon"]:
    r = json.loads((B / sc / "运行摘要.json").read_text(encoding="utf-8"))
    times[sc] = r["elapsed_seconds"]
    check(f"B {sc} exit=ok", r.get("exit") == "ok")
s2 = json.loads((B / "16s" / "thetaverse分析输出_revised" / "stats_A2.json").read_text(encoding="utf-8"))
check("B 16s ThetaData 34×770 不变", s2["thetadata_shape"] == [34, 770], str(s2["thetadata_shape"]))
p3 = json.loads((B / "taxon" / "NCBI下载" / "provenance_A3.json").read_text(encoding="utf-8"))
check("B taxon 组装一致", p3["steps"]["esummary"]["assemblyaccession"] == "GCF_000786775.1")

# D
D = DELIV / "D_经验库"
rec = json.loads((D / "建库对账.json").read_text(encoding="utf-8"))
check("D 对账全 PASS", all(rec["checks"].values()))
con = sqlite3.connect(D / "盐湖经验库.db")
check("D SQLite 完整", con.execute("PRAGMA quick_check").fetchone()[0] == "ok")
check("D genomes 58171", con.execute("SELECT COUNT(*) FROM genomes").fetchone()[0] == 58171)
con.close()

# C/E
check("C 文档存在且含复验头注", "0.3.0" in (DELIV / "C_Agent流程" / "Agent数据分析流程与接入说明.md").read_text(encoding="utf-8")[:600])
E = DELIV / "E_专利移交"
check("E 三件齐全", (E / "环境工程专利OCR补全移交_20261020.zip").exists()
      and (E / "移交MD5.txt").exists() and (E / "移交说明.md").exists())

n_fail = sum(1 for _, ok, _ in checks if not ok)
rep = "\n".join(f"[{'PASS' if ok else 'FAIL'}] {n} {d}" for n, ok, d in checks)
(DELIV / "scripts" / "QA报告_v3.txt").write_text(f"revised QA共{len(checks)}项，失败{n_fail}项\n\n{rep}\n", encoding="utf-8")
print(f"\nQA done: {len(checks)} checks, {n_fail} failed")
