"""数据集加载与校验:把题库 CSV 解析成结构化的 Question 对象。

对应 BixBench 的 capsule 概念:每道题 = 题面 + 打分要点 + 参考答案 + 元数据。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# CSV 列名 -> 内部字段(列名含中文与全角括号,统一映射)
COLUMN_MAP = {
    "question_id": "question_id",
    "标签": "tag",
    "主题": "topic",
    "难度": "difficulty",
    "题型": "qtype",
    "question": "question",
    "ideal_keypoints（打分用）": "keypoints_raw",
    "ideal_detail（参考）": "ideal_detail",
    "eval_mode": "eval_mode",
    "categories": "categories_raw",
    "参考文献": "references_raw",
    "细分": "domain",
}

# 打分要点中形如 "1." "2、" "（3）" 的编号前缀
_NUM_PREFIX = re.compile(r"^\s*(?:（?\d+）?[\.\、．]\s*|\(\d+\)\s*)+")

# 判定拒答的表达(用于启发式评分与结果统计)
REFUSAL_PATTERNS = re.compile(
    r"无法回答|信息不足|无法确定|不能确定|无法判断|拒答|缺乏.{0,6}(?:信息|数据|依据)"
    r"|insufficient\s+information|cannot\s+answer",
    re.IGNORECASE,
)

# 题面中的结构化场景槽位(T1 因子设计:优势菌 × 盐度区间 × 基因组档案 × 反应器)
_ORGANISM_RE = re.compile(
    r"以\s*(Kuenenia|Brocadia|Jettenia|Scalindua|Anammoxoglobus)\s*为优势"
)
_HRT_RE = re.compile(r"HRT\s*(\d+)\s*h")
_SALT_RE = re.compile(r"盐度从\s*(\d+(?:\.\d+)?)%\s*提升到\s*(\d+(?:\.\d+)?)%")
_GENOME_RE = re.compile(r"附件\s*([A-Za-z]+-P\d+\.fna)")
_SCENARIO_RE = re.compile(r"某\s*([^,。]{2,24}?)（([^）]*)）")


def parse_scenario(text: str) -> dict:
    """从题面抽取因子变量;非 T1 题返回空值字段。"""
    org = _ORGANISM_RE.search(text)
    hrt = _HRT_RE.search(text)
    salt = _SALT_RE.search(text)
    genome = _GENOME_RE.search(text)
    scen = _SCENARIO_RE.search(text)
    return {
        "organism": org.group(1) if org else "",
        "hrt_h": int(hrt.group(1)) if hrt else None,
        "salt_from": float(salt.group(1)) if salt else None,
        "salt_to": float(salt.group(2)) if salt else None,
        "genome_file": genome.group(1) if genome else "",
        "scenario": f"{scen.group(1)}({scen.group(2)})" if scen else "",
    }


@dataclass
class Question:
    question_id: str
    tag: str
    topic: str
    difficulty: str
    qtype: str
    question: str
    keypoints: list[str]
    ideal_detail: str
    eval_mode: str
    categories: list[str]
    references: list[str]
    domain: str
    keypoints_raw: str = ""
    attachments: list[str] = field(default_factory=list)
    # 题面解析出的因子变量(T1 类题目有值,其余为空)
    organism: str = ""
    hrt_h: int | None = None
    salt_from: float | None = None
    salt_to: float | None = None
    genome_file: str = ""
    scenario: str = ""

    @property
    def num_keypoints(self) -> int:
        return len(self.keypoints)


def split_keypoints(raw: str) -> list[str]:
    """把 '1.xxx；2.yyy；3.zzz' 形式的要点串拆成独立要点列表。"""
    if not raw or pd.isna(raw):
        return []
    parts = re.split(r"[；;]", str(raw))
    cleaned = []
    for p in parts:
        p = _NUM_PREFIX.sub("", p.strip())
        p = p.rstrip("….").strip()
        if p:
            cleaned.append(p)
    return cleaned


def _split_list(raw: str) -> list[str]:
    if not raw or pd.isna(raw):
        return []
    return [s.strip() for s in re.split(r"[；;,，]", str(raw)) if s.strip()]


def _text_or_empty(value, default: str = "") -> str:
    """Normalize CSV scalar cells without turning missing values into ``nan``."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else default


def load_questions(csv_path: str | Path) -> list[Question]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"题库文件不存在: {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8-sig").rename(columns=COLUMN_MAP)

    missing = [c for c in COLUMN_MAP.values() if c not in df.columns]
    if missing:
        raise ValueError(f"题库缺少列: {missing}。实际列: {list(df.columns)}")

    df = df.dropna(subset=["question_id", "question"]).reset_index(drop=True)

    questions: list[Question] = []
    seen_ids: set[str] = set()
    for _, row in df.iterrows():
        qid = str(row["question_id"]).strip()
        if qid in seen_ids:
            raise ValueError(f"question_id 重复: {qid}")
        seen_ids.add(qid)

        keypoints_raw = _text_or_empty(row.get("keypoints_raw", ""))
        ideal_detail = _text_or_empty(row.get("ideal_detail", ""))
        keypoints = split_keypoints(keypoints_raw)
        if not keypoints:
            # 没有独立要点列时,退化使用参考答案整段作为单要点
            keypoints = [ideal_detail] if ideal_detail else []

        questions.append(
            Question(
                question_id=qid,
                tag=_text_or_empty(row.get("tag", "")),
                topic=_text_or_empty(row.get("topic", "")),
                difficulty=_text_or_empty(row.get("difficulty", "")),
                qtype=_text_or_empty(row.get("qtype", "")),
                question=str(row["question"]).strip(),
                keypoints=keypoints,
                ideal_detail=ideal_detail,
                eval_mode=_text_or_empty(row.get("eval_mode", ""), "rubric_6dims"),
                categories=_split_list(_text_or_empty(row.get("categories_raw", ""))),
                references=_split_list(_text_or_empty(row.get("references_raw", ""))),
                domain=_text_or_empty(row.get("domain", "")),
                keypoints_raw=keypoints_raw,
                **parse_scenario(str(row["question"])),
            )
        )

    if not questions:
        raise ValueError("题库为空")
    return questions


def filter_questions(questions: list[Question], **filters) -> list[Question]:
    """按元数据过滤,如 difficulty=['复杂'], qtype=['T1 总体耐盐化措施']。空列表/None 表示不过滤。"""
    out = questions
    for field_name, allowed in filters.items():
        if not allowed:
            continue
        allowed = {str(a) for a in allowed}
        out = [q for q in out if getattr(q, field_name) in allowed]
    return out


def dataset_stats(questions: list[Question]) -> dict:
    """题库概览统计,用于报告首页(仿 BixBench 的 dataset description)。"""

    def count(field_name: str, empty_label: str = "(空)") -> dict[str, int]:
        counts: dict[str, int] = {}
        for q in questions:
            key = getattr(q, field_name) or empty_label
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    from collections import Counter

    cat_freq = Counter(t for q in questions for t in q.categories)
    regimes = Counter(
        f"{q.salt_from:g}%→{q.salt_to:g}%" if q.salt_from is not None else "(非T1)"
        for q in questions
    )
    return {
        "n_questions": len(questions),
        "n_keypoints": sum(q.num_keypoints for q in questions),
        "avg_keypoints_per_question": round(
            sum(q.num_keypoints for q in questions) / len(questions), 2
        ),
        "by_tag": count("tag"),
        "by_topic": count("topic"),
        "by_difficulty": count("difficulty"),
        "by_qtype": count("qtype"),
        "eval_modes": count("eval_mode"),
        # 因子设计轴(T1 类题目)
        "by_organism": count("organism", "(非T1)"),
        "by_salt_regime": dict(sorted(regimes.items(), key=lambda kv: -kv[1])),
        "by_genome_file": count("genome_file", "(非T1)"),
        "categories_freq": dict(sorted(cat_freq.items(), key=lambda kv: -kv[1])),
    }
