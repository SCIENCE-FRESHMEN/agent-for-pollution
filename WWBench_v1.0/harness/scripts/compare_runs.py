"""多 run 横向对比:汇总 outputs/*/summary.json 生成排行榜表 + 分组柱状图。

对应 BixBench 图 4(多模型/多口径的总体表现对比)。

用法:python scripts/compare_runs.py [--runs a b c] [--out outputs/comparison_report.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

COLS = ["run", "solver", "mode", "mean_score", "accuracy", "stable_accuracy",
        "refusal_rate", "numeric_recall", "keypoint_coverage"]


def collect(outputs_dir: Path, run_names: list[str]) -> pd.DataFrame:
    rows = []
    for run_dir in sorted(outputs_dir.iterdir() if not run_names
                          else [outputs_dir / n for n in run_names]):
        summary = run_dir / "summary.json"
        if not summary.exists():
            continue
        data = json.loads(summary.read_text(encoding="utf-8"))
        o = data.get("overall", {})
        cfg = data.get("config", {})
        rows.append({
            "run": run_dir.name,
            "solver": (cfg.get("solver", {}).get("model")
                       or cfg.get("solver", {}).get("provider", "?")),
            "mode": "agent" if cfg.get("solver", {}).get("agent") else "single",
            "mean_score": o.get("mean_score"),
            "accuracy": o.get("accuracy"),
            "stable_accuracy": o.get("stable_accuracy"),
            "refusal_rate": o.get("refusal_rate"),
            "numeric_recall": o.get("numeric_recall"),
            "keypoint_coverage": o.get("keypoint_coverage"),
        })
    return pd.DataFrame(rows, columns=COLS)


def make_plot(df: pd.DataFrame, out_png: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        matplotlib.rcParams["font.sans-serif"] = [
            "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "PingFang SC",
            "Arial Unicode MS", "sans-serif",
        ]
        matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    fig, ax = plt.subplots(figsize=(max(6, 1.2 * len(df)), 4))
    x = range(len(df))
    ax.bar([i - 0.25 for i in x], df["accuracy"], width=0.25, label="逐次达标率", color="#4C72B0")
    ax.bar([i for i in x], df["stable_accuracy"], width=0.25, label="多数达标率", color="#DD8452")
    ax.bar([i + 0.25 for i in x], df["mean_score"], width=0.25, label="平均分", color="#55A868")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["run"], rotation=20, ha="right", fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_title("各 run 总体表现对比")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="WWBench 多 run 对比")
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--runs", nargs="*", default=[], help="要对比的 run 名(默认全部)")
    ap.add_argument("--out", default="outputs/comparison_report.md")
    args = ap.parse_args()

    outputs_dir = Path(args.outputs)
    outputs_dir = outputs_dir if outputs_dir.is_absolute() else ROOT / outputs_dir
    df = collect(outputs_dir, args.runs)
    if df.empty:
        print("[compare] 没有找到含 summary.json 的 run")
        return 1

    zh = {"run": "run", "solver": "模型", "mode": "模式", "mean_score": "平均分",
          "accuracy": "逐次达标率", "stable_accuracy": "多数达标率", "refusal_rate": "拒答率",
          "numeric_recall": "数值召回", "keypoint_coverage": "要点覆盖率"}
    lines = [
        "# WWBench 多 run 对比",
        "",
        df.rename(columns=zh).to_markdown(index=False),
        "",
    ]
    plotted = make_plot(df, outputs_dir / "comparison.png")
    if plotted:
        lines.append("![对比图](comparison.png)")
    else:
        lines.append("(matplotlib 不可用,仅输出表格)")

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[compare] {len(df)} 个 run -> {out}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
