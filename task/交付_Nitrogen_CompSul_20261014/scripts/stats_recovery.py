# -*- coding: utf-8 -*-
"""
stats 恢复脚本：首次扫描已完整跑完（两个源文件均打印"完成"），仅最后写 stats JSON 时
因 bytes 键崩溃。本脚本从 (a) 运行日志中的完成行恢复 total/malformed，
(b) 流式回读两个输出 TSV 恢复 per-source/per-KO 计数，重建 stats_extraction.json。
之后 run_qa.py 的全量重扫字节级复核会独立验证输出与源文件的一致性。
"""
import json
import re
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR.parent
TASK_DIR = SCRIPT_DIR.parents[1]
NIT_OUT = OUT_DIR / "1Nitrogen" / "氮循环KO命中行_env_ench合并.tsv"
CS_OUT = OUT_DIR / "2CompSul" / "相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv"
LOG = SCRIPT_DIR / "运行日志_首次全量扫描.txt"
STATS_OUT = SCRIPT_DIR / "stats_extraction.json"

stats = {"meta": None, "files": {}}

# (a) 从日志恢复 total/malformed/行数
done_re = re.compile(r"(\w+) 完成: total=([\d,]+) nit=([\d,]+) cs=([\d,]+) malformed=(\d+)")
for m in done_re.finditer(LOG.read_text(encoding="utf-8")):
    src, total, nit, cs, mal = m.groups()
    stats["files"][src] = {"total": int(total.replace(",", "")),
                           "nit_lines": int(nit.replace(",", "")),
                           "cs_lines": int(cs.replace(",", "")),
                           "malformed": int(mal)}
assert set(stats["files"]) == {"env", "ench"}, f"日志缺完成行: {list(stats['files'])}"

# (b) 从输出回读恢复 per-source 行数与 KO 计数（一行可含多个 KO，行数按行计）
multi_ko = {}
for key, path in [("nit", NIT_OUT), ("cs", CS_OUT)]:
    per_src_lines = {"env": 0, "ench": 0}
    per_src_ko = {"env": Counter(), "ench": Counter()}
    multi_ko[key] = 0
    with open(path, "rb") as f:
        f.readline()
        for raw in f:
            fields = raw.rstrip(b"\n").split(b"\t")
            src = fields[13].decode()
            if src not in per_src_lines:
                raise SystemExit(f"意外的 source 字段: {fields[:5]} ... {fields[13]!r}")
            per_src_lines[src] += 1
            kos = fields[14].split(b",")
            if len(kos) > 1:
                multi_ko[key] += 1
            for k in kos:
                per_src_ko[src][k.decode()] += 1
    for src in ("env", "ench"):
        stats["files"][src][f"{key}_lines_readback"] = per_src_lines[src]
        stats["files"][src][f"{key}_ko_counts"] = dict(per_src_ko[src])
    stats[f"{key}_multi_ko_rows"] = multi_ko[key]

# 行数自检：输出回读行数 == 日志完成行的计数（KO 实例数可大于行数，属多 KO 行）
for src, f in stats["files"].items():
    assert f["nit_lines_readback"] == f["nit_lines"], (src, f["nit_lines_readback"], f["nit_lines"])
    assert f["cs_lines_readback"] == f["cs_lines"], (src, f["cs_lines_readback"], f["cs_lines"])
print("行数交叉核验通过（日志计数 == 输出回读行数）")
print(f"多KO行: nitrogen={stats['nit_multi_ko_rows']}, compsul={stats['cs_multi_ko_rows']}")

# 字典元数据（与 run_extraction.load_dicts 相同逻辑）
import openpyxl
JOIN = " // "
wb = openpyxl.load_workbook(TASK_DIR / "Nitrogen_3files" / "氮循环Knumber_process.xlsx",
                            read_only=True, data_only=True)
nit_kos = []
for i, row in enumerate(wb.worksheets[0].iter_rows(values_only=True)):
    if i == 0:
        continue
    if row[0]:
        nit_kos.append(str(row[0]).strip())
wb.close()
wb = openpyxl.load_workbook(TASK_DIR / "2CompSul" / "Comp_Sul transDB.xlsx",
                            read_only=True, data_only=True)
cs_kos = []
for row in wb.worksheets[0].iter_rows(values_only=True):
    if row[0] is not None:
        cs_kos.append(str(row[0]).strip())
wb.close()
from collections import Counter as C
stats["meta"] = {
    "nit_dict_rows": len(nit_kos),
    "nit_dict_unique_ko": len(set(nit_kos)),
    "nit_dict_duplicates": [k for k, c in C(nit_kos).items() if c > 1],
    "cs_dict_rows": len(cs_kos),
    "cs_dict_unique_ko": len(set(cs_kos)),
    "cs_dict_duplicates": [k for k, c in C(cs_kos).items() if c > 1],
    "dict_overlap_nit_vs_cs": sorted(set(nit_kos) & set(cs_kos)),
}

nit_hit, cs_hit = set(), set()
for f in stats["files"].values():
    nit_hit |= set(f["nit_ko_counts"])
    cs_hit |= set(f["cs_ko_counts"])
stats["nit_never_matched"] = sorted(set(nit_kos) - nit_hit)
stats["cs_never_matched"] = sorted(set(cs_kos) - cs_hit)

# 行数自检：输出回读的总行数必须等于日志完成行里的计数
print(json.dumps({s: {k: v for k, v in f.items() if not k.endswith("ko_counts")}
                  for s, f in stats["files"].items()}, ensure_ascii=False))
STATS_OUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK stats 已恢复 -> {STATS_OUT}")
