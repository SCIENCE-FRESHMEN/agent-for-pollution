"""报告生成:summary.json + report.md + 分层柱状图。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .dataset import dataset_stats
from .metrics import compute_metrics

FIELD_CN = {
    "tag": "标签", "topic": "主题", "difficulty": "难度", "qtype": "题型",
    "domain": "细分", "organism": "优势菌", "salt_to": "目标盐度",
    "genome_file": "基因组档案", "by_category": "类别标签(多标签)",
    "category": "类别标签", "n": "题数", "mean_score": "平均分", "accuracy": "逐次达标率",
    "stable_accuracy": "多数达标率", "refusal_rate": "拒答率",
    "low": "下限", "high": "上限",
}


def _df_md(rows: list[dict]) -> str:
    if not rows:
        return "(无数据)"
    df = pd.DataFrame(rows)
    df = df.rename(columns={k: v for k, v in FIELD_CN.items() if k in df.columns})
    return df.to_markdown(index=False)


def make_plots(metrics: dict, out_dir: Path) -> list[str]:
    """按分层生成柱状图;matplotlib 缺失时静默跳过。"""
    try:
        import matplotlib

        matplotlib.use("Agg")
        # 中文字体(Windows 优先微软雅黑,否则尝试常见 CJK 字体),避免图中中文变方框
        matplotlib.rcParams["font.sans-serif"] = [
            "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "PingFang SC",
            "Arial Unicode MS", "sans-serif",
        ]
        matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    overall = metrics["overall"]
    per_dim = overall.get("per_dim") or {}

    if per_dim:
        fig, ax = plt.subplots(figsize=(7, 3.5))
        names = list(per_dim)
        vals = [per_dim[n] for n in names]
        ax.bar(names, vals, color="#4C72B0")
        ax.set_ylim(0, 1)
        ax.set_ylabel("归一化得分")
        ax.set_title("六维评分均值")
        fig.tight_layout()
        p = out_dir / "dims_overall.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(str(p))

    # 投票数-准确率曲线(对应 BixBench 图 5)
    avv = overall.get("accuracy_vs_votes") or {}
    if len(avv) > 1:
        fig, ax = plt.subplots(figsize=(5.5, 3.5))
        ks = sorted(int(k) for k in avv)
        ax.plot(ks, [avv[k] for k in ks], marker="o", color="#55A868")
        ax.set_xlabel("投票数 k(m 次抽样取多数)")
        ax.set_ylabel("多数达标率")
        ax.set_ylim(0, 1)
        ax.set_title("准确率随投票数的变化")
        fig.tight_layout()
        p = out_dir / "accuracy_vs_votes.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(str(p))

    # 每题平均分分布(对应 BixBench 图 7/8 的 per-question 视角)
    qlv = metrics.get("question_level")
    if qlv is not None and not qlv.empty and "mean_score" in qlv.columns:
        fig, ax = plt.subplots(figsize=(5.5, 3.5))
        ax.hist(pd.to_numeric(qlv["mean_score"], errors="coerce").dropna(),
                bins=20, range=(0, 1), color="#C44E52")
        ax.set_xlabel("每题平均分")
        ax.set_ylabel("题目数")
        ax.set_title("题目难度分布(越靠左越难)")
        fig.tight_layout()
        p = out_dir / "question_score_hist.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(str(p))

    for field, rows in (metrics.get("breakdowns") or {}).items():
        if not rows:
            continue
        key = "category" if field == "by_category" else field
        fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(rows)), 3.5))
        labels = [str(r.get(key, ""))[:14] for r in rows]
        acc = [r["accuracy"] for r in rows]
        stable = [r["stable_accuracy"] for r in rows]
        x = range(len(rows))
        ax.bar([i - 0.2 for i in x], acc, width=0.4, label="逐次达标率", color="#4C72B0")
        ax.bar([i + 0.2 for i in x], stable, width=0.4, label="多数达标率", color="#DD8452")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
        ax.set_ylim(0, 1)
        ax.set_title(f"按{FIELD_CN.get(field, field)}分层")
        ax.legend()
        fig.tight_layout()
        p = out_dir / f"breakdown_{field}.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(str(p))

    interaction = metrics.get("organism_salt_interaction") or []
    if interaction:
        pivot = pd.DataFrame(interaction).pivot(index="organism", columns="salt_to", values="mean_score")
        fig, ax = plt.subplots(figsize=(max(7, 0.9 * len(pivot.columns)), max(4, 0.45 * len(pivot.index))))
        im = ax.imshow(pivot.fillna(float("nan")), cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(pivot.columns)), [str(x) for x in pivot.columns], rotation=35, ha="right")
        ax.set_yticks(range(len(pivot.index)), [str(x) for x in pivot.index])
        ax.set_xlabel("目标盐度")
        ax.set_ylabel("优势菌")
        ax.set_title("优势菌 × 目标盐度平均分")
        fig.colorbar(im, ax=ax, label="平均综合分")
        fig.tight_layout()
        p = out_dir / "interaction_organism_salt.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(str(p))
    return paths


def write_report(
    questions,
    grades: pd.DataFrame,
    metrics: dict,
    out_dir: Path,
    config: dict,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = dataset_stats(questions)
    if "overall" not in metrics or not len(grades):
        # 全部作答出错/为空(v1.1 修复:原实现此处 KeyError 崩溃)。仍落盘诊断
        # 信息与最小报告,主链路不中断;断点续跑不会重复已成功条目。
        summary = {
            "overall": {},
            "dataset_stats": stats,
            "config": config,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "note": "无有效评分行(全部作答出错或为空)。请检查 solver 配置"
                    "(api_key/base_url/model)、网络与配额后重跑。",
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report_path = out_dir / "report.md"
        report_path.write_text(
            "# WWBench 评测报告\n\n**本次运行没有产生任何有效评分行。**\n\n"
            "请检查求解模型配置(api_key / base_url / model)、网络与配额后重跑;\n"
            "断点续跑会自动跳过已成功的 (question_id, replicate) 条目。\n",
            encoding="utf-8",
        )
        print(f"[report ] {report_path}(空结果守卫:无有效评分行)")
        return report_path
    o = metrics["overall"]

    # summary.json(question_level 单独存 csv)
    summary = {k: v for k, v in metrics.items() if k != "question_level"}
    summary["dataset_stats"] = stats
    summary["config"] = config
    summary["generated_at"] = datetime.now().isoformat(timespec="seconds")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metrics["question_level"].to_csv(out_dir / "question_level.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# WWBench 评测报告",
        "",
        f"生成时间:{summary['generated_at']}",
        "",
        "## 1. 题库概览",
        "",
        f"- 题目数:{stats['n_questions']},打分要点总数:{stats['n_keypoints']}"
        f"(平均 {stats['avg_keypoints_per_question']}/题)",
        f"- 难度分布:{stats['by_difficulty']}",
        f"- 题型分布:{stats['by_qtype']}",
        f"- 因子设计轴(题面解析):优势菌 {stats['by_organism']};"
        f"盐度区间 {stats['by_salt_regime']}",
        "",
        "## 2. 运行配置",
        "",
        f"- 求解模型:`{config.get('solver', {}).get('model', config.get('solver', {}).get('provider', '?'))}`"
        f",复跑次数:{config.get('replicates', '?')},上下文模式:{config.get('context_mode', 'closed')}",
        f"- 评分器:`{config.get('judge', {}).get('provider', '?')}`,通过阈值:{o['pass_threshold']}",
        "",
        "## 3. 总体指标",
        "",
        f"- 评测覆盖:期望 {o.get('n_questions_expected', stats['n_questions'])} 题,"
        f"实际评测 {o.get('n_questions_evaluated', o.get('n_questions', 0))} 题,"
        f"缺失 {o.get('n_questions_missing', 0)} 题,"
        f"未知题号 {o.get('n_unknown_question_ids', 0)} 个",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| 平均综合分 | {o['mean_score']} |",
        f"| 逐次达标率 (accuracy) | {o['accuracy']} |",
        f"| accuracy Wilson 95% CI | {o.get('accuracy_wilson_95', {})} |",
        f"| 多数达标率 (stable, majority-vote 口径) | {o['stable_accuracy']} |",
        f"| stable Wilson 95% CI | {o.get('stable_accuracy_wilson_95', {})} |",
        f"| 拒答率 | {o['refusal_rate']} |",
        f"| 非拒答作答平均分 (precision 口径) | {o['precision_on_answered']} |",
        f"| 要点覆盖率 | {o['keypoint_coverage']} |",
        f"| 六维归一分 | {o['dim_norm']} |",
        f"| 数值召回(容差校验{config.get('rubric', {}).get('numeric_tolerance', 0.05):.0%}内) "
        f"| {o.get('numeric_recall', '—')} |",
    ]
    if o.get("per_dim"):
        lines += ["", "六维明细:"]
        lines += [f"- {k}: {v}" for k, v in o["per_dim"].items()]

    for field, rows in (metrics.get("breakdowns") or {}).items():
        lines += ["", f"## 按{FIELD_CN.get(field, field)}分层", "", _df_md(rows)]

    interaction = metrics.get("organism_salt_interaction") or []
    if interaction:
        lines += ["", "## 优势菌 × 目标盐度交互", "", _df_md(interaction)]

    lines += ["", "## 最难题目 Top10", "", _df_md(metrics["hardest"])]
    lines += ["", "## 最易题目 Top10", "", _df_md(metrics["easiest"])]

    plots = make_plots(metrics, out_dir / "plots")
    if plots:
        lines += ["", "## 图表", ""]
        lines += [f"![{Path(p).stem}](plots/{Path(p).name})" for p in plots]

    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
