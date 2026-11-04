# -*- coding: utf-8 -*-
"""patents 交付物数字核实 + RAG/ 目录与 产出/ 差异检查"""
import csv, io, os, hashlib
from collections import Counter

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
OUT = io.StringIO()

def count_lines(p):
    with open(p, "rb") as f:
        return sum(1 for _ in f)

# 核实产出数字
kb = os.path.join(BASE, "产出", "RAG知识库")
for fn in ["chunks.jsonl", "chunks_with_tables.jsonl", "theme_digest_chunks.jsonl"]:
    p = os.path.join(kb, fn)
    OUT.write("%s: %d lines\n" % (fn, count_lines(p)))
    with open(p, "rb") as f:
        first = f.readline().decode("utf-8")
    OUT.write("  keys: %r\n" % list(csv.DictReader(io.StringIO(first)).fieldnames)[:16])
for fn in ["formulation_database.csv", "graph_nodes.csv", "graph_edges.csv"]:
    p = os.path.join(BASE, "产出", fn)
    n = count_lines(p) - 1
    OUT.write("%s: %d data rows\n" % (fn, n))
    with open(p, "rb") as f:
        first = f.readline().decode("utf-8-sig")
    OUT.write("  cols: %r\n" % next(csv.reader(io.StringIO(first))))
p = os.path.join(kb, "metadata_index.csv")
OUT.write("metadata_index.csv: %d data rows\n" % (count_lines(p) - 1))
with open(p, "rb") as f:
    first = f.readline().decode("utf-8-sig")
OUT.write("  cols: %r\n" % next(csv.reader(io.StringIO(first))))

# pdf / txt 实况
pdfs = [f for f in os.listdir(os.path.join(BASE, "pdf"))]
ext = Counter(os.path.splitext(f)[1].lower() for f in pdfs)
OUT.write("pdf/ dir: %d files, ext: %r\n" % (len(pdfs), dict(ext)))
txts = os.listdir(os.path.join(BASE, "txt"))
OUT.write("txt/ dir: %d files\n" % len(txts))

# metadata_index 字段与主题分布
with open(os.path.join(kb, "metadata_index.csv"), "rb") as f:
    rows = list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
OUT.write("metadata rows: %d, cols: %r\n" % (len(rows), list(rows[0].keys())))
if "themes" in rows[0]:
    tc = Counter()
    for r in rows:
        for t in (r.get("themes") or "").split(";"):
            t = t.strip()
            if t:
                tc[t] += 1
    OUT.write("theme dist: %r\n" % tc.most_common(10))
else:
    for k in rows[0]:
        OUT.write("  col %s sample: %r\n" % (k, rows[0][k][:40] if isinstance(rows[0][k], str) else rows[0][k]))

# RAG/ 快照 vs 产出/ 差异
def digest_dir(d):
    m = {}
    for root, dirs, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, d)
            try:
                m[rel] = (os.path.getsize(p), hashlib.md5(open(p, "rb").read(1 << 20)).hexdigest())
            except OSError:
                m[rel] = (os.path.getsize(p), "ERR")
    return m

a = digest_dir(os.path.join(BASE, "产出"))
b = digest_dir(os.path.join(BASE, "RAG", "产出"))
only_a = set(a) - set(b)
only_b = set(b) - set(a)
diff = [k for k in set(a) & set(b) if a[k] != b[k]]
OUT.write("\nRAG/产出 vs 产出/: only_in_产出=%d only_in_RAG=%d content_diff=%d\n"
          % (len(only_a), len(only_b), len(diff)))
OUT.write("only_in_产出 sample: %r\n" % list(only_a)[:8])
OUT.write("only_in_RAG sample: %r\n" % list(only_b)[:8])
OUT.write("content_diff: %r\n" % diff[:12])
# RAG 根下除 产出 外还有什么
rest = set()
for root, dirs, files in os.walk(os.path.join(BASE, "RAG")):
    for f in files:
        rest.add(os.path.relpath(os.path.join(root, f), os.path.join(BASE, "RAG")))
OUT.write("RAG/ total files: %d, top-level entries: %r\n"
          % (len(rest), sorted(set(r.split(os.sep)[0] for r in rest))))

with open(os.path.join(BASE, "analysis", "_verify_out.txt"), "w", encoding="utf-8") as f:
    f.write(OUT.getvalue())
print("OK")
