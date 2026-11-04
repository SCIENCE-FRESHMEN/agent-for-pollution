# -*- coding: utf-8 -*-
"""Batch-extract text from patents/pdf/*.pdf into patents/txt/*.txt with a manifest."""
import os, sys, io, csv, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pypdf

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
PDF_DIR = os.path.join(BASE, "pdf")
TXT_DIR = os.path.join(BASE, "txt")
os.makedirs(TXT_DIR, exist_ok=True)

pdfs = sorted(f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf"))
rows = []
t0 = time.time()
for i, fn in enumerate(pdfs, 1):
    stem = fn[:-4]
    src = os.path.join(PDF_DIR, fn)
    dst = os.path.join(TXT_DIR, stem + ".txt")
    pages, chars, err, enc = 0, 0, "", False
    try:
        r = pypdf.PdfReader(src)
        if r.is_encrypted:
            try:
                r.decrypt("")
                enc = True
            except Exception as e:
                err = "encrypt:" + str(e)[:80]
                enc = True
        if not err:
            parts = []
            pages = len(r.pages)
            for p in r.pages:
                try:
                    parts.append(p.extract_text() or "")
                except Exception as e:
                    parts.append("")
                    err = (err + "|" if err else "") + "page:" + str(e)[:60]
            text = "\n".join(parts)
            chars = len(text)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(text)
    except Exception as e:
        err = (err + "|" if err else "") + "read:" + str(e)[:120]
    rows.append({"file": fn, "pages": pages, "chars": chars, "encrypted": enc, "error": err})
    if i % 25 == 0 or i == len(pdfs):
        print(f"[{i}/{len(pdfs)}] {time.time()-t0:.0f}s  last={fn} pages={pages} chars={chars} err={err[:60]}", flush=True)

with open(os.path.join(BASE, "extract_manifest.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["file", "pages", "chars", "encrypted", "error"])
    w.writeheader()
    w.writerows(rows)

empty = [r for r in rows if r["chars"] < 200]
print("DONE", len(rows), "pdfs;", len(empty), "low/empty-text (likely scanned):")
for r in empty:
    print("  LOW", r["file"], r["chars"])
