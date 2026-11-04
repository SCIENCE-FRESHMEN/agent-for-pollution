# -*- coding: utf-8 -*-
import csv, io, os
from collections import Counter

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
with open(os.path.join(BASE, "产出", "RAG知识库", "metadata_index.csv"), "rb") as f:
    rows = list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
OUT = io.StringIO()
OUT.write("country: %r\n" % Counter(r["country"] for r in rows).most_common(10))
yr = Counter((r["priority"] or r["filing"] or "")[:4] for r in rows)
OUT.write("year(priority): %r\n" % sorted(yr.items()))
OUT.write("assignee top12: %r\n" % Counter(r["assignee"] for r in rows).most_common(12))
ipc = Counter()
for r in rows:
    try:
        arr = eval(r["ipc_cpc"]) if r["ipc_cpc"] else []
        for x in arr[:1]:
            ipc[x.split()[0][:4]] += 1
    except Exception:
        pass
OUT.write("primary IPC top: %r\n" % ipc.most_common(8))
with open(os.path.join(BASE, "analysis", "_verify3_out.txt"), "w", encoding="utf-8") as f:
    f.write(OUT.getvalue())
print("OK")
