"""指标汇总:复跑聚合、accuracy/precision/拒答率、按元数据分层。

对应 BixBench 的 majority voting + accuracy/precision 体系:
- pass_rate      —— 某题 N 次复跑中达标的比例(逐次 accuracy)
- stable_pass    —— 多数复跑达标才计通过(majority-vote 的开卷类比)
- mean_score     —— 综合分均值(连续量,比二值更细)
- precision      —— 非拒答作答中的平均得分/达标率
"""

from __future__ import annotations

from math import comb
from typing import Any

import pandas as pd

from .dataset import Question

BREAKDOWN_FIELDS = ["tag", "topic", "difficulty", "qtype", "domain",
                    "organism", "salt_to", "genome_file"]


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1.0 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denom
    return (round(max(0.0, center - half), 4), round(min(1.0, center + half), 4))


def _majority_accuracy(p: float, m: int) -> float:
    """已知单次通过率 p,m 次抽样下多数通过的精确概率(二项式)。"""
    q = 1.0 - p
    return sum(comb(m, j) * p**j * q ** (m - j) for j in range(m // 2 + 1, m + 1))


def _accuracy_vs_votes(qlv: pd.DataFrame) -> dict[int, float]:
    """投票数-准确率曲线(对应 BixBench 图 5):m=1..最大复跑数。"""
    if qlv.empty:
        return {}
    max_m = int(qlv["n_runs"].max())
    return {
        m: round(float(qlv["pass_rate"].map(lambda p: _majority_accuracy(p, m)).mean()), 4)
        for m in range(1, max_m + 1)
    }


def _as_bool(s: pd.Series) -> pd.Series:
    """CSV 读回的 True/False 字符串安全转布尔(直接 astype(bool) 会把 'False' 也变 True)。"""
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "1.0", "yes"])


def _as_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _question_level(grades: pd.DataFrame, pass_threshold: float) -> pd.DataFrame:
    grades = grades.copy()
    grades["refused"] = _as_bool(grades["refused"])
    grades["composite_score"] = _as_num(grades["composite_score"])
    grades["keypoint_coverage"] = _as_num(grades["keypoint_coverage"])
    grades["dim_norm"] = _as_num(grades["dim_norm"])
    grades["passed"] = (~grades["refused"]) & (grades["composite_score"] >= pass_threshold)

    qlv = grades.groupby("question_id", as_index=False).agg(
        n_runs=("passed", "size"),
        n_passed=("passed", "sum"),
        mean_score=("composite_score", "mean"),
        pass_rate=("passed", "mean"),
        refusal_rate=("refused", "mean"),
        keypoint_coverage=("keypoint_coverage", "mean"),
        dim_norm=("dim_norm", "mean"),
        n_answered=("refused", lambda s: int((~s).sum())),
    )
    # A majority requires strictly more than half of the runs; a 1/2 tie is
    # intentionally not a stable pass.
    qlv["stable_pass"] = qlv["n_passed"] > (qlv["n_runs"] / 2)
    num_cols = ["mean_score", "pass_rate", "refusal_rate", "keypoint_coverage", "dim_norm"]
    qlv[num_cols] = qlv[num_cols].round(4)
    return qlv


def compute_metrics(
    questions: list[Question],
    grades: pd.DataFrame,
    pass_threshold: float = 0.6,
) -> dict[str, Any]:
    if grades.empty:
        return {"error": "grades 为空"}

    qlv = _question_level(grades, pass_threshold)
    qmap = {q.question_id: q for q in questions}
    evaluated_ids = set(qlv["question_id"].astype(str))
    expected_ids = set(qmap)
    unknown_ids = evaluated_ids - expected_ids
    missing_ids = expected_ids - evaluated_ids
    meta = pd.DataFrame([
        {"question_id": q.question_id, "tag": q.tag, "topic": q.topic,
         "difficulty": q.difficulty, "qtype": q.qtype, "domain": q.domain or "(空)",
         "organism": q.organism or "(非T1)",
         "salt_to": f"{q.salt_to:g}%" if q.salt_to is not None else "(非T1)",
         "genome_file": q.genome_file or "(非T1)"}
        for q in questions
    ])
    qlv = qlv.merge(meta, on="question_id", how="inner")

    def _slice(sub: pd.DataFrame, key: str, value: str) -> dict:
        return {
            key: value, "n": int(len(sub)),
            "mean_score": round(float(sub["mean_score"].mean()), 4) if len(sub) else 0.0,
            "accuracy": round(float(sub["pass_rate"].mean()), 4) if len(sub) else 0.0,
            "stable_accuracy": round(float(sub["stable_pass"].mean()), 4) if len(sub) else 0.0,
            "refusal_rate": round(float(sub["refusal_rate"].mean()), 4) if len(sub) else 0.0,
        }

    # categories 是多标签字段:按每个标签聚合(一道题可进多个组)
    cat_rows = []
    for tag in sorted({t for q in questions for t in q.categories}):
        qids = {q.question_id for q in questions if tag in q.categories}
        sub = qlv[qlv["question_id"].isin(qids)]
        if not sub.empty:
            cat_rows.append(_slice(sub, "category", tag))
    metrics_cats = cat_rows

    grades = grades.copy()
    grades["refused"] = _as_bool(grades["refused"])
    grades["composite_score"] = _as_num(grades["composite_score"])
    answered = grades[~grades["refused"]]
    overall = {
        "n_questions": int(qlv.shape[0]),
        "n_questions_expected": len(expected_ids),
        "n_questions_evaluated": int(qlv.shape[0]),
        "n_questions_missing": len(missing_ids),
        "n_unknown_question_ids": len(unknown_ids),
        "n_runs": int(len(grades)),
        "pass_threshold": pass_threshold,
        "mean_score": round(float(qlv["mean_score"].mean()), 4),
        "accuracy": round(float(qlv["pass_rate"].mean()), 4),          # 逐次达标率的均值
        "stable_accuracy": round(float(qlv["stable_pass"].mean()), 4),  # 多数投票口径
        "refusal_rate": round(float(qlv["refusal_rate"].mean()), 4),
        "precision_on_answered": round(float(answered["composite_score"].mean()), 4)
        if not answered.empty else 0.0,
        "keypoint_coverage": round(float(qlv["keypoint_coverage"].mean()), 4),
        "dim_norm": round(float(qlv["dim_norm"].mean()), 4),
    }
    # Wilson interval is calculated over run-level outcomes, preserving the
    # uncertainty that is hidden by the per-question mean accuracy.
    passed = (~grades["refused"]) & (grades["composite_score"] >= pass_threshold)
    lo, hi = wilson_interval(int(passed.sum()), int(len(passed)))
    overall["accuracy_wilson_95"] = {"low": lo, "high": hi}
    q_passed = qlv["stable_pass"].astype(bool)
    qlo, qhi = wilson_interval(int(q_passed.sum()), int(len(q_passed)))
    overall["stable_accuracy_wilson_95"] = {"low": qlo, "high": qhi}

    dims = [c for c in grades.columns if c.startswith("dim_") and c not in ("dim_norm", "dim_total")]
    overall["per_dim"] = {
        c[4:]: round(float(_as_num(grades[c]).mean() / 2), 4) for c in dims
    } if dims else {}

    # 数值容差校验均值(仅统计含数值期望的题;None 已写为空串)
    if "numeric_rate" in grades.columns:
        nr = pd.to_numeric(grades["numeric_rate"], errors="coerce").dropna()
        overall["numeric_recall"] = round(float(nr.mean()), 4) if not nr.empty else None
        overall["n_questions_with_numbers"] = int(nr.shape[0])
    overall["accuracy_vs_votes"] = _accuracy_vs_votes(qlv)

    breakdowns = {}
    for f in BREAKDOWN_FIELDS:
        if f not in qlv.columns:
            continue
        g = qlv.groupby(f).agg(
            n=("question_id", "count"),
            mean_score=("mean_score", "mean"),
            accuracy=("pass_rate", "mean"),
            stable_accuracy=("stable_pass", "mean"),
            refusal_rate=("refusal_rate", "mean"),
        ).round(4).reset_index().sort_values("n", ascending=False)
        breakdowns[f] = g.to_dict(orient="records")
    breakdowns["by_category"] = metrics_cats

    # Two-factor interaction table for the controlled T1 axes.
    interaction = qlv.groupby(["organism", "salt_to"], dropna=False).agg(
        n=("question_id", "count"), mean_score=("mean_score", "mean"),
        accuracy=("pass_rate", "mean"), stable_accuracy=("stable_pass", "mean"),
    ).round(4).reset_index()

    hardest = qlv.nsmallest(10, "mean_score")[["question_id", "mean_score", "pass_rate"]]
    easiest = qlv.nlargest(10, "mean_score")[["question_id", "mean_score", "pass_rate"]]

    return {
        "overall": overall,
        "breakdowns": breakdowns,
        "organism_salt_interaction": interaction.to_dict(orient="records"),
        "hardest": hardest.to_dict(orient="records"),
        "easiest": easiest.to_dict(orient="records"),
        "question_level": qlv,
    }
