# -*- coding: utf-8 -*-
"""Task 3: GraphRAG 基础图谱 (nodes/edges CSV).
Nodes: Patent(227) / Applicant / Solute(canonical) / IPC(subclass)
Edges: HAS_APPLICANT, HAS_IPC, CONTAINS_SOLUTE, CITES + CITED_BY (full-text cross-reference),
       SAME_FAMILY (normalized-title proxy, evidence-tagged)
Inputs: metadata_index.csv, grounding_records.json, formulation_database.csv (Task 1), patents/txt/*.txt
Output: patents/产出/graph_nodes.csv, patents/产出/graph_edges.csv
"""
import os, sys, io, csv, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from collections import defaultdict

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
OUTD = os.path.join(BASE, "RAG", "产出")
META = os.path.join(BASE, "RAG", "产出", "RAG知识库", "metadata_index.csv")
FORM = os.path.join(BASE, "RAG", "产出", "formulation_database.csv")
GR = os.path.join(BASE, "analysis", "grounding_records.json")
TXT = os.path.join(BASE, "txt")

SOLUTE_CANON = {
    "四氢嘧啶/tetrahydropyrimidine(中文语境)": "Ectoine",
    "ectoine": "Ectoine", "hydroxyectoine": "Hydroxyectoine",
    "glycine betaine": "Glycine Betaine", "betaine(unspecified)": "Betaine",
    "trehalose": "Trehalose", "proline": "Proline", "sorbitol": "Sorbitol",
    "mannitol": "Mannitol", "xylitol": "Xylitol", "carnitine": "Carnitine",
    "glucosylglycerol": "Glucosylglycerol", "mannosylglycerol": "Mannosylglycerate/MG",
    "di-myo-inositol-phosphate": "Di-myo-inositol-phosphate", "dimsqrt": "Diglycerol-phosphate",
    "firoin": "Firoin", "四氢嘧啶": "Ectoine",
}
EXTRA_SOLUTES = {"Glycerol", "Urea", "Glutamine", "Citrulline", "cDPG", "Mannosylglyceramide/Firoin-A"}

nodes = {}   # node_id -> {node_type, name, metadata_json}
edges = []
eset = set()

def add_node(nid, ntype, name, meta=None):
    if nid not in nodes:
        nodes[nid] = {"node_id": nid, "node_type": ntype, "name": name,
                      "metadata_json": json.dumps(meta or {}, ensure_ascii=False)}
    elif meta:
        cur = json.loads(nodes[nid]["metadata_json"])
        cur.update(meta)
        nodes[nid]["metadata_json"] = json.dumps(cur, ensure_ascii=False)

def add_edge(s, t, rel, evidence=""):
    key = (s, t, rel)
    if key in eset or s == t:
        return
    eset.add(key)
    edges.append({"source_id": s, "target_id": t, "relation_type": rel, "evidence": evidence})

def solute_canon(x):
    return SOLUTE_CANON.get(x, x)

# ---------- load patents ----------
pats = list(csv.DictReader(open(META, encoding="utf-8-sig")))
grecs = {r["pub"]: r for r in json.load(open(GR, encoding="utf-8"))}

# ---------- Task1 solute hits per patent ----------
t1_solute = defaultdict(set)
if os.path.exists(FORM):
    for r in csv.DictReader(open(FORM, encoding="utf-8-sig")):
        st = (r.get("solute_type") or "").strip()
        if st and st not in ("Multiple/Mixed",) and st not in ("null",):
            t1_solute[r["patent_id"]].add(st)

# ---------- patent nodes + HAS_APPLICANT + HAS_IPC + CONTAINS_SOLUTE ----------
PUBSET = {p["pub"] for p in pats}
for p in pats:
    pub = p["pub"]
    add_node(f"PATENT::{pub}", "Patent", pub, {
        "title": p.get("title", ""), "assignee": p.get("assignee", ""),
        "country": p.get("country", ""), "filing": p.get("filing", ""),
        "publication": p.get("publication", ""), "primary_theme": p.get("primary_theme", ""),
        "ipc_all": p.get("ipc_cpc", ""), "sha256_pdf": p.get("sha256_pdf", "")[:32]})
    ap = (p.get("assignee") or "").strip()
    if ap and ap != "（元数据缺失）":
        aid = "APPLICANT::" + re.sub(r"\s+", "", ap.lower())[:60]
        add_node(aid, "Applicant", ap)
        add_edge(f"PATENT::{pub}", aid, "HAS_APPLICANT")
    for code in [c for c in (p.get("ipc_cpc") or "").split(";") if c]:
        sub = code.split(" ")[0][:4]
        add_node(f"IPC::{sub}", "IPC", sub, {"full_codes": []})
        cur = json.loads(nodes[f"IPC::{sub}"]["metadata_json"])
        if code not in cur["full_codes"]:
            cur["full_codes"].append(code)
            nodes[f"IPC::{sub}"]["metadata_json"] = json.dumps(cur, ensure_ascii=False)
        add_edge(f"PATENT::{pub}", f"IPC::{sub}", "HAS_IPC")
    sols = set()
    for s in [x for x in (grecs.get(pub, {}).get("solutes") or "").split(";") if x]:
        sols.add(solute_canon(s))
    for s in t1_solute.get(pub, ()):  # Task1 names already canonical-ish
        sols.add(s)
    for s in sols:
        add_node(f"SOLUTE::{s}", "Solute", s)
        add_edge(f"PATENT::{pub}", f"SOLUTE::{s}", "CONTAINS_SOLUTE", "metadata+task1_textmining")

# ---------- CITES / CITED_BY via full-text cross references ----------
PATNUM = re.compile(r"\b((?:CN|US|EP|WO|JP|KR|DE|ES|AU|CA|HK|TW|NZ|BR|AT|RO|RU)[0-9]{6,12}[A-Z][0-9]?)\b")
n_cite_hits = 0
for pub in sorted(PUBSET):
    fp = os.path.join(TXT, pub + ".txt")
    if not os.path.exists(fp):
        continue
    txt = re.sub(r"\s+", "", open(fp, encoding="utf-8", errors="ignore").read().upper())
    refs = set(PATNUM.findall(txt))
    for r in refs:
        if r in PUBSET and r != pub:
            add_edge(f"PATENT::{pub}", f"PATENT::{r}", "CITES", "fulltext_reference")
            add_edge(f"PATENT::{r}", f"PATENT::{pub}", "CITED_BY", "fulltext_reference_inverse")
            n_cite_hits += 1

# ---------- SAME_FAMILY (normalized title proxy) ----------
fam = defaultdict(list)
for p in pats:
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", (p.get("title") or "").lower())
    if len(t) >= 20:
        fam[t].append(p["pub"])
n_fam_edges = 0
for t, members in fam.items():
    if len(members) < 2:
        continue
    for i in range(len(members) - 1):
        add_edge(f"PATENT::{members[i]}", f"PATENT::{members[i+1]}", "SAME_FAMILY",
                 "normalized_title_proxy")
        add_edge(f"PATENT::{members[i+1]}", f"PATENT::{members[i]}", "SAME_FAMILY",
                 "normalized_title_proxy")
        n_fam_edges += 1

with open(os.path.join(OUTD, "graph_nodes.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["node_id", "node_type", "name", "metadata_json"])
    w.writeheader()
    w.writerows(sorted(nodes.values(), key=lambda x: (x["node_type"], x["node_id"])))
with open(os.path.join(OUTD, "graph_edges.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["source_id", "target_id", "relation_type", "evidence"])
    w.writeheader()
    w.writerows(edges)

from collections import Counter
print(f"[Task3] nodes={len(nodes)} by_type={dict(Counter(n['node_type'] for n in nodes.values()))}")
print(f"[Task3] edges={len(edges)} by_type={dict(Counter(e['relation_type'] for e in edges))}")
print(f"[Task3] cite_links_in_corpus={n_cite_hits} family_groups={[len(v) for v in fam.values() if len(v)>1]}")
