# -*- coding: utf-8 -*-
import sys, io, os, csv, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import openpyxl

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"

print("========== compatible_solute_patents.xlsx ==========")
wb = openpyxl.load_workbook(os.path.join(BASE, "compatible_solute_patents.xlsx"), read_only=True, data_only=True)
for ws in wb.worksheets:
    print(f"--- sheet: {ws.title}  dims={ws.calculate_dimension()} ---")
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i > 8:
            print(f"... ({ws.max_row} rows total)")
            break
        print(" | ".join("" if c is None else str(c)[:60] for c in row))

for name in ["google_patents_compatible_solute_candidates.csv",
             "google_patents_compatible_solute_candidates.pre_full_query.csv",
             "patent_pdf_download_status.csv"]:
    p = os.path.join(BASE, name)
    print("\n" + "=" * 20, name, "=" * 20)
    if not os.path.exists(p):
        print("MISSING"); continue
    with open(p, encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    print("rows:", len(rows), "cols:", len(rows[0]) if rows else 0)
    print("header:", rows[0] if rows else "")
    for r in rows[1:4]:
        print("  ", " | ".join(c[:50] for c in r))

p = os.path.join(BASE, "google_patents_compatible_solute_candidates.json")
print("\n" + "=" * 20, "candidates.json", "=" * 20)
with open(p, encoding="utf-8") as f:
    data = json.load(f)
print(type(data), len(data))
if isinstance(data, list) and data:
    print(json.dumps(data[0], ensure_ascii=False, indent=1)[:800])
elif isinstance(data, dict):
    print(list(data.keys())[:20])
