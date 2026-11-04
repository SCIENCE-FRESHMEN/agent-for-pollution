# -*- coding: utf-8 -*-
import csv, io, json, os
from collections import Counter

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
OUT = io.StringIO()

with open(os.path.join(BASE, "产出", "formulation_database.csv"), "rb") as f:
    rows = list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
OUT.write("formulation total: %d\n" % len(rows))
OUT.write("extraction_method: %r\n" % Counter(r["extraction_method"] for r in rows).most_common())
OUT.write("info_class: %r\n" % Counter(r["info_class"] for r in rows).most_common(6))
OUT.write("section: %r\n" % Counter(r["section"] for r in rows).most_common(8))
pats = set(r["patent_id"] for r in rows)
OUT.write("distinct patents: %d\n" % len(pats))

cls = Counter()
n = 0
with open(os.path.join(BASE, "产出", "RAG知识库", "chunks_with_tables.jsonl"), "rb") as f:
    for line in f:
        n += 1
        d = json.loads(line.decode("utf-8"))
        cls[d.get("info_class", "?")] += 1
OUT.write("\nchunks total: %d\ninfo_class: %r\n" % (n, cls.most_common(8)))

# 图谱关系类型
with open(os.path.join(BASE, "产出", "graph_edges.csv"), "rb") as f:
    er = list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
OUT.write("\nedge relations: %r\n" % Counter(r["relation_type"] for r in er).most_common())
with open(os.path.join(BASE, "产出", "graph_nodes.csv"), "rb") as f:
    nr = list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
OUT.write("node types: %r\n" % Counter(r["node_type"] for r in nr).most_common())

with open(os.path.join(BASE, "analysis", "_verify2_out.txt"), "w", encoding="utf-8") as f:
    f.write(OUT.getvalue())
print("OK")
