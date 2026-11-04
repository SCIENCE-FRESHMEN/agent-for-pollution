"""评分器:rubric_6dims(judge LLM)与 keypoint_overlap(离线启发式)。

对应 BixBench graders.py 的双轨设计:
- _grade_llm_verifier -> RubricLLMGrader(六维 + 要点命中 + 二值判定)
- _grade_str_verifier -> HeuristicGrader(词汇覆盖,无需 API,用于冒烟与交叉校验)
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

from .dataset import Question, REFUSAL_PATTERNS
from .prompts import DEFAULT_RUBRIC_DIMS, build_judge_prompt
from .providers import ChatProvider, build_provider

DIM_NAMES = list(DEFAULT_RUBRIC_DIMS)
MAX_DIM_SCORE = 2 * len(DIM_NAMES)  # 每维 0-2 分


@dataclass
class GradeResult:
    question_id: str
    keypoint_hits: list[bool] = field(default_factory=list)
    dim_scores: dict[str, int] = field(default_factory=dict)
    refused: bool = False
    overall: str = "incorrect"  # correct / incorrect / refused / error
    rationale: str = ""

    @property
    def keypoint_coverage(self) -> float:
        return sum(self.keypoint_hits) / len(self.keypoint_hits) if self.keypoint_hits else 0.0

    @property
    def dim_total(self) -> int:
        return sum(self.dim_scores.values())

    @property
    def dim_norm(self) -> float:
        return self.dim_total / MAX_DIM_SCORE if MAX_DIM_SCORE else 0.0

    def composite_score(self, kp_weight: float = 0.5) -> float:
        """综合分 = kp_weight*要点覆盖率 + (1-kp_weight)*六维归一化分;拒答记 0。"""
        if self.refused:
            return 0.0
        return kp_weight * self.keypoint_coverage + (1 - kp_weight) * self.dim_norm

    def is_correct(self, pass_threshold: float) -> bool:
        return (not self.refused) and self.composite_score() >= pass_threshold

    def to_row(self) -> dict:
        row = {
            "question_id": self.question_id,
            "n_keypoints": len(self.keypoint_hits),
            "n_keypoint_hits": sum(self.keypoint_hits),
            "keypoint_coverage": round(self.keypoint_coverage, 4),
            "dim_total": self.dim_total,
            "dim_norm": round(self.dim_norm, 4),
            "refused": self.refused,
            "overall": self.overall,
            "rationale": self.rationale,
        }
        for dim in DIM_NAMES:
            row[f"dim_{dim}"] = self.dim_scores.get(dim, -1)
        return row


def _extract_json(text: str) -> dict:
    """从 judge 输出中鲁棒抽取 JSON 对象(容忍代码块围栏与前后噪声)。"""
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"judge 输出中未找到 JSON: {text[:200]}")
    return json.loads(text[start : end + 1])


class RubricLLMGrader:
    """judge LLM 按 rubric_6dims 评分。"""

    def __init__(self, provider: ChatProvider, dims: dict[str, str] | None = None,
                 temperature: float = 0.0, max_tokens: int = 2048):
        self.provider = provider
        self.name = f"rubric_6dims:{provider.name}"
        self.dims = dims or DEFAULT_RUBRIC_DIMS
        self.temperature = temperature
        self.max_tokens = max_tokens

    def grade(self, question: Question, response: str) -> GradeResult:
        system, user = build_judge_prompt(question, response, self.dims)
        raw = self.provider.chat(system, user, self.temperature, self.max_tokens)
        data = _extract_json(raw)
        return self._parse(question, data, response)

    @staticmethod
    def _parse(question: Question, data: dict, response: str) -> GradeResult:
        def as_bool(value) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            return str(value).strip().lower() in {"true", "1", "yes", "y"}

        n = question.num_keypoints
        raw_hits = data.get("keypoint_hits", [])
        if not isinstance(raw_hits, list):
            raw_hits = []
        hits = [as_bool(h) for h in raw_hits][:n]
        hits += [False] * (n - len(hits))  # 缺失的要点按未命中补齐

        dims = {}
        raw_dims = data.get("dim_scores", {})
        if not isinstance(raw_dims, dict):
            raw_dims = {}
        for dim in DIM_NAMES:
            try:
                dims[dim] = max(0, min(2, int(raw_dims.get(dim, 0))))
            except (TypeError, ValueError):
                dims[dim] = 0

        refused = as_bool(data.get("refused", False)) or bool(REFUSAL_PATTERNS.search(response or ""))
        overall = str(data.get("overall", "incorrect")).strip().lower()
        if overall not in {"correct", "incorrect", "refused", "error"}:
            overall = "incorrect"
        if refused:
            overall = "refused"

        return GradeResult(
            question_id=question.question_id,
            keypoint_hits=hits,
            dim_scores=dims,
            refused=refused,
            overall=overall,
            rationale=str(data.get("rationale", ""))[:500],
        )


class HeuristicGrader:
    """离线启发式评分:要点按词汇覆盖率判定命中,六维由覆盖率映射。"""

    def __init__(self, token_hit_ratio: float = 0.4):
        self.token_hit_ratio = token_hit_ratio
        self.name = "heuristic"

    # 引证锚点:DOI / 期刊缩写(或名)+年份(如 "ES&T 2022" "Biodegradation 2012")
    # / et al. / 书名号教科书来源。只作为"可追溯依据"的标记,不作内容真伪判断。
    _CITE_RE = re.compile(
        r"10\.\d{4,9}/\S+"
        r"|[A-Za-z][A-Za-z&.\-]*\s+(?:19|20)\d{2}\b"
        r"|\bet\s+al\.?"
        r"|《[^》]{2,40}》"
    )

    def _evidence_dim(self, question: Question, response: str, coverage: float) -> int:
        """依据支撑维(v1.0.1 修复):以参考答案中的引证标记集合为锚点,检验作答
        是否给出同样的可追溯依据。

        v1.0 缺陷:统一用 coverage*1.2 映射,oracle 覆盖率 0.9842×1.2=1.18→四舍
        五入恒为 1 分(归一 0.5),全队列无区分度。现改为:参考答案含引证锚点时,
        按"作答命中锚点比例"打分(oracle→2,半分档→1,mock→0);参考答案本身
        无引证锚点时,退化为与准确性同权的覆盖率映射(2.0),不再产生常数中间值。
        """
        ref_cites = {m.group(0).strip().lower()
                     for m in self._CITE_RE.finditer(question.ideal_detail or "")}
        if not ref_cites:
            return max(0, min(2, round(coverage * 2.0)))
        resp_text = (response or "").lower()
        matched = sum(1 for c in ref_cites if c in resp_text)
        ratio = matched / len(ref_cites)
        if ratio >= 0.6:
            return 2
        if ratio >= 0.25:
            return 1
        return 0

    def _tokens(self, text: str) -> list[str]:
        """英文/数字取整词,中文取字符二元组——对中文改写稳健(整段连续中文
        若按最大匹配切分会得到超长 token,意译即 miss)。"""
        toks: list[str] = []
        for m in re.finditer(r"[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*", text or ""):
            if len(m.group()) >= 2:
                toks.append(m.group().lower())
        for m in re.finditer(r"[\u4e00-\u9fff]+", text or ""):
            seg = m.group()
            if len(seg) == 1:
                toks.append(seg)
            for i in range(len(seg) - 1):
                toks.append(seg[i : i + 2])
        return toks

    def grade(self, question: Question, response: str) -> GradeResult:
        resp_tokens = set(self._tokens(response))
        hits: list[bool] = []
        for kp in question.keypoints:
            kp_tokens = [t for t in self._tokens(kp) if len(t) >= 2]
            if not kp_tokens:
                hits.append(False)
                continue
            found = sum(1 for t in kp_tokens if t in resp_tokens)
            hits.append(found / len(kp_tokens) >= self.token_hit_ratio)

        coverage = sum(hits) / len(hits) if hits else 0.0
        refused = bool(REFUSAL_PATTERNS.search(response or ""))
        # 覆盖率映射到各维:不同维度用不同敏感度,避免六维完全同值
        def scaled(mult: float) -> int:
            return max(0, min(2, round(coverage * mult)))

        dims = {
            "accuracy": scaled(2.0),
            "completeness": scaled(2.0),
            "mechanism": scaled(1.5),
            "feasibility": scaled(1.6),
            "evidence": self._evidence_dim(question, response, coverage),
            "rigor": scaled(1.5),
        }
        return GradeResult(
            question_id=question.question_id,
            keypoint_hits=hits,
            dim_scores=dims,
            refused=refused,
            overall="refused" if refused else ("correct" if coverage >= 0.5 else "incorrect"),
            rationale=f"[heuristic] 要点词汇覆盖率={coverage:.2f}",
        )


# ---------- 数值容差校验(仿 BixBench 的 range/str verifier 双轨设计) ----------

_NUM_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_LIST_NUMBER_RE = re.compile(r"(?:\(\s*\d+\s*\)|（\s*\d+\s*）|(?<![\d.])\d+\.(?!\d)|(?<!\d)\d+\))")


def _numeric_values(text: str) -> list[float]:
    """Extract numeric values while ignoring ordinary list numbering."""
    cleaned = _LIST_NUMBER_RE.sub(" ", text or "")
    values = []
    for match in _NUM_RE.finditer(cleaned):
        value = float(match.group())
        if abs(value) < 1e12:
            values.append(value)
    return values


def numeric_check(ideal: str, response: str, tol: float = 0.05) -> dict:
    """从参考答案抽取全部数值,检验作答中是否给出等值(相对容差内)数字。

    对"共 8 步、约 56 天、NRR≥90%、COD/TN<1"这类硬性数值给出客观的机器校验,
    不依赖 judge LLM 的数值判断(BixBench 论文用 range-verifier 达到同一目的)。
    无数值的题返回 rate=None,不计入均值。
    """
    expected = sorted({round(value, 4) for value in _numeric_values(ideal)})
    if not expected:
        return {"expected": 0, "matched": 0, "rate": None}
    found = _numeric_values(response)
    adjacency = [
        [i for i, found_value in enumerate(found)
         if abs(found_value - expected_value) <= tol * max(1.0, abs(expected_value))]
        for expected_value in expected
    ]
    # Maximum-cardinality bipartite matching prevents one response number from
    # satisfying multiple expectations and avoids greedy-order artefacts.
    matched_found = [-1] * len(found)

    def augment(expected_index: int, seen: set[int]) -> bool:
        for found_index in adjacency[expected_index]:
            if found_index in seen:
                continue
            seen.add(found_index)
            previous = matched_found[found_index]
            if previous == -1 or augment(previous, seen):
                matched_found[found_index] = expected_index
                return True
        return False

    matched = sum(augment(index, set()) for index in range(len(expected)))
    return {"expected": len(expected), "matched": matched, "rate": round(matched / len(expected), 4)}


# ---------- A/D 型题客观校验器(v1.1 新增:基因组缺陷谱 / 供体菌排序) ----------

_FDP_STATE = {
    "present": {"present", "有", "齐全", "完整", "存在", "yes", "true", "1"},
    "partial": {"partial", "不完整", "部分", "残缺", "仅部分"},
    "missing": {"missing", "缺失", "无", "没有", "absent", "no", "false", "0"},
}


def _normalize_fdp_state(value) -> str:
    text = str(value).strip().lower()
    for state, aliases in _FDP_STATE.items():
        if text in aliases:
            return state
    return "unknown"


def parse_fdp_json(response: str) -> dict | None:
    """从作答中抽取功能缺陷谱 JSON(形如 {"ectoine_synthesis": "missing", ...})。

    扫描全部花括号块并从后往前尝试解析,取第一个可解析且值为可识别状态的字典;
    找不到则返回 None(判为全错,不静默给分)。
    """
    candidates = []
    for start in (m.start() for m in re.finditer(r"\{", response or "")):
        depth = 0
        for i in range(start, len(response)):
            if response[i] == "{":
                depth += 1
            elif response[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(response[start : i + 1])
                    break
    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data:
            return data
    return None


def fdp_check(gold: dict[str, str], response: str) -> dict:
    """基因组功能缺陷谱客观校验:逐模块比对 状态(present/partial/missing)。

    gold 来自可信注释管线(金标准),作答经 parse_fdp_json 抽取;不依赖 judge LLM。
    无 JSON 时返回 accuracy=0 并置 parse_ok=False,杜绝"格式错即静默得分"。
    """
    predicted_raw = parse_fdp_json(response)
    if predicted_raw is None:
        return {"parse_ok": False, "expected": len(gold), "matched": 0,
                "accuracy": 0.0, "strict_match": False, "detail": {}}
    detail, matched = {}, 0
    for module, gold_state in gold.items():
        gold_norm = _normalize_fdp_state(gold_state)
        pred_norm = _normalize_fdp_state(predicted_raw.get(module, "unknown"))
        ok = gold_norm != "unknown" and pred_norm == gold_norm
        matched += ok
        detail[module] = {"gold": gold_norm, "predicted": pred_norm, "ok": ok}
    return {"parse_ok": True, "expected": len(gold), "matched": matched,
            "accuracy": round(matched / len(gold), 4) if gold else 0.0,
            "strict_match": matched == len(gold) and gold != {},
            "detail": detail}


def rank_check(gold_rank: list[str], response_rank: list[str], k: int | None = None) -> dict:
    """供体菌推荐排序校验:NDCG@k(gold 排位为 relevance,第一名义 1.0)+ 逐对一致率。

    gold_rank 为金标准从优到劣的候选序列;response_rank 为作答排序。作答中未出现
    的 gold 候选 gain=0;gold 之外的候选不参与计算。k 缺省取 len(gold_rank)。
    """
    gold_rank = [str(g).strip() for g in gold_rank if str(g).strip()]
    response_rank = [str(r).strip() for r in response_rank if str(r).strip()]
    if not gold_rank:
        return {"ndcg": None, "pairwise_concordance": None, "hit_at_1": None}
    k = k or len(gold_rank)
    gain = {name: 1.0 / (i + 1) for i, name in enumerate(gold_rank)}  # 排位折扣增益
    dcg = sum(gain[name] / math.log2(i + 2)
              for i, name in enumerate(response_rank[:k]) if name in gain)
    idcg = sum((1.0 / (i + 1)) / math.log2(i + 2) for i in range(min(k, len(gold_rank))))
    ndcg = round(dcg / idcg, 4) if idcg else 0.0

    pairs = [(a, b) for i, a in enumerate(gold_rank) for b in gold_rank[i + 1:]]
    pos = {name: i for i, name in enumerate(response_rank)}
    concordant = sum(1 for a, b in pairs
                     if a in pos and b in pos and pos[a] < pos[b])
    comparable = sum(1 for a, b in pairs if a in pos and b in pos)
    return {
        "ndcg": ndcg,
        "pairwise_concordance": round(concordant / comparable, 4) if comparable else None,
        "hit_at_1": response_rank[:1] == gold_rank[:1],
    }


# judge 配置中属于"连接参数"的键(交给 provider),其余属于"评分参数"
_PROVIDER_KEYS = {"model", "api_key", "api_key_env", "base_url", "retries", "retry_wait"}


def build_grader(cfg: dict) -> RubricLLMGrader | HeuristicGrader:
    cfg = dict(cfg or {})
    kind = cfg.pop("provider", "heuristic")
    if kind == "heuristic":
        return HeuristicGrader(token_hit_ratio=cfg.get("token_hit_ratio", 0.4))
    if kind == "openai":
        prov_cfg = {k: v for k, v in cfg.items() if k in _PROVIDER_KEYS}
        provider = build_provider({**prov_cfg, "provider": "openai"})
        return RubricLLMGrader(
            provider=provider,
            temperature=cfg.get("temperature", 0.0),
            max_tokens=cfg.get("max_tokens", 2048),
            dims=cfg.get("dims"),
        )
    raise ValueError(f"未知 judge provider: {kind}(可选 heuristic / openai)")
