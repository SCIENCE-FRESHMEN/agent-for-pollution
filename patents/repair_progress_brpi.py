# -*- coding: utf-8 -*-
"""最小修复：以 txt 实存 + 运行日志为事实源，重建 progress.json 的 BRPI 条目。"""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
P = Path(r"C:\Users\25416\Desktop\agent for pollution\patents")

# 事实源 1：txt 实存文件（UTF-8 字符数）
txt = P / "txt" / "BRPI0618328A2_OCR.txt"
content = txt.read_text(encoding="utf-8", errors="replace")
chars = len(content)
n_pages = content.count("===== PAGE")

# 事实源 2：当日运行日志（含 lowconf 与耗时）
log_text = (P / "ocr_最终补跑2件_20261020.txt").read_text(encoding="utf-8", errors="replace")
info_line = [l for l in log_text.splitlines() if "BRPI0618328A2: pages=" in l]
info = info_line[0].split("lowconf_pages=")[1] if info_line and "lowconf_pages=" in info_line[0] else ""
lowconf = info.split(";")[0] if info else "unknown"

prog = json.loads((P / "ocr_batch_progress.json").read_text(encoding="utf-8"))
prog["BRPI0618328A2"] = {"pages": n_pages, "chars": chars,
                         "info": f"lowconf_pages={lowconf};1515s（误删还原后按 txt 实存+运行日志重建）"}
(P / "ocr_batch_progress.json").write_text(json.dumps(prog, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"progress.json 重建 BRPI 条目: pages={n_pages} chars={chars} lowconf={lowconf}，总条目={len(prog)}")
print(f"字符数与运行日志一致: {chars == 418164}；页数与日志一致: {n_pages == 290}")
