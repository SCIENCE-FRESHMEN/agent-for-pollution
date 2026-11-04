"""Judge reliability and bias probes.

This module is deliberately separate from the production grading path.  It
replays already generated responses with one or two configured graders and
writes machine-readable evidence for judge self-consistency, inter-judge
agreement, and simple presentation-order/length probes.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .dataset import Question
from .graders import GradeResult, build_grader


@dataclass
class AuditConfig:
    repeats: int = 3
    pass_threshold: float = 0.6
    low_consistency_threshold: float = 0.67
    max_questions: int = 0
    seed: int = 17


def _signature(grade: GradeResult, pass_threshold: float) -> tuple:
    return (
        bool(grade.refused),
        tuple(bool(x) for x in grade.keypoint_hits),
        tuple(int(grade.dim_scores.get(k, 0)) for k in sorted(grade.dim_scores)),
        bool(grade.is_correct(pass_threshold)),
    )


def _binary_kappa(a: list[bool], b: list[bool]) -> float | None:
    if not a or len(a) != len(b):
        return None
    n = len(a)
    agree = sum(x == y for x, y in zip(a, b)) / n
    pa = sum(a) / n
    pb = sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected >= 1.0:
        return 1.0 if agree >= 1.0 else 0.0
    return round((agree - expected) / (1 - expected), 4)


def _answer_parts(text: str) -> list[str]:
    """Split numbered answers while keeping unstructured prose usable."""
    parts = [p.strip() for p in re.split(r"(?=\(?\d+[\)\.、])", text or "") if p.strip()]
    return parts if len(parts) >= 2 else [p.strip() for p in re.split(r"\n+", text or "") if p.strip()]


def expand_answer(text: str) -> str:
    """Length probe: duplicate the answer's substantive content once."""
    text = (text or "").strip()
    return f"{text}\n\n补充说明：\n{text}" if text else text


def compress_answer(text: str) -> str:
    """Length probe: retain roughly half of numbered/prose segments."""
    parts = _answer_parts(text)
    if len(parts) <= 1:
        compact = re.sub(r"\s+", " ", text or "").strip()
        return compact[: max(1, len(compact) // 2)]
    keep = max(1, (len(parts) + 1) // 2)
    return "\n".join(parts[:keep])


def shuffle_answer_order(text: str, seed: int = 17) -> str:
    parts = _answer_parts(text)
    if len(parts) <= 1:
        return text
    rng = random.Random(seed)
    rng.shuffle(parts)
    return "\n".join(parts)


def _valid_rows(responses: pd.DataFrame, max_questions: int) -> pd.DataFrame:
    df = responses.copy()
    if "error" in df.columns:
        df = df[df["error"].astype(str).eq("")]
    if "response" in df.columns:
        df = df[df["response"].astype(str).str.strip().ne("")]
    # One representative response per question keeps probes comparable and
    # prevents replicate imbalance from changing kappa.
    df = df.sort_values([c for c in ["question_id", "replicate"] if c in df.columns])
    df = df.drop_duplicates("question_id", keep="first")
    if max_questions:
        df = df.head(max_questions)
    return df


def _derived_second_config(cfg: dict) -> dict:
    """Make a deterministic offline contrast when no second judge is given."""
    out = dict(cfg or {})
    if out.get("provider", "heuristic") == "heuristic":
        out["token_hit_ratio"] = 0.6 if float(out.get("token_hit_ratio", 0.4)) < 0.6 else 0.4
    return out


def run_judge_audit(
    questions: list[Question],
    responses: pd.DataFrame,
    judge_a_cfg: dict,
    output_dir: Path,
    judge_b_cfg: dict | None = None,
    config: AuditConfig | None = None,
) -> dict[str, Any]:
    """Run reliability and bias probes and persist all intermediate evidence."""
    ac = config or AuditConfig()
    qmap = {q.question_id: q for q in questions}
    rows = _valid_rows(responses, ac.max_questions)
    grader_a = build_grader(judge_a_cfg)
    grader_b = build_grader(judge_b_cfg if judge_b_cfg is not None else _derived_second_config(judge_a_cfg))

    consistency_rows: list[dict[str, Any]] = []
    dual_rows: list[dict[str, Any]] = []
    bias_rows: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        qid = str(row["question_id"])
        q = qmap.get(qid)
        if q is None:
            continue
        response = str(row["response"])
        a_grades = [grader_a.grade(q, response) for _ in range(max(1, ac.repeats))]
        sigs = [_signature(g, ac.pass_threshold) for g in a_grades]
        exact_rate = sum(s == sigs[0] for s in sigs) / len(sigs)
        pass_values = [g.is_correct(ac.pass_threshold) for g in a_grades]
        pass_rate = sum(x == pass_values[0] for x in pass_values) / len(pass_values)
        consistency_rows.append({
            "question_id": qid,
            "judge": grader_a.name,
            "n_repeats": len(a_grades),
            "exact_consistency": round(exact_rate, 4),
            "pass_consistency": round(pass_rate, 4),
            "mean_score": round(sum(g.composite_score() for g in a_grades) / len(a_grades), 4),
            "needs_review": exact_rate < ac.low_consistency_threshold,
        })

        b_grade = grader_b.grade(q, response)
        a_pass = a_grades[0].is_correct(ac.pass_threshold)
        b_pass = b_grade.is_correct(ac.pass_threshold)
        dual_rows.append({
            "question_id": qid,
            "judge_a": grader_a.name,
            "judge_b": grader_b.name,
            "a_pass": a_pass,
            "b_pass": b_pass,
            "a_score": round(a_grades[0].composite_score(), 4),
            "b_score": round(b_grade.composite_score(), 4),
            "disagreement": a_pass != b_pass,
            "a_rationale": a_grades[0].rationale,
            "b_rationale": b_grade.rationale,
        })

        variants = {
            "original": response,
            "expanded": expand_answer(response),
            "compressed": compress_answer(response),
            "order_shuffled": shuffle_answer_order(response, ac.seed),
        }
        variant_grades = {name: grader_a.grade(q, text) for name, text in variants.items()}
        base = variant_grades["original"]
        for name, grade in variant_grades.items():
            bias_rows.append({
                "question_id": qid,
                "probe": name,
                "response_chars": len(variants[name]),
                "score": round(grade.composite_score(), 4),
                "pass": grade.is_correct(ac.pass_threshold),
                "score_delta_vs_original": round(grade.composite_score() - base.composite_score(), 4),
                "pass_flip_vs_original": grade.is_correct(ac.pass_threshold) != base.is_correct(ac.pass_threshold),
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    consistency = pd.DataFrame(consistency_rows)
    dual = pd.DataFrame(dual_rows)
    bias = pd.DataFrame(bias_rows)
    consistency.to_csv(output_dir / "judge_consistency.csv", index=False, encoding="utf-8-sig")
    dual.to_csv(output_dir / "judge_disagreements.csv", index=False, encoding="utf-8-sig")
    bias.to_csv(output_dir / "judge_bias_probes.csv", index=False, encoding="utf-8-sig")

    a_pass = dual["a_pass"].astype(bool).tolist() if not dual.empty else []
    b_pass = dual["b_pass"].astype(bool).tolist() if not dual.empty else []
    kappa = _binary_kappa(a_pass, b_pass)
    summary = {
        "n_questions": int(len(consistency)),
        "judge_a": grader_a.name,
        "judge_b": grader_b.name,
        "repeats": int(max(1, ac.repeats)),
        "low_consistency_threshold": ac.low_consistency_threshold,
        "n_low_consistency": int(consistency["needs_review"].sum()) if not consistency.empty else 0,
        "mean_exact_consistency": round(float(consistency["exact_consistency"].mean()), 4) if not consistency.empty else None,
        "mean_pass_consistency": round(float(consistency["pass_consistency"].mean()), 4) if not consistency.empty else None,
        "cohen_kappa_pass": kappa,
        "n_disagreements": int(dual["disagreement"].sum()) if not dual.empty else 0,
        "bias": {
            probe: {
                "mean_score_delta": round(float(g["score_delta_vs_original"].mean()), 4),
                "pass_flip_rate": round(float(g["pass_flip_vs_original"].mean()), 4),
            }
            for probe, g in bias[bias["probe"].ne("original")].groupby("probe")
        } if not bias.empty else {},
    }
    (output_dir / "judge_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_lines = [
        "# Judge 审计报告", "", f"- 题目数: {summary['n_questions']}",
        f"- Judge A: `{summary['judge_a']}`", f"- Judge B: `{summary['judge_b']}`",
        f"- 重复评分次数: {summary['repeats']}",
        f"- 平均精确一致率: {summary['mean_exact_consistency']}",
        f"- 待审题数(一致率低于 {ac.low_consistency_threshold:.0%}): {summary['n_low_consistency']}",
        f"- Cohen's kappa(达标二元标签): {summary['cohen_kappa_pass']}",
        f"- 双 judge 分歧题数: {summary['n_disagreements']}", "",
        "## 偏差探针", "",
        "| 探针 | 平均综合分变化 | 达标翻转率 |", "|---|---:|---:|",
    ]
    for probe, vals in summary["bias"].items():
        report_lines.append(f"| {probe} | {vals['mean_score_delta']} | {vals['pass_flip_rate']} |")
    report_lines += ["", "详细分歧见 `judge_disagreements.csv`；低一致题见 `judge_consistency.csv`。"]
    (output_dir / "judge_audit_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return summary

