# -*- coding: utf-8 -*-
"""把任意 Excel/CSV 文献清单转成下载队列 data/my_queue.csv（含 DOI 列即可）。
用法：python code/make_queue.py 清单.xlsx
"""
import sys, re, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import out_utf8, sn, safe_dir, DL, DATA
out_utf8()

def find_col(header, keys):
    for i, h in enumerate(header):
        hl = str(h or "").strip().lower()
        if any(k == hl or k in hl for k in keys):
            return i
    return None

def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法: python code/make_queue.py 清单.xlsx|清单.csv")
    src = Path(sys.argv[1])
    if not src.exists():
        raise SystemExit(f"找不到文件: {src}")

    recs = []
    if src.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            try:
                hdr = next(it)
            except StopIteration:
                continue
            ci = find_col(hdr, ("doi",))
            cj = find_col(hdr, ("期刊", "journal", "来源", "container"))
            if ci is None:
                for r in it:
                    if r is None:
                        continue
                    for cell in r:
                        if cell and re.match(r"^10\.\d{4,9}/\S+$", str(cell).strip()):
                            recs.append((str(cell).strip(), ""))
                            break
                continue
            for r in it:
                if r is None or r[ci] is None:
                    continue
                doi = str(r[ci]).strip()
                if not re.match(r"^10\.\d{4,9}/", doi):
                    continue
                j = str(r[cj]).strip() if (cj is not None and r[cj] is not None) else ""
                recs.append((doi, j))
        wb.close()
    else:
        with open(src, encoding="utf-8-sig", newline="") as f:
            dr = csv.reader(f)
            hdr = next(dr, None)
            ci = find_col(hdr or [], ("doi",))
            cj = find_col(hdr or [], ("期刊", "journal", "来源"))
            if ci is None:
                for r in dr:
                    for cell in r:
                        if cell and re.match(r"^10\.\d{4,9}/\S+$", str(cell).strip()):
                            recs.append((str(cell).strip(), ""))
                            break
            else:
                for r in dr:
                    if r and r[ci] and re.match(r"^10\.\d{4,9}/", r[ci].strip()):
                        j = r[cj].strip() if (cj is not None and cj < len(r)) else ""
                        recs.append((r[ci].strip(), j))

    seen, out = set(), []
    for doi, j in recs:
        k = doi.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append((doi, j))
    have = {p.stem.lower() for p in DL.rglob("*.pdf") if p.stat().st_size >= 20000}
    final = [(d, j) for d, j in out if sn(d) not in have]

    dst = DATA / "my_queue.csv"
    DATA.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["DOI", "Journal"])
        for d, j in final:
            w.writerow([d, j])
    print(f"[make_queue] 输入 {len(recs)} 行 -> 去重后 {len(out)} -> 剔除已下载 {len(out)-len(final)} -> 写出 {len(final)} 行")
    print(f"[make_queue] 已生成 {dst}")
    print("[make_queue] 请把 config.json 里的 queue 改为: data/my_queue.csv")

if __name__ == "__main__":
    main()
