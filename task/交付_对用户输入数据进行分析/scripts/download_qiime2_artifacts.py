# -*- coding: utf-8 -*-
"""A2 前置（带重试）：补齐 QIIME 2 官方 moving-pictures 教程 artifacts。"""
import io, sys, time, hashlib, urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DOCS = "https://docs.qiime2.org/2024.10/data/tutorials/moving-pictures"
DATA = "https://data.qiime2.org/2024.10/tutorials/moving-pictures"
OUT = Path(r"C:\Users\25416\Desktop\agent for pollution\task\交付_剩余任务_20261020\A_用户输入分析\A2_16S_qiime2\artifacts")
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}

WANT = {
    "sample_metadata.tsv": [f"{DATA}/sample_metadata.tsv", f"{DOCS}/sample_metadata.tsv"],
    "table.qza": [f"{DOCS}/table.qza", f"{DOCS}/table-dada2.qza"],
    "taxonomy.qza": [f"{DOCS}/taxonomy.qza"],
    "rooted-tree.qza": [f"{DOCS}/rooted-tree.qza"],
}

for name, urls in WANT.items():
    p = OUT / name
    if p.exists() and p.stat().st_size > 1000:
        print(f"SKIP {name} (已有 {p.stat().st_size} B)")
        continue
    ok = False
    for url in urls:
        for attempt in range(5):
            try:
                data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
                if len(data) < 100:
                    print(f"TINY {url}: {len(data)}B"); continue
                p.write_bytes(data)
                print(f"OK {name}: {len(data)} bytes md5={hashlib.md5(data).hexdigest()[:12]} <- {url}")
                ok = True
                break
            except Exception as e:
                print(f"retry{attempt+1} {url}: {e}")
                time.sleep(3 * (attempt + 1))
        if ok:
            break
    if not ok:
        print(f"FAIL {name}")
