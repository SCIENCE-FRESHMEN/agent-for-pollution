# -*- coding: utf-8 -*-
"""Task 1: 参数化配方数据库抽取 (Formulation DB)
Primary path : OpenAI LLM (response_format=json_object), requires OPENAI_API_KEY.
Fallback path: deterministic rule extractor (regex + controlled vocabulary), used
when the key is absent or the API fails, so the deliverable is always produced.
Output: patents/产出/formulation_database.csv
"""
import os, sys, io, csv, json, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = r"C:\Users\25416\Desktop\agent for pollution\patents"
KB = os.path.join(BASE, "RAG", "产出", "RAG知识库", "chunks.jsonl")
OUT = os.path.join(BASE, "RAG", "产出", "formulation_database.csv")

HAS_KEY = bool(os.environ.get("OPENAI_API_KEY"))
LLM_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
LLM_BUDGET = int(os.environ.get("LLM_CHUNK_BUDGET", "900"))  # max chunks sent to LLM

SOLUTE_PATTERNS = [
    (r"hydroxy\s?ectoine|羟基四氢嘧啶|ヒドロキシエクトイン", "Hydroxyectoine"),
    (r"四氢嘧啶|依克多因|エクトイン|(?<![a-z])ectoin(e)?(?![a-z])", "Ectoine"),
    (r"glycine\s?betaine|甘氨酸甜菜碱|グリシンベタイン", "Glycine Betaine"),
    (r"甜菜碱|betaine|トリメチルグリシン|trimethylglycine", "Betaine"),
    (r"海藻糖|trehalose|トレハロース", "Trehalose"),
    (r"脯氨酸|(?<![a-z])proline(?![a-z])|プロリン", "Proline"),
    (r"山梨(糖)?醇|(?<![a-z])sorbitol(?![a-z])", "Sorbitol"),
    (r"甘露醇|(?<![a-z])mannitol(?![a-z])", "Mannitol"),
    (r"木糖醇|(?<![a-z])xylitol(?![a-z])", "Xylitol"),
    (r"肉碱|(?<![a-z])carnitine(?![a-z])", "Carnitine"),
    (r"葡萄糖基甘油|glucosyl\s?glycer", "Glucosylglycerol"),
    (r"甘露糖基甘油|mannosyl\s?glycer", "Mannosylglycerate/MG"),
    (r"(?<![a-z])firoin(-?a)?(?![a-z])", "Firoin"),
    (r"di-?myo-?inositol", "Di-myo-inositol-phosphate"),
    (r"diglycerol\s?phosphate|二甘油磷酸", "Diglycerol-phosphate"),
    (r"cyclic(al)?\s?2,?[34][- ]?diphospho\s?glycerate|(?<![a-z])c?dpg(?![a-z])|环状\s?2,?[34]-?二磷酸甘油酸", "cDPG"),
    (r"甘油|(?<![a-z])glycerol(?![a-z])|グリセロール", "Glycerol"),
    (r"尿素|(?<![a-z])urea(?![a-z])", "Urea"),
    (r"谷氨酰胺|(?<![a-z])glutamine(?![a-z])", "Glutamine"),
    (r"瓜氨酸|(?<![a-z])citrulline(?![a-z])", "Citrulline"),
]
CONC_RANGE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-–~至]\s*(\d+(?:\.\d+)?)\s*(mM|mmol/L|mol/L|g/L|mg/L|μg/mL|µg/mL|mg/mL|wt\s?%|％|%|μM|µM|mg/g|MPa|g/mL|v/v|w/v)")
CONC_SINGLE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mM|mmol/L|mol/L|g/L|mg/L|μg/mL|µg/mL|mg/mL|wt\s?%|％|%|μM|µM|mg/g|MPa|g/mL)")
RATIO = re.compile(r"(质量比|质量百分比|摩尔比|weight ratio|molar ratio|按质量比)[^。;；\n]{2,60}")
EFFECT = re.compile(
    r"((?:脱氮|去除|降解|回收|存活|抑制|保护|稳定)(?:效率|率|能)?|efficiency|removal(?: rate)?|survival(?: rate)?|yield|accumulation|积累量|存活率|收率|产率)[^。;；\n]{0,50}?\s(\d+(?:\.\d+)?)\s*(%|mg/g|g/L|mg/L|倍|℃)", re.I)
EFFECT_NUM_FIRST = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%|mg/g|g/L|mg/L|倍)[^。;；\n]{0,30}?(脱氮|去除|降解|回收|存活|积累|效率|率|收率|产率|efficiency|removal|survival|accumulation)", re.I)
SCEN_KW = [
    ("高盐废水生物处理", r"废水|污水|wastewater|sewage|denitrif|脱氮|anammox|硝化|sludge|污泥|反应器|bioreactor|水处理"),
    ("盐碱地/土壤改良", r"盐碱|土壤|soil|saline[- ]alkali|土壤改良"),
    ("眼科制剂", r"ophthalmic|dry[- ]eye|干眼|眼科|泪|tear film|contact lens|隐形眼镜"),
    ("化妆品/皮肤护理", r"cosmetic|skin|皮肤|化妆|护肤|dermatolog|anti[- ]?aging|保湿"),
    ("生物分子/细胞保存", r"冻干|lyophil|freeze[- ]?dry|保存|preserv|storage|cryoprotect|红细胞|血小板|RNA|platelet|erythrocyte"),
    ("医药制剂", r"pharmaceut|药物|vaccine|疫苗|治疗|therap|医"),
    ("溶质生产制造", r"发酵|ferment|producing|生产|提取|纯化|结晶|extraction|purif|crystalliz|菌株|recombinant|工程菌"),
    ("农业/植物抗逆", r"plant|植物|seed|种子|crop|作物|drought|干旱|耐盐|盐渍"),
    ("食品/饲料", r"food|feed|食品|饲料|保鲜|soy sauce|酱油"),
]

def find_solutes(t):
    low = t.lower()
    out = []
    for pat, name in SOLUTE_PATTERNS:
        if re.search(pat, low):
            out.append(name)
    return out

def find_scenario(t, fallback):
    for name, pat in SCEN_KW:
        if re.search(pat, t, re.I):
            return name
    return fallback

def extract_rules(chunk):
    raw = chunk["text"]
    # normalize digit-spacing artifacts from pypdf CJK extraction: "0 . 5%" -> "0.5%", "1 00%" -> "100%"
    t = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", raw)
    t = re.sub(r"(\d)\s+(\d{2}%|mg|g|mM|MPa|μM|µM)", r"\1\2", t)
    low = t.lower()
    # noise anchors: matches whose context is clearly not a formulation fact
    NOISE = ("琼脂糖凝胶", "切胶回收", "电泳", "不良反应发生率", "发生率", " gel ", "agarose")
    recs = []
    sols = find_solutes(t)
    scen = find_scenario(t, chunk.get("primary_theme", ""))
    concs = []
    for m in CONC_RANGE.finditer(t):
        concs.append((m.start(), m.group(0).strip()))
    for m in CONC_SINGLE.finditer(t):
        s = m.start()
        ctx = t[max(0, s - 60):s + 60].lower()
        if any(k in ctx for k in NOISE):
            continue
        concs.append((s, m.group(0).strip()))
    if RATIO.search(t):
        concs.append((RATIO.search(t).start(), RATIO.search(t).group(0)[:70]))
    effects = []
    for m in EFFECT.finditer(t):
        if any(k in m.group(0).lower() for k in NOISE):
            continue
        effects.append((m.start(), m.group(0).strip()[:80]))
    for m in EFFECT_NUM_FIRST.finditer(t):
        if any(k in m.group(0).lower() for k in NOISE):
            continue
        effects.append((m.start(), m.group(0).strip()[:80]))
    concs = concs[:6]
    effects = effects[:4]
    if not sols:
        return recs
    pairs = []
    if concs and effects:
        for c in concs[:3]:
            ce = min(effects, key=lambda e: abs(e[0] - c[0])) if effects else None
            pairs.append((c, ce))
    elif concs:
        for c in concs[:3]:
            pairs.append((c, None))
    elif effects:
        for e in effects[:2]:
            pairs.append((None, e))
    else:
        pairs.append((None, None))
    sol_near = lambda pos: (min(sols, key=lambda s: low.find(s.lower()) if low.find(s.lower()) >= 0 else 10**9)
                            if not pos else None)
    for (c, e) in pairs:
        pos = (c or e or (0, ""))[0]
        near = None
        if pos:
            best, bd = None, 10**9
            for s in sols:
                for mm in re.finditer(re.escape(s.lower()), low):
                    d = abs(mm.start() - pos)
                    if d < bd:
                        bd, best = d, s
            near = best if bd <= 400 else None
        recs.append({
            "solute_type": near or (sols[0] if len(sols) == 1 else "Multiple/Mixed"),
            "application_scenario": scen,
            "concentration_ratio": c[1] if c else None,
            "quantitative_effect": e[1] if e else None,
            "evidence": t[max(0, pos - 80):pos + 120].replace("\n", " ") if pos else t[:160].replace("\n", " "),
        })
    return recs

LLM_PROMPT = (
    "你从专利切片中抽取相容性溶质配方四元组。只使用切片原文信息，不得推断。"
    "返回JSON对象：{\"records\":[{\"solute_type\":str|null,\"application_scenario\":str|null,"
    "\"concentration_ratio\":str|null,\"quantitative_effect\":str|null,\"evidence\":str(原文片段<=120字)}]}。"
    "切片中无配方信息时返回 {\"records\":[]}。")

def extract_llm(chunk):
    from openai import OpenAI
    global _client
    try:
        _client
    except NameError:
        _client = OpenAI()
    resp = _client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[{"role": "system", "content": LLM_PROMPT},
                  {"role": "user", "content": chunk["text"][:3500]}],
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    out = []
    for r in data.get("records", [])[:4]:
        out.append({
            "solute_type": r.get("solute_type"),
            "application_scenario": r.get("application_scenario"),
            "concentration_ratio": r.get("concentration_ratio"),
            "quantitative_effect": r.get("quantitative_effect"),
            "evidence": (r.get("evidence") or "")[:160],
        })
    return out

def main():
    t0 = time.time()
    rows, seen = [], set()
    n_read = n_filtered = n_llm = 0
    llm_failed = 0
    use_llm = HAS_KEY
    with open(KB, encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            n_read += 1
            ic = c.get("info_class", "")
            if ("实施例" not in ic) and ("权利要求" not in ic):
                continue
            n_filtered += 1
            recs = []
            if use_llm and n_llm < LLM_BUDGET:
                try:
                    recs = extract_llm(c)
                    n_llm += 1
                except Exception as e:
                    llm_failed += 1
                    if llm_failed >= 3:
                        use_llm = False
                    recs = extract_rules(c)
            else:
                recs = extract_rules(c)
            for r in recs:
                if not any([r.get("concentration_ratio"), r.get("quantitative_effect"),
                            r.get("solute_type")]):
                    continue
                key = (c["pub"], r.get("solute_type"), r.get("concentration_ratio"),
                       r.get("quantitative_effect"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "record_id": f"FD-{len(rows)+1:05d}",
                    "patent_id": c["pub"],
                    "chunk_id": c["chunk_id"],
                    "section": c.get("section", ""),
                    "info_class": ic,
                    "solute_type": r.get("solute_type") or "",
                    "application_scenario": r.get("application_scenario") or "",
                    "concentration_ratio": r.get("concentration_ratio") or "",
                    "quantitative_effect": r.get("quantitative_effect") or "",
                    "evidence_snippet": (r.get("evidence") or "")[:200],
                    "extraction_method": "llm" if (HAS_KEY and n_llm > 0 and not llm_failed) else "rule_based_v1",
                    "source_pdf": c.get("source_pdf", ""),
                })
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["record_id", "patent_id", "chunk_id", "section", "info_class",
                            "solute_type", "application_scenario", "concentration_ratio",
                            "quantitative_effect", "evidence_snippet", "extraction_method", "source_pdf"])
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"[Task1] chunks_read={n_read} filtered(实施例/权利要求)={n_filtered} llm_calls={n_llm} llm_fail={llm_failed}")
    print(f"[Task1] formulation records={len(rows)} distinct patents={len({r['patent_id'] for r in rows})} elapsed={time.time()-t0:.0f}s")
    print(f"[Task1] solute_type top:", Counter(r['solute_type'] for r in rows).most_common(8))
    print(f"[Task1] scenario top:", Counter(r['application_scenario'] for r in rows).most_common(6))

if __name__ == "__main__":
    main()
