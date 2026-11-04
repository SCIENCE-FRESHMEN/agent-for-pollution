# -*- coding: utf-8 -*-
"""C1: real 档与 degraded 档逐题均分 delta 的 bootstrap 95% CI(1000 次重抽样)。

用法(C 阶段,B2 出数后):
  python scripts/bootstrap_ci.py \
    --real outputs/real_<model>_<date>/per_question_aggregate.csv \
    --baseline ../results/oracle_degraded50/question_level.csv

输出:每维与综合分的 delta、bootstrap 95% CI、p 双侧近似;写 --out JSON。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    import numpy as np
    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("--real", required=True, help="per_question_aggregate.csv")
    ap.add_argument("--baseline", required=True, help="degraded 档 question_level.csv")
    ap.add_argument("--col-real", default="mean_score")
    ap.add_argument("--col-base", default="mean_score")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    real = pd.read_csv(args.real, encoding="utf-8-sig")[args.col_real].dropna().to_numpy()
    base = pd.read_csv(args.baseline, encoding="utf-8-sig")[args.col_base].dropna().to_numpy()
    rng = np.random.default_rng(args.seed)
    delta_obs = float(real.mean() - base.mean())
    boots = np.empty(args.n)
    for i in range(args.n):
        r = rng.choice(real, size=len(real), replace=True).mean()
        b = rng.choice(base, size=len(base), replace=True).mean()
        boots[i] = r - b
    lo, hi = np.percentile(boots, [2.5, 97.5])
    p_two_sided = float((np.abs(boots - boots.mean()) >= abs(delta_obs - boots.mean())).mean())
    result = {
        "delta_mean": round(delta_obs, 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
        "p_two_sided_approx": round(p_two_sided, 4),
        "n_bootstrap": args.n, "n_real": int(len(real)), "n_baseline": int(len(base)),
        "significant_at_95": bool(lo > 0 or hi < 0),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
