"""智能体求解模式:工具循环 + 每题独立工作区(仿 BixBench 的 Aviary 脚手架)。

对应 BixBench 的三个工具:
  edit cell    -> run_python(小步执行代码并观察输出,每次全量看到 stdout/stderr)
  list workdir -> list_workdir(递归列出工作区)
  submit answer-> submit_answer(提交完整作答并结束轨迹)
外加 read_file(阅读工作区文件;BixBench 中由 notebook 内代码承担)。

轨迹完整落盘 JSONL,便于复盘(对应 BixBench 的 1220 条轨迹数据)。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .dataset import Question
from .providers import ChatProvider

TOOLS = ["list_workdir", "read_file", "run_python", "submit_answer"]


def stage_workspace(
    workspace: Path,
    question: Question,
    attachments_root: Path | None,
    stage_references: bool,
) -> bool:
    """为单题布置工作区(仿 BixBench 的 capsule 数据分发)。

    attachments_root/<question_id>/** 与 attachments_root/_shared/** 会拷入工作区;
    stage_references 时把参考文献写入 references.txt。
    返回工作区是否有资料可供探索。
    """
    workspace.mkdir(parents=True, exist_ok=True)
    staged = False
    if attachments_root and attachments_root.exists():
        for src in (attachments_root / "_shared", attachments_root / question.question_id):
            if src.exists():
                shutil.copytree(src, workspace, dirs_exist_ok=True)
                staged = True
    if stage_references and question.references:
        (workspace / "references.txt").write_text(
            "\n\n".join(question.references), encoding="utf-8"
        )
        staged = True
    return staged

_TOOL_CALL_RE = re.compile(r"(list_workdir|read_file|run_python|submit_answer)\s*(\{)", re.S)
_MAX_OBS_CHARS = 4000
_MAX_FILE_CHARS = 8000


@dataclass
class AgentResult:
    answer: str = ""
    error: str = ""
    n_steps: int = 0
    trajectory: list[dict] = field(default_factory=list)


def _parse_tool_call(text: str) -> tuple[str, dict] | None:
    """从模型输出中抽取第一个工具调用(容忍前后噪声,JSON 按括号配平截取)。"""
    m = _TOOL_CALL_RE.search(text)
    if not m:
        return None
    name, start = m.group(1), m.end(1)
    brace = text.find("{", start)
    if brace == -1:
        return name, {}
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                raw = text[brace : i + 1]
                try:
                    return name, json.loads(raw)
                except json.JSONDecodeError:
                    return name, {}
    return name, {}


def _list_workdir(workspace: Path) -> str:
    lines = []
    for p in sorted(workspace.rglob("*")):
        rel = p.relative_to(workspace)
        if p.is_dir():
            lines.append(f"[dir]  {rel}/")
        else:
            lines.append(f"[file] {rel}  ({p.stat().st_size} B)")
    return "\n".join(lines) or "(工作区为空)"


def _read_file(workspace: Path, args: dict) -> str:
    rel = str(args.get("path", "")).strip().lstrip("/\\")
    root = workspace.resolve()
    target = (workspace / rel).resolve() if rel else root
    try:
        target.relative_to(root)
    except ValueError:
        return "[错误] 拒绝读取工作区之外的路径"
    if not target.exists():
        return f"[错误] 文件不存在: {rel}(可用 list_workdir 查看)"
    if target.is_dir():
        return f"[错误] 这是一个目录: {rel}"
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        return f"[错误] 读取失败: {err}"
    if len(content) > _MAX_FILE_CHARS:
        content = content[:_MAX_FILE_CHARS] + f"\n...(截断,共 {len(content)} 字符)"
    return content or "(空文件)"


def _run_python(workspace: Path, args: dict, timeout: int) -> str:
    code = str(args.get("code", ""))
    if not code.strip():
        return "[错误] run_python 需要非空 code"
    script = workspace / "_agent_tmp_script.py"
    script.write_text(code, encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(script.name)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr.strip() else "")
        suffix = f"\n[exit={proc.returncode}]"
    except subprocess.TimeoutExpired:
        out, suffix = "", f"\n[错误] 执行超时(>{timeout}s),请缩小计算规模"
    finally:
        script.unlink(missing_ok=True)
    if len(out) > _MAX_OBS_CHARS:
        out = out[:_MAX_OBS_CHARS] + "\n...(输出截断)"
    return (out + suffix).strip() or "(无输出)"


def run_agent(
    provider: ChatProvider,
    question: Question,
    workspace: Path,
    max_steps: int = 30,
    exec_timeout: int = 60,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    references_hint: bool = False,
) -> AgentResult:
    """执行一条智能体轨迹,返回最终作答与完整轨迹。"""
    from .prompts import agent_system_prompt, agent_turn_prompt

    workspace.mkdir(parents=True, exist_ok=True)
    system = agent_system_prompt(references_hint)
    history = agent_turn_prompt(question, step=1)
    result = AgentResult()
    parse_fails = 0

    for step in range(1, max_steps + 1):
        result.n_steps = step
        raw = provider.chat(system, history, temperature, max_tokens)
        call = _parse_tool_call(raw)
        if call is None:
            parse_fails += 1
            if parse_fails >= 3:
                result.error = f"agent 连续 {parse_fails} 轮未输出合法工具调用"
                break
            history += f"\n\n[格式错误] 请只输出一行工具调用,格式见系统说明(第 {step} 步)。"
            continue
        parse_fails = 0
        name, args = call

        if name == "submit_answer":
            answer = str(args.get("answer", "")).strip()
            result.answer = answer
            result.trajectory.append({
                "step": step, "tool": name, "args": {"answer_len": len(answer)},
                "observation": "submitted", "ts": time.time(),
            })
            if not answer:
                result.error = "submit_answer 内容为空"
            return result

        if name == "list_workdir":
            obs = _list_workdir(workspace)
        elif name == "read_file":
            obs = _read_file(workspace, args)
        elif name == "run_python":
            obs = _run_python(workspace, args, exec_timeout)
        else:  # pragma: no cover —— 正则已限定四个工具名
            obs = f"[错误] 未知工具 {name}"

        result.trajectory.append({
            "step": step, "tool": name, "args": args, "observation": obs[:2000], "ts": time.time(),
        })
        history = agent_turn_prompt(question, step=step + 1) + f"\n\n<上一步观察({name})>\n{obs}\n</上一步观察>\n请输出下一个工具调用。"

    if not result.error:
        result.error = f"agent 达到最大步数({max_steps})仍未提交答案"
    return result


def save_trajectory(path: Path, result: AgentResult, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in result.trajectory:
            f.write(json.dumps({**meta, **entry}, ensure_ascii=False) + "\n")
