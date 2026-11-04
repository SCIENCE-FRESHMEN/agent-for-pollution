# -*- coding: utf-8 -*-
"""B1: 真实模型 5 题冒烟(参数化读环境变量,密钥不落盘)。

用法(密钥只经环境变量注入,禁止写入任何文件):
  set WWBENCH_API_KEY=sk-xxx
  set WWBENCH_JUDGE_KEY=sk-yyy        (可选;缺省用 heuristic judge 并显式标记)
  python scripts/run_real_smoke.py

验收闸门(全部通过才允许进 B2 全量):
  (a) 无 401/无限流/无未捕获异常(error 列全空);
  (b) grades.csv 列集与 oracle 档 grades.csv 完全同构(WWBench 产物为 CSV,
      与 BixBench 的 JSONL 不同,如实按本仓格式验收同构性);
  (c) 空结果守卫未触发(report.md 非守卫版);
  (d) 六维分全部 ∈[0,2](归一 [0,1]),且 evidence 维 5 题不全部等于 1.0
      (归一 0.5——若全为 1.0 说明锚点命中法在真实回答下又退化为常量,立即停);
  (e) fdp_check/rank_check 在本题集作答上调用不抛异常(当前题集无对应金标准,
      属空集调用,如实报告 vacuous)。

题号说明:用户要求 q-001~q-005,但题库题号自 q-061 起,不存在 q-001;按
`--limit 5` 取文件顺序前 5 题(q-061,q-104,q-105,q-113,q-118),此处如实声明。
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "real_smoke"
CFG = OUT / "config_generated.yaml"

HEURISTIC_JUDGE_NOTE = (
    "WWBENCH_JUDGE_KEY 未设置,使用 heuristic judge(仅用于链路冒烟;"
    "B2 全量与成绩单必须配置 LLM judge, judge 与 solver 须异厂商)"
)


def main() -> int:
    key = os.environ.get("WWBENCH_API_KEY", "").strip()
    if not key:
        print("[FAIL] 未检测到 WWBENCH_API_KEY 环境变量;密钥只经环境变量注入,不写入文件")
        return 1
    base_url = os.environ.get("WWBENCH_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    model = os.environ.get("WWBENCH_MODEL", "glm-4.7")
    judge_key = os.environ.get("WWBENCH_JUDGE_KEY", "").strip()
    judge_model = os.environ.get("WWBENCH_JUDGE_MODEL", "gpt-4o")
    judge_base = os.environ.get("WWBENCH_JUDGE_BASE_URL", "https://api.openai.com/v1")

    judge_block = (
        f"judge:\n  provider: openai\n  model: {judge_model}\n"
        f"  base_url: {judge_base}\n  api_key_env: WWBENCH_JUDGE_KEY\n"
        "  temperature: 0.0\n  max_tokens: 2048\n"
        if judge_key else
        "judge:\n  provider: heuristic\n  token_hit_ratio: 0.4\n"
    )
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(
        "run_name: real_smoke\n"
        "questions_csv: data/questions.csv\n"
        f"output_dir: {OUT.as_posix()}\n"
        "context_mode: closed\n"
        "replicates: 1\nmax_workers: 2\ntemperature: 0.2\nmax_tokens: 4096\n"
        "solver:\n  provider: openai\n"
        f"  model: {model}\n  base_url: {base_url}\n"
        "  api_key_env: WWBENCH_API_KEY\n  retries: 3\n"
        + judge_block +
        "rubric:\n  pass_threshold: 0.6\n  kp_weight: 0.5\n",
        encoding="utf-8",
    )
    print(f"[cfg] solver={model} @ {base_url};judge={'LLM:' + judge_model if judge_key else 'heuristic(见注)'}")
    if not judge_key:
        print(f"[warn] {HEURISTIC_JUDGE_NOTE}")

    env = dict(os.environ)
    env["WWBENCH_JUDGE_KEY"] = judge_key  # 可为空串;provider 仅在 openai 分支读取
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_bench.py"),
         "--config", str(CFG), "--limit", "5", "--no-resume"],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    (OUT / "run_stdout.log").write_text(
        (proc.stdout or "") + "\n[stderr]\n" + (proc.stderr or ""), encoding="utf-8")
    print(proc.stdout[-1500:])

    import pandas as pd

    gates = []

    # (a) 错误闸门
    resp_path = OUT / "responses.csv"
    if not resp_path.exists():
        print("[FAIL] (a) 未产出 responses.csv")
        return 1
    resp = pd.read_csv(resp_path, encoding="utf-8-sig")
    errors = resp["error"].astype(str)
    n_err = (errors.str.strip() != "").sum()
    hard_err = errors.str.contains("401|429|RateLimit|Traceback", case=False, regex=True).sum()
    gates.append(("(a) 无401/限流/未捕获异常", n_err == 0 and hard_err == 0,
                  f"错误行={n_err}, 硬错误={hard_err}"))

    grades_path = OUT / "grades.csv"
    if not grades_path.exists():
        gates.append(("(b) schema 同构", False, "无 grades.csv"))
        gates.append(("(c) 空结果守卫未触发", False, "无 report.md 判定依据"))
        gates.append(("(d) 六维取值合法且 evidence 非退化", False, "无 grades.csv"))
    else:
        grades = pd.read_csv(grades_path, encoding="utf-8-sig")
        oracle = pd.read_csv(ROOT / "outputs" / "oracle_calibration" / "grades.csv",
                             encoding="utf-8-sig", nrows=1)
        gates.append(("(b) grades.csv 列集与 oracle 档同构",
                      list(grades.columns) == list(oracle.columns),
                      f"列差={set(grades.columns) ^ set(oracle.columns) or '无'}"))
        guard_text = (OUT / "report.md").read_text(encoding="utf-8")
        gates.append(("(c) 空结果守卫未触发", "没有产生任何有效评分行" not in guard_text,
                      "report.md 为守卫版" if "没有产生任何有效评分行" in guard_text else "正常报告"))
        dims = ["accuracy", "completeness", "mechanism", "feasibility", "evidence", "rigor"]
        in_range = all(grades[f"dim_{d}"].between(0, 2).all() for d in dims)
        ev = grades["dim_evidence"]
        degenerate = bool((ev == 1).all())
        gates.append(("(d) 六维∈[0,2] 且 evidence 非退化常量",
                      in_range and not degenerate and len(grades) > 0,
                      f"evidence 取值分布={sorted(ev.unique().tolist())} (归一后÷2)"))

    # (e) 客观校验器空集调用不抛异常
    try:
        from wwbench.graders import fdp_check, rank_check
        sample = ""
        if grades_path.exists():
            resp_df = pd.read_csv(grades_path, encoding="utf-8-sig")
            sample = resp_df.iloc[0].get("rationale", "") if len(resp_df) else ""
        fdp_check({"demo": "present"}, f'{{"demo": "present"}} // {sample[:50]}')
        rank_check(["A", "B"], ["A", "B"])
        gates.append(("(e) fdp/rank 校验器调用无异常", True, "本题集无 FDP/排序金标准,空集调用(vacuous,如实报告)"))
    except Exception as err:  # noqa: BLE001
        gates.append(("(e) fdp/rank 校验器调用无异常", False, repr(err)))

    all_pass = True
    for name, ok, detail in gates:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
        all_pass &= bool(ok)
    print(f"\n[B1] {'全部闸门通过 → 允许进入 B2 全量' if all_pass else '存在未通过闸门 → 禁止进入 B2'}")
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
