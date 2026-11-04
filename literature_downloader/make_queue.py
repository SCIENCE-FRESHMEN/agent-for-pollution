# -*- coding: utf-8 -*-
"""
make_queue.py —— 把"待下载清单 xlsx"转成下载器要的 remaining.csv。

下载器 downloader_v4.py 按列读取 remaining.csv: DOI, Title, Publisher。
本脚本从 split_three_v3.py 产出的 xlsx
（剩余待下载_汇总.xlsx 或 待下载_第X份.xlsx）提取待下文献，
可选 --rescan 重新扫描磁盘剔除已下载项，输出 remaining.csv。

用法:
  python make_queue.py --input 待下载_第1份.xlsx --output remaining_1.csv
  python make_queue.py --input 剩余待下载_汇总.xlsx --output remaining.csv --rescan
"""
import argparse, csv, io, os, re, sys
from pathlib import Path
import openpyxl

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)


def sn(d):
    return re.sub(r'[<>:"/\\|?*]', "_", d).lower()


def real_pdf_stems(lit_root):
    stems = set()
    for p in Path(lit_root).rglob("*.pdf"):
        try:
            if p.stat().st_size >= 1024 and p.read_bytes()[:5] == b"%PDF-":
                stems.add(p.stem.lower())
        except OSError:
            continue
    return stems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="待下载 xlsx（剩余待下载_汇总 或 待下载_第X份）")
    ap.add_argument("--output", default="remaining.csv")
    ap.add_argument("--rescan", action="store_true", help="重新扫描磁盘，剔除已下载的 DOI")
    ap.add_argument("--lit-root", default=os.environ.get("LIT_ROOT", r"D:\Compatible_solute_project"))
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.input, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h) if h is not None else "" for h in rows[0]]
    i_doi = hdr.index("DOI") if "DOI" in hdr else 0
    i_title = hdr.index("标题") if "标题" in hdr else 1
    i_status = hdr.index("状态") if "状态" in hdr else None

    have = real_pdf_stems(args.lit_root) if args.rescan else set()
    out = []
    for r in rows[1:]:
        doi = str(r[i_doi] or "").strip()
        if not doi or doi.lower() == "none":
            continue
        if i_status is not None and str(r[i_status] or "").strip() == "已下载":
            continue
        if args.rescan and sn(doi) in have:
            continue
        title = str(r[i_title] or "").strip()
        out.append((doi, title, ""))   # Publisher 留空，下载器仅用于日志
    wb.close()

    with open(args.output, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["DOI", "Title", "Publisher"])
        for row in out:
            w.writerow(row)
    print(f"写入 {len(out)} 条 -> {args.output}")


if __name__ == "__main__":
    main()
