"""Run offline judge reliability/bias probes against an existing run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wwbench.dataset import load_questions  # noqa: E402
from wwbench.judge_audit import AuditConfig, run_judge_audit  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="WWBench judge 自洽性/交叉/偏差审计")
    ap.add_argument("--config", required=True, help="原运行 YAML 配置")
    ap.add_argument("--run-dir", default="", help="包含 responses.csv 的目录,默认按配置推导")
    ap.add_argument("--judge-b-config", default="", help="可选第二 judge 配置 YAML")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--max-questions", type=int, default=0)
    ap.add_argument("--low-consistency", type=float, default=0.67)
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    root = cfg_path.parents[1]
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    csv_path = Path(cfg["questions_csv"])
    csv_path = csv_path if csv_path.is_absolute() else root / csv_path
    run_dir = Path(args.run_dir) if args.run_dir else root / cfg.get("output_dir", "outputs") / cfg.get("run_name", "run")
    responses_path = run_dir / "responses.csv"
    if not responses_path.exists():
        raise FileNotFoundError(f"找不到 {responses_path},请先完成 answer 阶段")
    questions = load_questions(csv_path)
    responses = pd.read_csv(responses_path, encoding="utf-8-sig", keep_default_na=False)
    judge_b = None
    if args.judge_b_config:
        b_path = Path(args.judge_b_config)
        b_cfg = yaml.safe_load(b_path.read_text(encoding="utf-8"))
        judge_b = b_cfg.get("judge", b_cfg)
    summary = run_judge_audit(
        questions, responses, cfg.get("judge") or {}, run_dir / "judge_audit",
        judge_b_cfg=judge_b,
        config=AuditConfig(repeats=max(1, args.repeats), max_questions=args.max_questions,
                           low_consistency_threshold=args.low_consistency),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
