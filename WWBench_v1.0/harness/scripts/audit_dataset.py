"""题库健康审计:模板簇检测 + 完整性检查(对应 BixBench 的 LLM 去重/质检环节)。

BixBench 出题后用 LLM 三次独立标记重复题再人工核实;这里用确定性的
"数字归一化 + 文本签名"做模板簇聚类——同簇题目仅数值/菌株/反应器等槽位不同,
评测时应意识到它们本质是同一题面的实例,统计口径上相关。

用法:python scripts/audit_dataset.py [--csv data/questions.csv] [--out outputs/audit_report.md]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wwbench.dataset import COLUMN_MAP, load_questions  # noqa: E402

# 模板签名:数字、百分数、菌株名、反应器代号都视作可变槽位
_SLOT_PATTERNS = [
    (re.compile(r"-?\d+(?:\.\d+)?\s*%?"), "#"),
    (re.compile(r"(?:Kuenenia|Brocadia|Jettenia|Scalindua|Anammoxoglobus)-P\d+"), "GENOME"),
    (re.compile(r"HRT\s*\d+\s*h"), "HRT#"),
]


def template_signature(text: str) -> str:
    for pat, repl in _SLOT_PATTERNS:
        text = pat.sub(repl, text)
    return re.sub(r"\s+", "", text)[:120]


def audit(questions) -> dict:
    clusters: dict[str, list[str]] = defaultdict(list)
    for q in questions:
        clusters[template_signature(q.question)].append(q.question_id)

    template_clusters = sorted(
        (list(v) for v in clusters.values() if len(v) > 1), key=lambda v: -len(v)
    )
    singleton_n = sum(1 for v in clusters.values() if len(v) == 1)

    issues = {
        "no_references": [q.question_id for q in questions if not q.references],
        "few_keypoints": [q.question_id for q in questions if q.num_keypoints < 3],
        "no_ideal_detail": [q.question_id for q in questions if len(q.ideal_detail) < 50],
        "declared_attachment_missing": [
            q.question_id for q in questions
            if re.search(r"附件\s*[A-Za-z]+-P\d+\.fna", q.question)
        ],
    }
    return {
        "n_questions": len(questions),
        "n_signatures": len(clusters),
        "singleton_questions": singleton_n,
        "template_clusters": template_clusters,
        "issues": issues,
    }


def audit_schema(csv_path: Path) -> dict:
    """Report the on-disk CSV schema separately from the parsed Question model."""
    columns = list(pd.read_csv(csv_path, encoding="utf-8-sig", nrows=0).columns)
    expected = list(COLUMN_MAP.keys())
    return {
        "actual_columns": len(columns),
        "expected_parser_columns": len(expected),
        "missing_columns": [column for column in expected if column not in columns],
        "extra_columns": [column for column in columns if column not in expected],
    }
def render(report: dict, csv_path: str, schema: dict) -> str:
    lines = [
        "# 题库审计报告",
        "",
        f"- CSV schema:实际 {schema['actual_columns']} 列,解析器需要 {schema['expected_parser_columns']} 列;"
        f"缺失 {len(schema['missing_columns'])} 列,额外 {len(schema['extra_columns'])} 列",
        "",
        "## Schema 差异",
        "",
        f"- 缺失列:{schema['missing_columns'] or '无'}",
        f"- 额外列:{schema['extra_columns'] or '无'}",
        "",
        f"- 题目数:{report['n_questions']},去槽位后独立题面:{report['n_signatures']}"
        f"(其中单例题 {report['singleton_questions']} 道)",
        "",
        "## 模板簇(同簇仅数值/菌株/反应器等槽位不同)",
        "",
    ]
    for i, cluster in enumerate(report["template_clusters"], 1):
        lines.append(f"{i}. **{len(cluster)} 题**:{', '.join(cluster)}")
    if not report["template_clusters"]:
        lines.append("(无)")

    lines += ["", "## 完整性问题", ""]
    zh = {
        "no_references": "无参考文献",
        "few_keypoints": "打分要点 <3 条",
        "no_ideal_detail": "参考答案过短(<50 字)",
        "declared_attachment_missing": "题面声明了 .fna 附件(注意准备 data/attachments)",
    }
    for key, label in zh.items():
        ids = report["issues"][key]
        lines.append(f"- {label}:{len(ids)} 题" + (f"({', '.join(ids[:12])}{'…' if len(ids) > 12 else ''})" if ids else ""))

    lines += [
        "",
        "## 建议",
        "",
        "- 模板簇内的题目统计相关:汇报总体 accuracy 时建议同时给出"
        "「独立题面口径」(每簇只计一题)作为参考;",
        "- 大簇(≥5 题)若全部保留,等于对该模板加权;可考虑分层抽样或扩充题面多样性;",
        "- 声明 .fna 附件的题目请把文件放入 data/attachments/<question_id>/,"
        "智能体模式会自动分发到该题工作区。",
        "",
        f"审计对象:`{csv_path}`",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="WWBench 题库审计")
    ap.add_argument("--csv", default="data/questions.csv")
    ap.add_argument("--out", default="outputs/audit_report.md")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    csv_path = Path(args.csv)
    csv_path = csv_path if csv_path.is_absolute() else root / csv_path
    questions = load_questions(csv_path)

    report = audit(questions)
    text = render(report, str(csv_path), audit_schema(csv_path))
    out = Path(args.out)
    out = out if out.is_absolute() else root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    n_clustered = sum(len(c) for c in report["template_clusters"])
    print(f"[audit] {report['n_questions']} 题 / {report['n_signatures']} 个独立题面; "
          f"{n_clustered} 题属于 {len(report['template_clusters'])} 个模板簇")
    print(f"[audit] 报告: {out}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
