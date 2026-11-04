"""WWBench CLI 入口。

用法:
    python scripts/run_bench.py --config configs/run_mock.yaml                 # 全流程
    python scripts/run_bench.py --config configs/run_openai.yaml --limit 5    # 先试 5 题
    python scripts/run_bench.py --config configs/run_openai.yaml --stage grade  # 只评分已有回答
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wwbench.dataset import dataset_stats, filter_questions, load_questions  # noqa: E402
from wwbench.metrics import compute_metrics  # noqa: E402
from wwbench.report import write_report  # noqa: E402
from wwbench.runner import run_answers, run_grading  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="WWBench 评测流水线")
    ap.add_argument("--config", required=True, help="YAML 配置文件路径")
    ap.add_argument("--stage", default="all", choices=["answer", "grade", "report", "all"])
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题(0=全部)")
    ap.add_argument("--replicates", type=int, default=0, help="覆盖配置中的复跑次数")
    ap.add_argument("--no-resume", action="store_true", help="不复用已有结果,重跑全部")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    root = Path(args.config).resolve().parents[1]
    csv_path = Path(cfg["questions_csv"])
    csv_path = csv_path if csv_path.is_absolute() else root / csv_path
    out_dir = Path(cfg.get("output_dir", "outputs"))
    out_dir = out_dir if out_dir.is_absolute() else root / out_dir
    out_dir = out_dir / cfg.get("run_name", "run")

    replicates = args.replicates or int(cfg.get("replicates", 1))
    max_workers = int(cfg.get("max_workers", 4))
    rubric_cfg = cfg.get("rubric") or {}
    pass_threshold = float(rubric_cfg.get("pass_threshold", 0.6))
    kp_weight = float(rubric_cfg.get("kp_weight", 0.5))
    numeric_tol = float(rubric_cfg.get("numeric_tolerance", 0.05))
    att_dir = Path(cfg.get("attachments_dir", "data/attachments"))
    att_dir = att_dir if att_dir.is_absolute() else root / att_dir

    questions = load_questions(csv_path)
    questions = filter_questions(questions, **(cfg.get("filters") or {}))
    if args.limit:
        questions = questions[: args.limit]

    stats = dataset_stats(questions)
    print(f"[dataset] {stats['n_questions']} 题, {stats['n_keypoints']} 个打分要点, "
          f"难度={stats['by_difficulty']}")
    print(f"[output ] {out_dir}")

    responses = None
    if args.stage in ("answer", "all"):
        responses = run_answers(
            questions,
            cfg.get("solver") or {},
            out_dir,
            replicates=replicates,
            max_workers=max_workers,
            context_mode=cfg.get("context_mode", "closed"),
            resume=not args.no_resume,
            temperature=float(cfg.get("temperature", 0.2)),
            max_tokens=int(cfg.get("max_tokens", 4096)),
            attachments_root=att_dir if att_dir.exists() else None,
        )
        n_err = int((responses["error"].astype(str) != "").sum()) if not responses.empty else 0
        print(f"[answers] 完成: {len(responses)} 条回答, {n_err} 条出错")

    grades = None
    if args.stage in ("grade", "report", "all"):
        if responses is None:
            from wwbench.runner import _load_existing

            responses = _load_existing(out_dir / "responses.csv")
            if responses.empty:
                print("[grades] 无 responses.csv,请先运行 --stage answer")
                return 1
        grades = run_grading(
            questions, responses, cfg.get("judge") or {}, out_dir,
            max_workers=max_workers, kp_weight=kp_weight, resume=not args.no_resume,
            numeric_tol=numeric_tol,
        )
        print(f"[grades] 完成: {len(grades)} 条评分")

    if args.stage in ("report", "all"):
        if grades is None:
            from wwbench.runner import _load_existing

            grades = _load_existing(out_dir / "grades.csv")
            if grades.empty:
                print("[report] 无 grades.csv,请先运行 --stage grade")
                return 1
        metrics = compute_metrics(questions, grades, pass_threshold=pass_threshold)
        report_path = write_report(questions, grades, metrics, out_dir, cfg)
        o = metrics.get("overall")
        if not o:
            print(f"[report ] {report_path}(空结果守卫:无有效评分行,详见 summary.json 的 note)")
            return 0
        print(f"[report ] {report_path}")
        print(f"[summary] 平均分={o['mean_score']} 逐次达标率={o['accuracy']} "
              f"多数达标率={o['stable_accuracy']} 拒答率={o['refusal_rate']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
