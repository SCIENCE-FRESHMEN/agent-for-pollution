# -*- coding: utf-8 -*-
"""Task 4: 跨语言 Query 重写器 (Cross-Lingual Query Rewriter)
将中文/英文查询扩展为覆盖 中/英/日/德/法/西 语言等价术语的布尔检索式。

用法:
    from cross_lingual_rewriter import CrossLingualQueryRewriter
    rw = CrossLingualQueryRewriter()          # 纯词典模式（离线可用）
    rw = CrossLingualQueryRewriter(use_llm=True)  # 附加 LLM 同义扩展（需 OPENAI_API_KEY）
    qs = rw.rewrite("高盐废水中四氢嘧啶的投加量")
    weighted = rw.rewrite_weighted("高盐废水中四氢嘧啶的投加量")
"""
from __future__ import annotations
import os
import re
from collections import OrderedDict

# ---------------------------------------------------------------- dictionaries
# 1) 核心概念 "相容性溶质" 的全语言等价术语（含拼写变体）
CORE_TERMS = {
    "zh": ["相容性溶质", "相容溶质", "兼容性溶质", "兼容溶质"],
    "zh-jp-gloss": ["相溶性溶质", "相容性溶質", "相溶性溶質", "親和性溶質", "適合性の溶質"],
    "en": ["compatible solute", "compatible solutes", "osmoprotectant", "osmolyte",
           "compatible osmolyte"],
    "ja": ["相溶性溶質", "適合溶質", "互換性溶質"],
    "de": ["kompatible Solute", "kompatiblen Soluten", "kompatibles Solut"],
    "fr": ["solutés compatibles", "soluté compatible"],
    "es": ["solutos compatibles", "soluto compatible"],
}

# 2) 具体溶质种类的跨语言变体（canonical -> 变体列表）
SOLUTE_SYNONYMS = OrderedDict([
    ("Ectoine", ["ectoine", "ectoin", "四氢嘧啶", "依克多因", "四氢甲基嘧啶羧酸",
                 "1,4,5,6-tetrahydro-2-methyl-4-pyrimidinecarboxylic acid", "エクトイン",
                 "tetrahydropyrimidine", "THP"]),
    ("Hydroxyectoine", ["hydroxyectoine", "hydroxyectoin", "羟基四氢嘧啶",
                        "5-hydroxyectoine", "ヒドロキシエクトイン"]),
    ("Glycine Betaine", ["glycine betaine", "glycinebetaine", "甘氨酸甜菜碱", "甜菜碱",
                         "betaine", "trimethylglycine", "トリメチルグリシン", "グリシンベタイン"]),
    ("Trehalose", ["trehalose", "海藻糖", "トレハロース"]),
    ("Proline", ["proline", "脯氨酸", "プロリン", "Prolin"]),
    ("Mannosylglycerate", ["mannosylglycerate", "mannosyl glycerate", "firoin",
                           "甘露糖基甘油酸", "甘露糖基甘油酸酯", "MG"]),
    ("Glucosylglycerol", ["glucosylglycerol", "glucosyl glycerol", "glucosylglycerate",
                          "葡萄糖基甘油", "GG"]),
    ("cDPG", ["cyclic 2,3-diphosphoglycerate", "cyclic diglycerophosphate", "cDPG",
              "环状二磷酸甘油酸", "环状2,3-二磷酸甘油酸"]),
    ("Glycerol", ["glycerol", "甘油", "グリセロール", "Glycerin"]),
])

# 3) 常见应用场景的跨语言扩展（用于第二路检索式）
SCENARIO_SYNONYMS = OrderedDict([
    ("wastewater", ["wastewater", "sewage", "废水", "污水", "水处理", "排水",
                    "Abwasser", "eaux usées", "aguas residuales", "排水処理"]),
    ("denitrification", ["denitrification", "denitrifying", "脱氮", "反硝化", "硝化",
                         "Denitrifikation", "dénitrification", "desnitrificación"]),
    ("anammox", ["anammox", "厌氧氨氧化", "厌氧氨氧化菌", "Anaerammonium Oxidation"]),
    ("high salinity", ["high salinity", "high-salt", "saline", "高盐", "盐度", "嗜盐",
                       "Salinität", "salinité", "salinidad"]),
    ("cosmetics", ["cosmetic", "skin care", "化妆品", "护肤", "皮肤", " Kosmetik",
                   "cosmétique", "cosmético"]),
    ("lyophilization", ["lyophilization", "freeze-drying", "冻干", "冷冻干燥", "保存",
                        "Gefriertrocknung", "lyophilisation", "liofilización"]),
    ("fermentation production", ["fermentation", "fermentative production", "发酵生产",
                                 "菌株", "工程菌", "Fermentation", "fermentation"]),
])

ZH_DETECT = re.compile(r"[\u4e00-\u9fff]")
JA_KANA = re.compile(r"[\u3040-\u30ff]")

# 权重策略: 核心概念 1.0 > 命中溶质变体式 0.9 > 场景扩展式 0.7 > LLM 增补式 0.5
W_CORE, W_SOLUTE, W_SCEN, W_LLM = 1.0, 0.9, 0.7, 0.5


class CrossLingualQueryRewriter:
    """词典驱动的多语言布尔检索式重写器；可选 LLM 增补。"""

    def __init__(self, use_llm: bool = False, llm_model: str | None = None):
        self.use_llm = use_llm and bool(os.environ.get("OPENAI_API_KEY"))
        self.llm_model = llm_model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._extra_terms: list[str] = []

    # ------------------------------------------------------------- detection
    @staticmethod
    def _detect_core(query: str) -> bool:
        q = query.lower()
        zh = bool(ZH_DETECT.search(query))
        kana = bool(JA_KANA.search(query))
        en = any(t in q for t in ("compatible solute", "osmoprotectant", "osmolyte"))
        if zh:  # 中文查询中即使未出现核心词，也通过溶质词触发核心扩展
            return True
        return bool(en or kana or zh)

    def _detect_solutes(self, query: str) -> list[str]:
        q = query.lower()
        hits = []
        for canon, variants in SOLUTE_SYNONYMS.items():
            for v in variants:
                if v.lower() in q:
                    hits.append(canon)
                    break
        return hits

    def _detect_scenarios(self, query: str) -> list[str]:
        q = query.lower()
        hits = []
        for canon, variants in SCENARIO_SYNONYMS.items():
            for v in variants:
                if v.lower() in q:
                    hits.append(canon)
                    break
        return hits

    # ------------------------------------------------------------- builders
    @staticmethod
    def _or_group(terms: list[str]) -> str:
        seen, out = set(), []
        for t in terms:
            k = t.lower()
            if k not in seen:
                seen.add(k)
                out.append(f'"{t}"')
        return "(" + " OR ".join(out) + ")"

    def _core_query(self) -> str:
        all_core = [t for group in CORE_TERMS.values() for t in group]
        return self._or_group(all_core)

    def _solute_query(self, canon: str) -> str:
        return self._or_group(SOLUTE_SYNONYMS[canon])

    def _scenario_query(self, canon: str) -> str:
        return self._or_group(SCENARIO_SYNONYMS[canon])

    # ------------------------------------------------------------- LLM extras
    def _llm_expand(self, query: str) -> list[str]:
        try:
            from openai import OpenAI
            client = OpenAI()
            resp = client.chat.completions.create(
                model=self.llm_model,
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system",
                     "content": "给出与查询等价的检索关键词扩展（中/英/日/德/法/西），"
                                "只输出JSON：{\"terms\":[...]}，最多10个，禁止解释。"},
                    {"role": "user", "content": query}],
            )
            import json
            return [str(t) for t in json.loads(resp.choices[0].message.content or "{}").get("terms", [])][:10]
        except Exception:
            return []

    # ------------------------------------------------------------- public API
    def rewrite(self, query: str) -> list[str]:
        """返回去重后的布尔检索式列表（核心式在前）。"""
        weighted = self.rewrite_weighted(query)
        seen, out = set(), []
        for q, _ in weighted:
            if q not in seen:
                seen.add(q)
                out.append(q)
        return out

    def rewrite_weighted(self, query: str) -> list[tuple[str, float]]:
        """返回 (布尔检索式, 权重) 列表，按权重降序。"""
        results: list[tuple[str, float]] = []
        core = self._detect_core(query)
        if core:
            results.append((self._core_query(), W_CORE))
        for canon in self._detect_solutes(query):
            results.append((self._solute_query(canon), W_SOLUTE))
        for canon in self._detect_scenarios(query):
            results.append((self._scenario_query(canon), W_SCEN))
        # 组合式: 核心 AND 溶质（若两者均命中）
        if core and self._detect_solutes(query):
            combo = self._core_query() + " AND " + self._solute_query(self._detect_solutes(query)[0])
            results.append((combo, min(1.0, W_CORE + 0.3 * W_SOLUTE)))
        if self.use_llm:
            for t in self._llm_expand(query):
                results.append((f'"{t}"', W_LLM))
        seen, out = set(), []
        for q, w in sorted(results, key=lambda x: -x[1]):
            if q in seen:
                continue
            seen.add(q)
            out.append((q, round(w, 2)))
        return out


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    rw = CrossLingualQueryRewriter(use_llm=False)
    for q in ["高盐废水中四氢嘧啶的投加量",
              "anammox系统甜菜碱恢复铁抑制",
              "依克多因发酵生产菌株"]:
        print("=" * 70)
        print("QUERY:", q)
        for qq, w in rw.rewrite_weighted(q):
            print(f"  [{w:.2f}] {qq}")
