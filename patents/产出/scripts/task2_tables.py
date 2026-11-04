# -*- coding: utf-8 -*-
"""Task 2: Table-Aware chunking via pdfplumber over all non-scanned patent PDFs.
- Non-scanned = extract_manifest rows with chars>=200 and no read error (the 299 text-layer PDFs).
- Each valid table (>=2 rows, >=2 cols, >=4 non-empty cells) -> one chunk:
    chunk_type="table", patent_id, page_number, table_content(Markdown),
    context_text(+-200 chars of page text), + bibliographic metadata.
- Output: patents/产出/RAG知识库/chunks_with_tables.jsonl  (original 7941 chunks + table chunks)
- Resumable: checkpoint patents/产出/scripts/task2_progress.json ; wall-clock budget guarded.
"""
import os, sys, io, csv, json, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pdfplumber

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
KB = os.path.join(BASE, "产出", "RAG知识库", "chunks.jsonl")
KB_OUT = os.path.join(BASE, "产出", "RAG知识库", "chunks_with_tables.jsonl")
META = os.path.join(BASE, "产出", "RAG知识库", "metadata_index.csv")
MANI = os.path.join(BASE, "extract_manifest.csv")
PROG = os.path.join(BASE, "产出", "scripts", "task2_progress.json")
BUDGET_S = int(os.environ.get("TASK2_BUDGET_S", "2700"))  # 45 min wall clock
PAGE_CAP = 120

meta = {}
with open(META, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        meta[r["pub"]] = r

todo = []
with open(MANI, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if int(r["chars"] or 0) >= 200 and "read:" not in (r["error"] or ""):
            todo.append(r["file"][:-4])
todo.sort()

done = {}
if os.path.exists(PROG):
    done = json.load(open(PROG, encoding="utf-8"))
pending = [p for p in todo if p not in done]
total_pages_target = sum(int(r["pages"]) for r in csv.DictReader(open(MANI, encoding="utf-8-sig"))
                         if r["file"][:-4] in set(pending))
print(f"[Task2] non-scanned PDFs={len(todo)} already_done={len(done)} pending={len(pending)} pages_to_scan~{total_pages_target}", flush=True)

table_chunks = []
def table_chunk(pub, page_no, tbl_idx, rows, ctx):
    m = meta.get(pub, {})
    clean = lambda s: (s or "").replace("|", "/").replace("\n", " ").strip()
    header = [clean(c) for c in rows[0]]
    body = [[clean(c) for c in r] for r in rows[1:]]
    ncol = max(1, len(header))
    md = ["| " + " | ".join(header + [""] * (ncol - len(header))) + " |",
          "|" + "---|" * ncol]
    for r in body[:60]:
        md.append("| " + " | ".join(r + [""] * (ncol - len(r))) + " |")
    return {
        "chunk_id": f"{pub}::table_p{page_no:03d}_{tbl_idx}",
        "chunk_type": "table",
        "patent_id": pub,
        "pub": pub,
        "page_number": page_no,
        "title": m.get("title", ""),
        "assignee": m.get("assignee", ""),
        "country": m.get("country", ""),
        "filing": m.get("filing", ""),
        "publication": m.get("publication", ""),
        "primary_theme": m.get("primary_theme", ""),
        "sha256_pdf": m.get("sha256_pdf", ""),
        "source_pdf": f"patents/pdf/{pub}.pdf",
        "table_content": "\n".join(md),
        "context_text": ctx,
        "extraction": "pdfplumber extract_tables",
    }

t0 = time.time()
n_tables = 0
stopped = "completed"
for i, pub in enumerate(pending, 1):
    if time.time() - t0 > BUDGET_S:
        stopped = "budget_exceeded"
        print(f"[Task2] wall-clock budget {BUDGET_S}s reached, stopping gracefully.", flush=True)
        break
    path = os.path.join(BASE, "pdf", pub + ".pdf")
    try:
        with pdfplumber.open(path) as pdf:
            pages = pdf.pages[:PAGE_CAP]
            for pno, page in enumerate(pages, 1):
                try:
                    txt = page.extract_text() or ""
                except Exception:
                    txt = ""
                if len(txt) < 150:
                    continue
                try:
                    tables = page.extract_tables()
                except Exception:
                    tables = []
                for ti, rows in enumerate(tables or []):
                    if not rows or len(rows) < 2 or len(rows[0]) < 2:
                        continue
                    nonempty = sum(1 for r in rows for c in r if c and str(c).strip())
                    if nonempty < 4:
                        continue
                    ctx_a = txt[:200]
                    ctx_b = txt[-200:] if len(txt) > 400 else txt[200:]
                    table_chunks.append(table_chunk(pub, pno, ti, rows, (ctx_a + " …… " + ctx_b)[:420]))
                    n_tables += 1
        done[pub] = 1
    except Exception as e:
        done[pub] = f"error:{str(e)[:80]}"
    if i % 10 == 0 or i == len(pending):
        with open(PROG, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False)
        print(f"[Task2] {i}/{len(pending)} PDFs | tables={n_tables} | {time.time()-t0:.0f}s | last={pub}", flush=True)

with open(PROG, "w", encoding="utf-8") as f:
    json.dump(done, f, ensure_ascii=False)

# merge: original chunks + table chunks
n_orig = 0
with open(KB_OUT, "w", encoding="utf-8") as out, open(KB, encoding="utf-8") as src:
    for line in src:
        out.write(line if line.endswith("\n") else line + "\n")
        n_orig += 1
    for c in table_chunks:
        out.write(json.dumps(c, ensure_ascii=False) + "\n")
print(f"[Task2] DONE status={stopped} | table_chunks={len(table_chunks)} | wrote {n_orig}+{len(table_chunks)}={n_orig+len(table_chunks)} lines -> chunks_with_tables.jsonl | elapsed={time.time()-t0:.0f}s", flush=True)
errs = {k: v for k, v in done.items() if isinstance(v, str)}
if errs:
    print(f"[Task2] errors={len(errs)}:", list(errs.items())[:5], flush=True)
