# -*- coding: utf-8 -*-
"""
零命中 KO 复核：对 stats 中从未命中的 KO，直接在两个源文件做字节级存在性扫描。
若字节串都不存在 -> 确证数据中确无该 KO（非正则漏配）；
若存在 -> 打印所在行，人工检查是否应命中。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parents[1]
SRC_DIR = TASK_DIR / "Nitrogen_3files"
stats = json.loads((SCRIPT_DIR / "stats_extraction.json").read_text(encoding="utf-8"))
targets = [k.encode() for k in stats["nit_never_matched"]]
print("复核对象:", [t.decode() for t in targets])

files = ["KEGG_des_env_kegg_e-5_num1_similarity30.tsv",
         "KEGG_des_ench_kegg_e-5_num1_similarity30.tsv"]
KO_RE = re.compile(rb"\bK\d{5}\b")
DICT = set(targets)
occurrences = {}
report = [f"复核对象: {', '.join(t.decode() for t in targets)}"]
for fname in files:
    with open(SRC_DIR / fname, "rb", buffering=0) as fin:
        rem = b""
        while True:
            chunk = fin.read(1 << 24)
            if not chunk:
                break
            data = rem + chunk
            rem = data[-32:]          # 跨块边界保护
            for t in targets:
                start = 0
                while True:
                    i = data.find(t, start)
                    if i < 0:
                        break
                    # 确认是完整 KO token（前后非数字字母）
                    line_start = data.rfind(b"\n", 0, i) + 1
                    line_end = data.find(b"\n", i)
                    if line_end < 0:
                        break
                    line = data[line_start:line_end]
                    desc = line.split(b"\t", 12)[-1]
                    if t in KO_RE.findall(desc):
                        occurrences.setdefault(t, []).append((fname, desc[:120]))
                    start = i + 1
        if rem.strip():
            pass
for t in targets:
    n = len(occurrences.get(t, []))
    line = f"{t.decode()}: 源文件中出现于描述列的行数 = {n}"
    print(line)
    report.append(line)
    for fname, desc in occurrences.get(t, [])[:3]:
        d = f"   [{fname}] {desc.decode('utf-8', 'replace')}"
        print(d)
        report.append(d)
verdict = "全部确证零命中（非漏配）" if not occurrences else "存在疑似漏配行，需人工检查"
print("结论:", verdict)
report.append("结论: " + verdict)
open(SCRIPT_DIR / "零命中KO复核.txt", "w", encoding="utf-8").write("\n".join(report) + "\n")
