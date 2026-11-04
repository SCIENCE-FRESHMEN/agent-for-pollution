# -*- coding: utf-8 -*-
"""OCR the 3 scanned env patents (RapidOCR+PyMuPDF; MinerU unavailable offline).
Output: 环境工程专利/05_OCR文本/<pub>_OCR.txt + OCR质量报告.csv ; texts also copied to patents/txt/ as <pub>_OCR.txt
"""
import os, sys, io, csv, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pymupdf
from rapidocr_onnxruntime import RapidOCR

SRC = r"C:\Users\25416\Desktop\agent for pollution\patents"
ENV = r"C:\Users\25416\Desktop\agent for pollution\patents\RAG\产出\环境工程专利"
OUTDIR = os.path.join(ENV, "05_OCR文本")
os.makedirs(OUTDIR, exist_ok=True)
PUBS = ["CN108658243A", "WO2005014488A1", "CN106365887A"]
ZOOM = 2.8  # ~200dpi

ocr = RapidOCR()
report = []
t0 = time.time()
for pub in PUBS:
    p = os.path.join(SRC, "pdf", pub + ".pdf")
    doc = pymupdf.open(p)
    parts = []
    for i, pg in enumerate(doc, 1):
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM))
        img = pix.tobytes("png")
        res, _ = ocr(img)
        if not res:
            parts.append(f"\n===== PAGE {i} (0 boxes) =====\n")
            report.append([pub, i, 0, 0.0, "无文本框(纯图页)"])
            continue
        # order by y then x
        items = sorted(res, key=lambda r: (min(pt[1] for pt in r[0]), min(pt[0] for pt in r[0])))
        lines = [it[1] for it in items]
        scores = [float(it[2]) for it in items]
        mean = sum(scores) / len(scores)
        txt = "\n".join(lines)
        parts.append(f"\n===== PAGE {i} ({len(lines)} boxes, conf {mean:.3f}) =====\n" + txt)
        report.append([pub, i, len(lines), round(mean, 3),
                       "OK" if (mean >= 0.85 and len(txt) >= 30) else "低置信页(需复核)"])
        print(f"  {pub} p{i}: {len(lines)} boxes conf={mean:.3f}", flush=True)
    full = "".join(parts)
    with open(os.path.join(OUTDIR, pub + "_OCR.txt"), "w", encoding="utf-8") as f:
        f.write(full)
    with open(os.path.join(SRC, "txt", pub + "_OCR.txt"), "w", encoding="utf-8") as f:
        f.write(full)
    n = len(full)
    print(f"[OCR] {pub} done: {n} chars, {time.time()-t0:.0f}s elapsed", flush=True)

with open(os.path.join(ENV, "OCR质量报告.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["公开号", "页码", "文本框数", "平均置信度", "状态"])
    w.writerows(report)
low = [r for r in report if r[4] != "OK" and r[4] != "无文本框(纯图页)"]
print(f"[OCR] ALL DONE pages={len(report)} low_conf_pages={len(low)} elapsed={time.time()-t0:.0f}s")
