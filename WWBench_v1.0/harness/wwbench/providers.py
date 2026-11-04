"""LLM 后端:OpenAI 兼容接口(适用于 OpenAI/GLM/DeepSeek/Qwen 等)与离线 mock。

mock 后端用于无 API key 的冒烟测试:确定性地产出"部分正确"的回答,
让整条评测流水线(含拒答分支)可以离线跑通。
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Protocol

DEFAULT_MAX_TOKENS = 4096

_STEP_RE = re.compile(r"<step>\s*(\d+)\s*</step>")


class ChatProvider(Protocol):
    name: str

    def chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        ...


class OpenAICompatProvider:
    """任何 OpenAI 兼容 /chat/completions 端点。"""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        retries: int = 3,
        retry_wait: float = 2.0,
    ):
        from openai import OpenAI

        if not api_key:
            raise ValueError("openai provider 需要 api_key(或环境变量)")
        self.name = f"openai:{model}"
        self.model = model
        self.retries = retries
        self.retry_wait = retry_wait
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content or ""
            except Exception as err:  # noqa: BLE001 —— 网络/限流等各类错误统一重试
                last_err = err
                time.sleep(self.retry_wait * (2**attempt))
        raise RuntimeError(f"{self.name} 调用失败(已重试 {self.retries} 次): {last_err}")


class MockProvider:
    """离线确定性后端:按 question_id 哈希决定答对哪些要点,小概率触发拒答。"""

    def __init__(self, correct_ratio: float = 0.6, refusal_rate: float = 0.125):
        self.name = "mock"
        self.correct_ratio = correct_ratio
        self.refusal_rate = refusal_rate

    def _seed(self, key: str) -> int:
        return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)

    def chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        step = _STEP_RE.search(user)
        if step:
            if int(step.group(1)) == 1:
                return "list_workdir {}"
            return ("submit_answer " + json.dumps(
                {"answer": "（1）建议梯度驯化提升盐度;（2）投加相容性溶质缓解渗透冲击;"
                           "（3）引入耐盐功能菌强化。具体参数需结合进水水质确定。"},
                ensure_ascii=False,
            ))
        qid = _question_id_of(user)
        seed = self._seed(qid + f"|t={temperature}")

        if (seed % 1000) / 1000 < self.refusal_rate:
            return "根据现有信息不足,无法回答该问题,建议补充进水水质与菌群丰度数据后再判断。"

        # 从题目要求中抽取作答骨架(不访问标准答案,保持"模型"语义)
        steps = [s.strip() for s in user.split("（") if s.strip()]
        take = max(1, int(len(steps) * self.correct_ratio))
        body = "\n".join(f"（{i+1}）{s[:180]}" for i, s in enumerate(steps[:take]))
        return f"以下按步骤作答:\n{body}\n综上,建议采用梯度驯化结合相容性溶质强化路线。"


def _question_id_of(user: str) -> str:
    marker = "<question_id>"
    if marker in user:
        return user.split(marker)[1].split("</question_id>")[0].strip()
    return user[:64]


class OracleProvider:
    """回放标准答案的"满分模型",用于校准评分体系上界与流水线验证。

    degrade:按要点丢弃比例人为劣化答案,可生成"部分正确"的受控样本。
    """

    def __init__(self, answers: dict[str, str] | None = None, degrade: float = 0.0):
        self.name = "oracle"
        self.answers = answers or {}
        self.degrade = degrade

    def _degrade(self, text: str) -> str:
        if self.degrade <= 0:
            return text
        # 同时按分号与句号切分:v1 批次答案以分号连接,v2 批次以句号连接
        parts = [p.strip() for p in re.split(r"[；;。]", text) if p.strip()]
        keep = max(1, round(len(parts) * (1 - self.degrade)))
        return "。".join(parts[:keep])

    def chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        # 智能体模式:按步走脚本化协议(第 1 步看工作区,之后直接提交)
        step = _STEP_RE.search(user)
        if step:
            if int(step.group(1)) == 1:
                return "list_workdir {}"
            answer = self._degrade(self.answers.get(_question_id_of(user), "(该题无参考答案)"))
            return "submit_answer " + json.dumps({"answer": answer}, ensure_ascii=False)
        qid = _question_id_of(user)
        text = self._degrade(self.answers.get(qid, "(该题无参考答案)"))
        return text


def build_provider(cfg: dict, questions=None) -> ChatProvider:
    """从配置字典构造 provider:solver 与 judge 各一份。"""
    cfg = dict(cfg or {})
    kind = cfg.pop("provider", "mock")
    cfg.pop("agent", None)  # agent 行为参数由 runner 使用,不传给 provider

    if kind == "mock":
        return MockProvider(**cfg)
    if kind == "oracle":
        answers = {q.question_id: q.ideal_detail for q in (questions or [])}
        return OracleProvider(answers=answers, degrade=cfg.get("degrade", 0.0))
    if kind == "openai":
        import os

        api_key = cfg.pop("api_key", None) or os.environ.get(cfg.pop("api_key_env", "OPENAI_API_KEY"))
        base_url = cfg.pop("base_url", None) or os.environ.get("OPENAI_BASE_URL") or None
        return OpenAICompatProvider(model=cfg.pop("model"), api_key=api_key, base_url=base_url, **cfg)
    raise ValueError(f"未知 provider: {kind}(可选 mock / oracle / openai)")
