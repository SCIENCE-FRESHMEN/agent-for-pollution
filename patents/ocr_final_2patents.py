# -*- coding: utf-8 -*-
"""E 最终补跑：仅 OCR 真缺的 2 件（CN102770542A + BRPI0618328A2），其余 3 件已有成品。"""
import sys, json, hashlib, time, csv, urllib.request
from pathlib import Path

BASE = Path(r"C:\Users\25416\Desktop\agent for pollution\patents")
PROG = BASE / "ocr_batch_progress.json"
UA = {"User-Agent": "Mozilla/5.0"}
(BASE / "txt").mkdir(exist_ok=True)

rows = {r["publication_number"]: r for r in csv.DictReader(open(BASE / "patent_pdf_download_status.csv", encoding="utf-8-sig"))}

# BRPI PDF 下载 + SHA256 核验
brpi_pdf = BASE / "pdf" / "BRPI0618328A2.pdf"
if not brpi_pdf.exists():
    r = rows["BRPI0618328A2"]
    data = urllib.request.urlopen(urllib.request.Request(r["pdf_url"], headers=UA), timeout=600).read()
    sha = hashlib.sha256(data).hexdigest()
    brpi_pdf.write_bytes(data)
    print(f"[dl] BRPI0618328A2: {len(data)}B sha256_match={sha == r['sha256']}", flush=True)

sys.path.insert(0, str(BASE))
import ocr_batch  # noqa: E402

done = json.loads(PROG.read_text(encoding="utf-8"))
for pub in ["CN102770542A", "BRPI0618328A2"]:
    if (BASE / "txt" / f"{pub}_OCR.txt").exists():
        print(f"[skip] {pub} 已有 OCR 文本", flush=True)
        continue
    t0 = time.time()
    pub2, np_, chars, info = ocr_batch.ocr_one(pub)
    done[pub2] = {"pages": np_, "chars": chars, "info": info}
    PROG.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    print(f"[done] {pub2}: pages={np_} chars={chars} {info} ({time.time()-t0:.0f}s)", flush=True)
print("[final] E 项 OCR 全部补齐", flush=True)
