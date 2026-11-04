# -*- coding: utf-8 -*-
"""验收：1)按harness逻辑解析 2)DOI溯源到oa_pdf_20260926 3)要点/文献切分健全"""
import pandas as pd, re, os, sys
sys.stdout.reconfigure(encoding='utf-8')

OUT = r"C:\Users\25416\Desktop\agent for pollution\高盐厌氧氨氧化AI智能体评测试题_20260927.csv"
SRC = r"C:\Users\25416\Desktop\agent for pollution\lit_workspace\literature\oa_pdf_20260926"

df = pd.read_csv(OUT, encoding='utf-8-sig')
print("rows:", len(df), "cols ok:", list(df.columns))

NUM_PREFIX = re.compile(r"^\s*(?:\d+[.、)]|[(（]\d+[)）])\s*")
def split_keypoints(raw):
    parts = re.split(r"[；;]", str(raw))
    cleaned = []
    for p in parts:
        p = NUM_PREFIX.sub("", p.strip())
        p = p.rstrip("….").strip()
        if p:
            cleaned.append(p)
    return cleaned

def _split_list(raw):
    return [s.strip() for s in re.split(r"[；;,，]", str(raw)) if s.strip()]

pdfs = set(f[:-4] for f in os.listdir(SRC) if f.endswith(".pdf"))
problems = []
kp_counts = []
for _, row in df.iterrows():
    qid = row["question_id"]
    kps = split_keypoints(row["ideal_keypoints（打分用）"])
    kp_counts.append((qid, len(kps)))
    if not 3 <= len(kps) <= 6:
        problems.append(f"{qid}: keypoint数={len(kps)}")
    refs = _split_list(row["参考文献"])
    for r in refs:
        m = re.match(r"(10\.\d{4,9}/\S+)", r)
        if not m:
            problems.append(f"{qid}: 文献无DOI前缀 -> {r[:50]}")
            continue
        doi = m.group(1).rstrip(".")
        fname = doi.replace("/", "_")
        if fname not in pdfs:
            problems.append(f"{qid}: DOI不在文献库 -> {doi}")
    if row["eval_mode"] != "rubric_6dims":
        problems.append(f"{qid}: eval_mode异常")
    for col in ["question", "ideal_detail（参考）", "categories"]:
        if not str(row[col]).strip():
            problems.append(f"{qid}: {col}为空")
    # 要点内部残留分隔符的检查：切分后的要点若过短说明被误切
    for k in kps:
        if len(k) < 8:
            problems.append(f"{qid}: 疑似误切要点 -> {k[:20]}")

print("\nkeypoint分布:", kp_counts)
print("\n难度分布:", df['难度'].value_counts().to_dict())
print("题型分布:", df['题型'].value_counts().to_dict())
print("主题分布:", df['主题'].value_counts().to_dict())
n_refs = sum(len(_split_list(r)) for r in df['参考文献'])
print("文献条目总数:", n_refs, " 涉及唯一DOI:", len({re.match(r'(10\.\d{4,9}/\S+)', s).group(1).rstrip('.') for r in df['参考文献'] for s in _split_list(r) if re.match(r'(10\.\d{4,9}/\S+)', s)}))
print("\n问题清单:" if problems else "\n验收通过：无问题")
for p in problems:
    print(" -", p)
