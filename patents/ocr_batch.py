# -*- coding: utf-8 -*-
"""全量 OCR：110 份无文本层扫描件（+1 读取失败件尝试 PyMuPDF 抢救）。
3 进程并行，158dpi，逐文件 checkpoint，预算 150 分钟。产出 txt/<pub>_OCR.txt + 全量质量报告。
"""
import os, sys, io, csv, json, time
import multiprocessing as mp
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
PROG = os.path.join(BASE, "ocr_batch_progress.json")
ZOOM = 2.3

def scan_list():
    rows = list(csv.DictReader(open(os.path.join(BASE, "extract_manifest.csv"), encoding="utf-8-sig")))
    low = [r["file"][:-4] for r in rows if int(r["chars"] or 0) < 200]
    extra = []
    if "CN102770542A" in {r["file"][:-4] for r in rows} or True:
        man = {r["file"][:-4]: r for r in rows}
        r = man.get("CN102770542A")
        if r is None or "read:" in (r.get("error") or ""):
            extra = ["CN102770542A"]
    done = set(json.load(open(PROG, encoding="utf-8"))) if os.path.exists(PROG) else set()
    todo = [p for p in sorted(low + extra) if p not in done and not os.path.exists(os.path.join(BASE, "txt", p + "_OCR.txt"))]
    return todo

def ocr_one(pub):
    os.environ["OMP_NUM_THREADS"] = "3"
    os.environ["ORT_INTRA_OP_NUM_THREADS"] = "3"
    import pymupdf
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    p = os.path.join(BASE, "pdf", pub + ".pdf")
    t0 = time.time()
    try:
        doc = pymupdf.open(p)
    except Exception as e:
        return pub, 0, 0, f"open_fail:{str(e)[:60]}"
    parts, lowp = [], 0
    npages = len(doc)
    for i, pg in enumerate(doc, 1):
        try:
            pix = pg.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM))
            res, _ = ocr(pix.tobytes("png"))
        except Exception:
            res = None
        if not res:
            parts.append(f"\n===== PAGE {i} (0 boxes) =====\n")
            continue
        items = sorted(res, key=lambda r: (min(pt[1] for pt in r[0]), min(pt[0] for pt in r[0])))
        lines = [it[1] for it in items]
        scores = [float(it[2]) for it in items]
        mean = sum(scores) / len(scores)
        txt = "\n".join(lines)
        if mean < 0.82:
            lowp += 1
        parts.append(f"\n===== PAGE {i} ({len(lines)} boxes, conf {mean:.3f}) =====\n" + txt)
    full = "".join(parts)
    with open(os.path.join(BASE, "txt", pub + "_OCR.txt"), "w", encoding="utf-8") as f:
        f.write(full)
    return pub, npages, len(full), f"lowconf_pages={lowp};{time.time()-t0:.0f}s"

if __name__ == "__main__":
    todo = scan_list()
    print(f"[batch] pending={len(todo)}", flush=True)
    t0 = time.time()
    results = []
    with mp.Pool(3) as pool:
        for pub, np_, chars, info in pool.imap_unordered(ocr_one, todo):
            results.append((pub, np_, chars, info))
            done = json.load(open(PROG, encoding="utf-8")) if os.path.exists(PROG) else {}
            done[pub] = {"pages": np_, "chars": chars, "info": info}
            json.dump(done, open(PROG, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"[batch] {len(results)}/{len(todo)} {pub} pages={np_} chars={chars} {info} elapsed={time.time()-t0:.0f}s", flush=True)
    print(f"[batch] ALL DONE {len(results)} files in {time.time()-t0:.0f}s", flush=True)
