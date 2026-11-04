# -*- coding: utf-8 -*-
"""B2+B3: 52 题金标准全量真实模型跑分,内置校准尺熔断硬闸门。

前置:B1(run_real_smoke.py)五闸门全部通过。

用法:
  set WWBENCH_API_KEY=sk-xxx            # solver(GLM/DeepSeek/Qwen 任一 OpenAI 兼容端点)
  set WWBENCH_JUDGE_KEY=sk-yyy          # 必填:B2 成绩单必须 LLM judge(异厂商)
  python scripts/run_real_full.py [--model glm-4.7] [--judge-model gpt-4o]

产出(outputs/real_<model>_<date>/):
  - grades.csv / responses.csv(框架原生,即 per-question 明细;含六维/overall/复跑号)
  - per_question_aggregate.csv(每题 5 复跑聚合:均分/标准差/达标)
  - summary_real.json(跨题+跨复跑两层聚合:六维均分、overall、标准差)
  - evidence_hist.png(evidence 维分布直方图,确认非退化常量)
  - calibration_gate.json(B3 熔断闸门判定)

B3 硬闸门(自动执行,越界即退出码 2):
  overall > 0.9840(oracle) → 停:先查泄漏(题库/答案/capsule 是否在模型训练数据);
  overall < 0.4965(degraded) → 停:先抽样 5 题人工读 responses 再判;
  落在 [0.4965, 0.9840] → 允许进入阶段 C。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ORACLE_UPPER = 0.9840   # v1.0.1 oracle_calibration mean_score(5710 runs 实测)
DEGRADED_LOWER = 0.4965  # v1.0.1 oracle_degraded50 dim_norm 口径对照下界(见下注)
# 注:B3 阈值取整改台账口径——上界=oracle mean 0.9840;下界取 degraded mean 0.5312
# 与任务书原文 0.4965 的并集保守值(取更低者 0.4965,宁可多留检查空间)。


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("WWBENCH_MODEL", "glm-4.7"))
    ap.add_argument("--judge-model", default=os.environ.get("WWBENCH_JUDGE_MODEL", "gpt-4o"))
    ap.add_argument("--limit", type=int, default=0, help="调试用;正式跑不加")
    args = ap.parse_args()

    key = os.environ.get("WWBENCH_API_KEY", "").strip()
    judge_key = os.environ.get("WWBENCH_JUDGE_KEY", "").strip()
    if not key or not judge_key:
        print("[FAIL] B2 需要 WWBENCH_API_KEY 与 WWBENCH_JUDGE_KEY(成绩单必须 LLM judge 且与 solver 异厂商)")
        return 1

    run_name = f"real_{args.model.replace('/', '_')}_{date.today().isoformat()}"
    out_dir = ROOT / "outputs" / run_name
    cfg = out_dir / "config_generated.yaml"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        f"run_name: {run_name}\n"
        f"questions_csv: ../dataset/questions-verified-52.csv\n"  # 52 题专家金标准
        f"output_dir: {out_dir.as_posix()}\n"
        "context_mode: closed\n"
        "replicates: 5\nmax_workers: 2\ntemperature: 0.2\nmax_tokens: 4096\n"
        "solver:\n  provider: openai\n"
        f"  model: {args.model}\n  base_url: {os.environ.get('WWBENCH_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4')}\n"
        "  api_key_env: WWBENCH_API_KEY\n  retries: 3\n"
        "judge:\n  provider: openai\n"
        f"  model: {args.judge_model}\n  base_url: {os.environ.get('WWBENCH_JUDGE_BASE_URL', 'https://api.openai.com/v1')}\n"
        "  api_key_env: WWBENCH_JUDGE_KEY\n  temperature: 0.0\n  max_tokens: 2048\n"
        "rubric:\n  pass_threshold: 0.6\n  kp_weight: 0.5\n",
        encoding="utf-8",
    )
    cmd = [sys.executable, str(ROOT / "scripts" / "run_bench.py"), "--config", str(cfg)]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (out_dir / "run_stdout.log").write_text(
        (proc.stdout or "") + "\n[stderr]\n" + (proc.stderr or ""), encoding="utf-8")
    print(proc.stdout[-1200:])

    import pandas as pd

    grades = pd.read_csv(out_dir / "grades.csv", encoding="utf-8-sig")
    dims = ["accuracy", "completeness", "mechanism", "feasibility", "evidence", "rigor"]
    dim_cols = [f"dim_{d}" for d in dims]

    # 跨复跑聚合 → 跨题聚合(两层标准差)
    agg = (grades.groupby("question_id")
           .agg(mean_score=("composite_score", "mean"),
                std_across_runs=("composite_score", "std"),
                n_runs=("composite_score", "size"),
                **{f"{d}_mean": (f"dim_{d}", "mean") for d in dims})
           .reset_index())
    agg.to_csv(out_dir / "per_question_aggregate.csv", index=False, encoding="utf-8-sig")

    import numpy as np

    summary = {
        "run": run_name,
        "n_questions": int(agg.shape[0]),
        "n_runs": int(len(grades)),
        "overall": {
            "mean": float(grades["composite_score"].mean()),
            "std_across_runs": float(grades["composite_score"].std()),
            "std_across_questions": float(agg["mean_score"].std()),
            "pass_rate": float((grades["composite_score"] >= 0.6).mean()),
        },
        "per_dim_mean": {d: round(float(grades[f"dim_{d}"].mean()), 4) for d in dims},
        "per_dim_std_across_questions": {d: round(float(agg[f"{d}_mean"].std()), 4) for d in dims},
    }
    (out_dir / "summary_real.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # evidence 直方图(非退化确认)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    grades["dim_evidence"].value_counts().sort_index().plot.bar(ax=ax)
    ax.set_xlabel("dim_evidence(0-2)")
    ax.set_ylabel("count")
    ax.set_title(f"evidence distribution — {run_name}")
    fig.tight_layout()
    fig.savefig(out_dir / "evidence_hist.png", dpi=150)

    # B3 熔断硬闸门
    overall = summary["overall"]["mean"]
    if overall > ORACLE_UPPER:
        verdict = "STOP_ABOVE_ORACLE"
        action = "立即停止:先查泄漏(题库/参考答案/capsule 是否在模型训练数据内;抽查 10 题逐字命中),不许发版"
    elif overall < DEGRADED_LOWER:
        verdict = "STOP_BELOW_DEGRADED"
        action = "立即停止:抽样 5 题人工读 responses.csv,判模型真弱 vs harness/提示词退化"
    else:
        verdict = "PASS_TO_PHASE_C"
        action = "落在校准区间 [0.4965, 0.9840] 内,允许进入阶段 C"
    gate = {"overall": round(overall, 4), "oracle_upper": ORACLE_UPPER,
            "degraded_lower": DEGRADED_LOWER, "verdict": verdict, "action": action,
            "evidence_unique_values": sorted(float(v) for v in grades["dim_evidence"].unique())}
    (out_dir / "calibration_gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[B3] {verdict} — overall={overall:.4f};{action}")
    return 0 if verdict == "PASS_TO_PHASE_C" else 2


if __name__ == "__main__":
    raise SystemExit(main())
