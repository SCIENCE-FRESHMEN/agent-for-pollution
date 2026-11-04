# -*- coding: utf-8 -*-
"""误删还原对账（只读）：还原版 patents vs 20261020 会话终态，核到字节/行数/SHA-256。"""
import hashlib
import csv
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
P = Path(r"C:\Users\25416\Desktop\agent for pollution\patents")
CSV = P / "patent_pdf_download_status.csv"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


rows = {r["publication_number"]: r for r in csv.DictReader(open(CSV, encoding="utf-8-sig"))}
report = []

# 1) progress json
prog = json.loads((P / "ocr_batch_progress.json").read_text(encoding="utf-8"))
report.append(("progress.json 条目数", len(prog), "预期 108（106 历史+BRPI+CN102770542A受阻记录）"))
brpi = prog.get("BRPI0618328A2", {})
report.append(("progress BRPI 条目", f'{brpi.get("pages")}/{brpi.get("chars")}/{brpi.get("info","")}', "预期 290/418164/lowconf 160"))
cn = prog.get("CN102770542A", {})
report.append(("progress CN102770542A 受阻记录", f'{cn.get("pages")}/{cn.get("chars")}', "预期 0/0"))

# 2) PDF SHA-256 核验
EXPECT_PDFS = ["CN102770542A", "CN106365887A", "CN108658243A", "WO2005014488A1", "BRPI0618328A2"]
for pid in EXPECT_PDFS:
    p = P / "pdf" / f"{pid}.pdf"
    if not p.exists():
        report.append((f"pdf/{pid}", "缺失", "需重下"))
        continue
    rec = rows.get(pid, {}).get("sha256", "")
    actual = sha256(p)
    report.append((f"pdf/{pid}", f"{p.stat().st_size}B sha_match={actual == rec}", "SHA-256 vs 下载记录"))

# 3) txt 本轮新增件
t = P / "txt" / "BRPI0618328A2_OCR.txt"
report.append(("txt/BRPI_OCR", f"{t.stat().st_size}B" if t.exists() else "缺失",
               "预期 418164B（若缺失需重 OCR 25min）"))
t2 = P / "txt" / "CN102770542A_OCR.txt"
report.append(("txt/CN102770542A_OCR", f"{t2.stat().st_size}B" if t2.exists() else "缺失（可接受，属受阻件）", "预期 0B 占位或缺失"))

# 4) 既有 107 件成品与对账文件
for rel, expect in [("RAG/产出/环境工程专利/05_OCR文本", 3),
                    ("extract_manifest.csv", None), ("ocr_todo.json", None)]:
    p = P / rel
    if p.is_dir():
        n = sum(1 for x in p.iterdir() if x.is_file())
        report.append((rel, f"{n} files", f"预期 ≥{expect}" if expect else "存在即可"))
    else:
        report.append((rel, "缺失" if not p.exists() else f"{p.stat().st_size}B", "存在即可" if expect is None else f"预期 ≥{expect}"))

# 5) 本轮脚本与日志
for rel in ["ocr_final_2patents.py", "ocr_最终补跑2件_20261020.txt"]:
    p = P / rel
    report.append((rel, "存在" if p.exists() else "缺失（不影响数据，可从交付记录重建）", "脚本/日志"))

# 6) BRPI txt 内容粗检（页数行计数）
if t.exists() and t.stat().st_size > 0:
    n_pages = t.read_text(encoding="utf-8", errors="replace").count("===== PAGE")
    report.append(("txt/BRPI_OCR 页数行", n_pages, "预期 290"))

print(f"{'项目':<38} {'实况':<40} 预期/判定")
print("-" * 110)
for name, actual, expect in report:
    print(f"{name:<38} {str(actual):<40} {expect}")

n_missing = sum(1 for _, a, _ in report if str(a).startswith(("缺失", "需重下")))
print("-" * 110)
print(f"对账项：{len(report)}，缺失/需修复：{n_missing}")
( P / "还原对账_原始数据.json").write_text(json.dumps(
    [{"item": n, "actual": str(a), "expect": e} for n, a, e in report],
    ensure_ascii=False, indent=2), encoding="utf-8")
