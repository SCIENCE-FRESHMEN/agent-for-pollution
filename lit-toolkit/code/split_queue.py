# -*- coding: utf-8 -*-
"""把队列拆成 N 份，分给不同同学各自下载（互不重复）。
用法：
    python code/split_queue.py 5          # 把当前队列平均拆成 5 份
    python code/split_queue.py 5 2        # 共拆 5 份，只生成第 2 份（自己领第 2 份时用）
生成 data/queue_part1.csv ... queue_partN.csv
领到第 k 份的同学，把 config.json 的 "queue" 改成 "data/queue_partk.csv" 即可。
"""
import sys, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import out_utf8, load_config, queue_path, DATA
out_utf8()

def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法: python code/split_queue.py 总份数 [只要第几份]")
    n = int(sys.argv[1])
    only = int(sys.argv[2]) if len(sys.argv) > 2 else None
    src = queue_path(load_config())
    rows = [r for r in csv.DictReader(open(src, encoding="utf-8-sig", newline=""))
            if (r.get("DOI") or r.get("doi") or "").strip()]
    # 均匀切：第 i 份拿 rows[i::n]（顺序交错，各份的期刊构成相近）
    hdr = list(rows[0].keys())
    for i in range(n):
        if only is not None and (i + 1) != only:
            continue
        part = rows[i::n]
        dst = DATA / f"queue_part{i+1}.csv"
        with open(dst, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=hdr)
            w.writeheader()
            w.writerows(part)
        print(f"[split] 第{i+1}份: {dst.name}  {len(part)} 篇")
    tip = f"queue_part{only}.csv" if only else "queue_part<你的份数>.csv"
    print(f'[split] 完成。领到自己那份的同学：用记事本把 config.json 里 "queue" 一行改为 "data/{tip}" 即可')

if __name__ == "__main__":
    main()
