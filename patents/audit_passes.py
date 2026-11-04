# -*- coding: utf-8 -*-
import os, sys, io, json, re, unicodedata, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
AN = os.path.join(BASE, "analysis")
rows = list(csv.DictReader(open(os.path.join(AN, "compliance.csv"), encoding="utf-8-sig")))
print("--- EU-criterion passes ---")
for r in rows:
    if "欧语" in r["criterion"]:
        print(f"  {r['pub']} | {r['criterion']} | {r['title'][:60]}")
print("--- remaining excluded (60) by criterion ---")
from collections import Counter
for k, n in Counter(r["criterion"] for r in rows if r["verdict"] == "剔除").most_common():
    print(f"  {n:3d}  {k}")
print("--- excluded single-word list ---")
for r in rows:
    if r["verdict"] == "剔除" and "仅单词" in r["criterion"]:
        print(f"  {r['pub']} | {r['title'][:70]}")

# EP2303847B1 context
p = os.path.join(BASE, "txt", "EP2303847B1.txt")
t = open(p, encoding="utf-8", errors="ignore").read().lower()
t = re.sub(r"\s+", " ", t)
print("\n--- EP2303847B1 'kompatibl/solut' contexts ---")
for m in list(re.finditer(r"kompatibl\w*\s+solut\w*|solut\w*\s+kompatibl\w*", t))[:5]:
    print("  ...", t[max(0, m.start() - 120):m.start() + 120].replace("\n", " "), "...")

# JP5773509B2 claims language
p = os.path.join(BASE, "txt", "JP5773509B2.txt")
raw = open(p, encoding="utf-8", errors="ignore").read()
print("\n--- JP5773509B2 claim-ish lines with 適合性/相溶性 ---")
for m in list(re.finditer(r"適合性|相溶性", raw))[:8]:
    print("  ...", raw[max(0, m.start() - 80):m.start() + 100].replace("\n", " "), "...")
