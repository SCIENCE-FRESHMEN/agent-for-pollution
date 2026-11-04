"""运行器:并行生成回答(responses.csv)与评分(grades.csv),支持断点续跑。

对应 BixBench 的 generate_trajectories.py + grade_outputs.py 两阶段。
solver.agent 配置存在时走智能体模式(工具循环 + 每题工作区),否则单轮问答。
"""

from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd

from .agent import run_agent, save_trajectory, stage_workspace
from .dataset import Question
from .graders import GradeResult, build_grader, numeric_check
from .prompts import build_solver_prompt
from .providers import build_provider

RESPONSE_COLUMNS = [
    "question_id", "replicate", "solver", "context_mode", "mode",
    "system_prompt", "user_prompt", "response", "error", "trajectory_path", "timestamp",
]


def _load_existing(path: Path, empty_columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists():
        try:
            # keep_default_na=False:空字符串保持 "" 而不是变成 NaN,
            # 否则 str(NaN)="nan" 会被误判为"出错回答"而跳过评分
            return pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
        except Exception:  # noqa: BLE001 —— 损坏的结果文件视为不存在
            pass
    return pd.DataFrame(columns=empty_columns if empty_columns is not None else RESPONSE_COLUMNS)


def _done_keys(df: pd.DataFrame, cols: list[str]) -> set[tuple]:
    if df.empty:
        return set()
    return set(map(tuple, df[cols].astype(str).values.tolist()))


def run_answers(
    questions: list[Question],
    solver_cfg: dict,
    output_dir: Path,
    replicates: int = 1,
    max_workers: int = 4,
    context_mode: str = "closed",
    resume: bool = True,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    attachments_root: Path | None = None,
) -> pd.DataFrame:
    """阶段一:生成回答。每题跑 replicates 次(仿 BixBench 的 5 次并行复跑)。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "responses.csv"
    existing = _load_existing(out_path)
    if resume:
        done = _done_keys(existing, ["question_id", "replicate", "solver", "context_mode", "mode"])
    else:
        existing = existing.iloc[0:0]  # 全新重跑,丢弃旧结果避免重复拼接
        done = set()

    solver_cfg = dict(solver_cfg or {})
    agent_cfg = solver_cfg.get("agent")
    mode = "agent" if agent_cfg else "single"
    provider = build_provider(solver_cfg, questions)
    jobs = [
        (q, r)
        for q in questions
        for r in range(1, replicates + 1)
        if (q.question_id, str(r), provider.name, context_mode, mode) not in done
    ]

    rows: list[dict] = []
    if jobs:
        def _one(job: tuple[Question, int]) -> dict:
            q, rep = job
            row = {
                "question_id": q.question_id, "replicate": rep, "solver": provider.name,
                "context_mode": context_mode, "mode": mode,
                "system_prompt": "", "user_prompt": "", "response": "", "error": "",
                "trajectory_path": "",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            try:
                if agent_cfg:
                    workspace = output_dir / "workspaces" / f"{q.question_id}_r{rep}"
                    staged = stage_workspace(workspace, q, attachments_root,
                                             bool(agent_cfg.get("stage_references")))
                    res = run_agent(
                        provider, q, workspace,
                        max_steps=int(agent_cfg.get("max_steps", 30)),
                        exec_timeout=int(agent_cfg.get("exec_timeout", 60)),
                        temperature=temperature, max_tokens=max_tokens,
                        references_hint=staged,
                    )
                    row["response"] = res.answer
                    row["error"] = res.error[:500]
                    traj_rel = f"trajectories/{q.question_id}_r{rep}.jsonl"
                    save_trajectory(
                        output_dir / traj_rel, res,
                        {"question_id": q.question_id, "replicate": rep, "solver": provider.name,
                         "n_steps": res.n_steps},
                    )
                    row["trajectory_path"] = traj_rel
                else:
                    system, user = build_solver_prompt(q, context_mode)
                    row["system_prompt"], row["user_prompt"] = system, user
                    row["response"] = provider.chat(system, user, temperature, max_tokens)
            except Exception as err:  # noqa: BLE001 —— 单题失败不中断整体
                row["error"] = str(err)[:500]
            return row

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_one, job): job for job in jobs}
            n_total = len(jobs)
            for i, fut in enumerate(as_completed(futures), 1):
                rows.append(fut.result())
                if i % 10 == 0 or i == n_total:
                    print(f"[answers] {i}/{n_total}")

    df = pd.concat([existing, pd.DataFrame(rows, columns=RESPONSE_COLUMNS)], ignore_index=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return df


def run_grading(
    questions: list[Question],
    responses: pd.DataFrame,
    judge_cfg: dict,
    output_dir: Path,
    max_workers: int = 4,
    kp_weight: float = 0.5,
    resume: bool = True,
    numeric_tol: float = 0.05,
) -> pd.DataFrame:
    """阶段二:对每条回答评分(LLM rubric + 数值容差校验),输出 grades.csv。"""
    out_path = output_dir / "grades.csv"
    existing = _load_existing(out_path, empty_columns=[])
    if resume:
        done = _done_keys(existing, ["question_id", "replicate", "grader"])
    else:
        existing = existing.iloc[0:0]
        done = set()

    grader = build_grader(judge_cfg)
    qmap = {q.question_id: q for q in questions}

    merged = responses.copy()
    merged["grader"] = grader.name

    jobs = []
    for _, row in merged.iterrows():
        if str(row.get("error", "")) or not str(row.get("response", "")):
            continue  # 无效回答不评分
        key = (str(row["question_id"]), str(row["replicate"]), str(row["grader"]))
        if key in done:
            continue
        q = qmap.get(str(row["question_id"]))
        if q is None:
            continue
        jobs.append((q, row))

    rows: list[dict] = []
    if jobs:
        def _one(job: tuple[Question, pd.Series]) -> dict:
            q, resp_row = job
            response_text = str(resp_row["response"])
            try:
                gr = grader.grade(q, response_text)
            except Exception as err:  # noqa: BLE001
                gr = GradeResult(question_id=q.question_id, overall="error", rationale=str(err)[:500])
            out = gr.to_row()
            nc = numeric_check(q.ideal_detail, response_text, tol=numeric_tol)
            out.update({
                "replicate": resp_row["replicate"],
                "grader": str(resp_row["grader"]),
                "composite_score": round(gr.composite_score(kp_weight), 4),
                "numeric_expected": nc["expected"],
                "numeric_matched": nc["matched"],
                "numeric_rate": nc["rate"] if nc["rate"] is not None else "",
            })
            return out

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_one, job) for job in jobs]
            n_total = len(jobs)
            for i, fut in enumerate(as_completed(futures), 1):
                rows.append(fut.result())
                if i % 10 == 0 or i == n_total:
                    print(f"[grades] {i}/{n_total}")

    df = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return df
