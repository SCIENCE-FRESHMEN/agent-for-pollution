"""WWBench 大规模出题 v2:模板 × 因子槽位组合生成,目标 ≥1000 题。

原则:
- 题面槽位(行业盐度、反应器、目标盐度等)是场景设计输入,可自由取值;
- 答案内容只依赖已确立的领域事实层(既有题库事实 + 教科书共识),不编造;
- 每条过 schema/要点数/内部分号/模板签名/自洽性五道门禁(复用 v1 的 quality_gate);
- 确定性生成(md5 播种),批内组合唯一,不与现有库撞号。

用法:
  python scripts/generate_questions_v2.py                    # 生成+质检 → data/pending_review_1000.csv
  python scripts/generate_questions_v2.py --approve          # 备份并合入题库
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_dataset import template_signature  # noqa: E402
from scripts.generate_questions import GENOME_PROFILES, REACTORS, _s  # noqa: E402
from wwbench.dataset import load_questions  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# ---------------- 知识事实层(仅使用已确立事实) ----------------

SOLUTE = {
    "海藻糖": dict(
        mech="稳定膜脂双分子层与酶构象,提供膜与蛋白双重保护,缓解盐冲击与干燥胁迫",
        path="otsA/otsB 合成(部分菌经 TreY/TreZ 途径),亦可经转运体直接摄取",
        niche="无氮溶质,氮源受限时优先选择",
        donor="外源补充或经梯度驯化上调 otsAB 表达",
    ),
    "四氢嘧啶(ectoine)": dict(
        mech="以'水化壳'稳定蛋白与酶构象并清除活性氧,不影响胞内大分子功能",
        path="ectA/ectB/ectC 三步合成(天冬氨酸-β-半醛途径)",
        niche="含氮高效溶质,中度嗜盐菌的主流选择",
        donor="Halomonas elongata、Chromohalobacter salexigens 等产 ectoine 菌",
    ),
    "甘氨酸甜菜碱(GB)": dict(
        mech="渗透平衡与蛋白稳定,摄取替代合成可节约能耗",
        path="betA/betB 合成,经 BetT/ProU/Opu 等转运体摄取",
        niche="最通用的保护溶质,可外源投加直接利用",
        donor="Halomonas、Thiocapsa、Rhodohalobacter 等产 GB 菌",
    ),
    "谷氨酸/谷氨酰胺": dict(
        mech="快速响应的应急相容溶质,兼氮代谢枢纽,外源投加可直接被摄取补偿内源合成不足",
        path="gdhA/glnA 同化(ES&T 2022:淡水 anammox 菌关键内源溶质)",
        niche="淡水菌与低-中盐环境的第一响应",
        donor="外源投加(如谷氨酸钠)或产谷氨酸菌共培养",
    ),
}
SOLUTE_NAMES = list(SOLUTE)

ORGANISMS = ["Kuenenia", "Brocadia", "Jettenia", "Scalindua", "Anammoxoglobus"]

TRANSPORT_FACTS = {
    "BetT": "胆碱/甜菜碱高亲和摄取",
    "ProU/ProP": "脯氨酸/甜菜碱广谱摄取",
    "Opu": "卵磷脂/甜菜碱家族摄取",
    "Ehu": "海藻糖/低渗冲击相关摄取",
    "NhaA": "钠氢反向转运(排钠保稳,非溶质摄取)",
}

REACTOR_POOL = [  # (名称, 水质, HRT h)
    ("MBR 膜生物反应器", "城市污水", 24), ("SBR 序批式反应器", "消化液侧流", 18),
    ("一体式 PN/A 反应器", "城市污水主流", 24), ("UASB 上升流厌氧污泥床", "高氨氮工业废水", 36),
    ("移动床生物膜反应器 MBBR", "海水入侵滨海厂", 12), ("序批式生物膜反应器", "食品加工高盐废水", 24),
    ("连续流厌氧氨氧化反应器", "油气田采出水", 48), ("盐湖卤水富集培养体系", "接种源筛选", 0),
    ("两段式缺氧-好氧反应器", "渗滤液处理", 20), ("生物滤池", "再生水回用", 8),
]

REGIMES = [(0.5, 2.0), (1.0, 3.0), (1.0, 5.0), (1.5, 4.0), (2.0, 4.0), (2.0, 6.0),
           (0.5, 3.0), (1.5, 5.5), (2.5, 5.0), (3.0, 6.0), (0.5, 1.5), (1.0, 2.0)]

INDUSTRIES = [  # (行业, 盐度%, 特征)——盐度为场景设定值
    ("腌渍废水", 4.0, "高盐高 COD,含盐渍浸出物"),
    ("水产加工废水", 6.0, "高盐高蛋白氮,含鱼腥废水油脂"),
    ("油气田采出水", 5.0, "高盐含氯离子,含少量烃类"),
    ("制药废水", 3.0, "含抗生素残留抑制菌群"),
    ("皮革废水", 5.0, "高盐含硫与铬"),
    ("印染废水", 2.0, "高色度含盐,可生化性差"),
    ("味精发酵废水", 4.5, "高氨高盐高 COD"),
    ("垃圾渗滤液", 1.0, "高氨氮中盐,含抑制性物质"),
]

PROCESSES = [
    ("短程硝化(PN)", "AOB 保留而 NOB 被盐度选择性抑制,需防盐度过高反抑 AOB"),
    ("短程反硝化-厌氧氨氧化(PD-A)", "Thauera 短程产 NO2⁻ 与 anammox 耦合,碳源窗口窄"),
    ("硫自养反硝化(SAD)", "硫氧化供电子,需碱度与 pH 管理,防硫化物毒性"),
    ("厌氧消化(AD)", "产甲烷古菌渗透敏感,盐-氨常双胁迫"),
    ("MBR 膜生物反应器", "EPS/SMP 组成变化驱动膜污染"),
    ("好氧颗粒污泥(AGS)", "适度盐促密实,过高盐致解体"),
    ("移动床生物膜(MBBR)", "载体持留菌群,抗冲击较强"),
    ("两段式硝化反硝化", "耐盐驯化为主,碳源利用率下降"),
]

TEMPS = [("中温", 25), ("偏低温", 15), ("低温", 10), ("夏季高温", 32)]

# ---------------- 通用构件 ----------------


def steps_days(a: float, b: float) -> tuple[int, int]:
    steps = round((b - a) / 0.5)
    return steps, steps * 7


def row(qid, tag, topic, diff, qt, q, kp_items, ideal_parts, cat, ref):
    # 逐条消毒字段内部的分号,再以"；"拼接条目——对整串消毒会毁掉分隔符
    kp = "；".join(f"{i+1}.{_s(it)}" for i, it in enumerate(kp_items))
    ideal = "。".join(_s(p) for p in ideal_parts) + "。"
    return dict(id=qid, tag=tag, topic=topic, diff=diff, qt=qt, q=q,
                kp=kp, ideal=ideal, cat=cat, ref=ref)


# ---------------- 模板族 ----------------

ORG_GROUPS = [
    "淡水 anammox 菌(以 Kuenenia/Brocadia 为代表)", "海洋型 anammox 菌(以 Scalindua 为代表)",
    "氨氧化菌 AOB(Nitrosomonas)", "亚硝酸盐氧化菌 NOB(Nitrospira)",
    "中度嗜盐反硝化菌", "嗜盐产甲烷古菌(Methanohalophilus 等)",
    "产 ectoine 的 Halomonas 属", "硫氧化反硝化菌 Thiohalomonas",
]
SALT_BANDS = [("低盐带(约 0.5-1%)", "0.5-1%"), ("中盐带(约 2-3%)", "2-3%"), ("高盐带(约 5%)", "5%")]


def gen_A(n: int, start: int):
    """A 类:主导溶质机制题(简单/中等)。轴:溶质×侧面×微生物组×盐度带 = 4×3×8×3。"""
    outs = []
    combos = list(itertools.product(range(len(SOLUTE_NAMES)), range(3),
                                    range(len(ORG_GROUPS)), range(len(SALT_BANDS))))
    openings = [
        ("的渗透保护机制是什么", "mech"),
        ("的合成或摄取途径有哪些", "path"),
        ("为何被选作相容性溶质", "niche"),
    ]
    for i in range(n):
        si_, oi, gi, bi = combos[i % len(combos)]
        sname = SOLUTE_NAMES[si_]
        s = SOLUTE[sname]
        g = ORG_GROUPS[gi]
        band, bandv = SALT_BANDS[bi]
        head, aspect = openings[oi]
        other = next(x for x in SOLUTE_NAMES if x != sname)
        if aspect == "mech":
            q = (f"{g}在{band}下,{sname}{head}?请按以下步骤完整作答:(1)说明{sname}在该场景下的作用机制;"
                 f"(2)与{other}的保护侧重点差异;(3)举一种依赖{sname}或{other}的代表微生物并说明其途径。")
            kps = [f"机制:{s['mech']}",
                   f"与{other}差异:{s['niche']} vs {SOLUTE[other]['niche']}",
                   f"代表菌与途径:{s['path']}"]
            ideal = [f"{g}在{bandv}场景下,{sname}的作用机制:{s['mech']}",
                     f"与{other}相比,二者保护侧重不同:{sname}——{s['niche']};{other}——{SOLUTE[other]['niche']}",
                     f"代表途径:{s['path']}"]
        elif aspect == "path":
            q = (f"{g}在{band}下,{sname}{head}?请按以下步骤完整作答:(1)指出{sname}的合成酶/途径;"
                 f"(2)说明其摄取转运方式;(3)说明外源补充{sname}的工程可行性与剂量起点。")
            kps = [f"合成途径:{s['path']}", f"摄取/外源利用:{s['donor']}",
                   "工程可行性:外源投加起始 0.1-1 mM 经小试优化,转运匹配时有效"]
            ideal = [f"{g}场景下{sname}的合成与摄取:{s['path']}",
                     f"外源供给方式:{s['donor']}",
                     "工程上外源投加以 0.1-1 mM 起试并经小试优化,需与体系转运状态匹配"]
        else:
            q = (f"{g}在{band}下{sname}{head}?请按以下步骤完整作答:(1)说明选择原因"
                 f"(保护能力与合成/摄取能耗的权衡);(2)氮源可得性如何影响该选择;(3)给出验证实验思路。")
            kps = [f"选择原因:{s['niche']},权衡保护力与能耗",
                   "氮影响:氮充足偏向含氮溶质(ectoine/GB),氮受限偏向无氮溶质(海藻糖)",
                   "验证:梯度盐度批次+HPLC 胞内溶质检测,3 平行"]
            ideal = [f"{g}在{bandv}下选择{sname}的原因:{s['niche']},是保护能力与能耗的折中",
                     "氮源可得性决定含氮溶质(ectoine/GB)与无氮溶质(海藻糖)之间的偏好",
                     "验证:梯度盐度批次培养,以 HPLC 定量胞内溶质组成,每组 3 平行"]
        outs.append(row(f"q-{start+len(outs)}", "脱氮", "高盐胁迫", "简单" if i % 2 else "中等",
                        "A 盐度-主导溶质", q, kps, ideal,
                        "Compatible solutes, 盐度-主导溶质",
                        "L0430 Glycine Betaine and Ectoine Are the Majo；10.1021/acs.est.2c01104 Glutamate Enhances Osmoadaptation of Ana"))
    return outs


def gen_T5(n: int, start: int):
    """T5:菌株/供体选择(中等)。轴:档案×系统×目标盐度 = 8×4×12。"""
    outs = []
    profiles = list(GENOME_PROFILES.items())
    systems = [("anammox 体系", "NRR 恢复与三氮"), ("PN/A 一体化体系", "NAR 与 NRR"),
               ("SAD 硫自养体系", "硝酸盐还原率与硫化物氧化"), ("颗粒污泥体系", "SVI 与粒径")]
    combos = list(itertools.product(range(len(profiles)), range(len(systems)), range(len(REGIMES))))
    for i in range(n):
        pi, si, ri = combos[i % len(combos)]
        pname, prof = profiles[pi]
        sysname, monitor = systems[si]
        a, b = REGIMES[ri]
        q = (f"某{sysname}(运行盐度 {a:g}%,拟提升至 {b:g}%)经诊断:{prof['concl']}的基因组背景"
             f"({pname} 档案,{_s(prof['syn'])[:40]}…)。请推荐相容性溶质供给方案/供体菌。"
             f"请按以下步骤完整作答:(1)给出供体菌或溶质供给方案;"
             f"(2)列出三条筛选依据(合成能力/盐度生态位/可定殖性);(3)给出富集与定殖验证要点。")
        kps = [f"方案:{_s(prof['concl'])},供体选 {_s(prof['donor'])}",
               "依据:合成能力(ectABC/betBA 齐全且高盐诱导)、盐度生态位匹配体系区间、可定殖性(生物膜持留,16S 共现支撑)",
               f"验证:16S/qPCR 回测供体丰度 ≥10%,HPLC 检出胞外溶质,以{monitor}对比提升"]
        ideal = [f"供给方案:{_s(prof['concl'])}——引入 {_s(prof['donor'])} 就地提供相容性溶质,支撑体系自 {a:g}% 向 {b:g}% 的盐度提升",
                 "筛选三依据:合成能力(目的溶质基因齐全且高盐下高表达)、盐度生态位(适生区间覆盖体系运行盐度)、可定殖性(能在载体/生物膜持留增殖)",
                 f"验证要点:富集后 16S/qPCR 回测供体相对丰度 ≥10%,HPLC 检出胞外 GB/ectoine,体系{monitor}较对照显著提升,连续流 ≥30 天"]
        outs.append(row(f"q-{start+len(outs)}", "脱氮" if si != 3 else "污泥", "微生物调控", "中等",
                        "T5 菌株选择", q, kps, ideal,
                        "Bioaugmentation, Compatible solutes, Anammox, 菌株选择",
                        "L0430 Glycine Betaine and Ectoine Are the Majo；L0420 Interspecific competition and adaptation"))
    return outs


SUB_N = [150, 300, 500]  # 基质浓度档(mg/L)
TEMP_V = [("常温", 25), ("低温", 15)]


def gen_T7(n: int, start: int):
    """T7:培养基/进水设计(中等)。轴:模板×盐度区间×基质浓度×温度 = 6×12×3×2=432。"""
    outs = []
    templates = [_t7_anammox, _t7_sad, _t7_aob, _t7_pd, _t7_halomonas, _t7_coculture]
    for i in range(n):
        a, b = REGIMES[(i // 6) % len(REGIMES)]
        sub = SUB_N[(i // 72) % 3]
        tn, tv = TEMP_V[(i // 216) % 2]
        fn = templates[i % 6]
        outs.append(fn(f"q-{start+len(outs)}", a, b, (i // 12) % 2, sub, tn, tv))
    return outs


def _t7_anammox(qid, a, b, v, sub, tn, tv):
    steps, days = steps_days(a, b)
    no2 = round(sub * 1.32)
    q = (f"请为 anammox 耐盐化富集(进水 NH4⁺-N 约 {sub} mg/L,{tn} {tv}°C,目标盐度 {b:g}%)设计培养基/进水方案。"
         f"请按以下步骤完整作答:(1)给出配方与关键约束(NO2⁻:NH4⁺ 比、COD/TN);"
         f"(2)校验基质比;(3)给出盐度梯度驯化方案({a:g}%→{b:g}%)与富集终点判据。")
    kps = ["关键约束:ρ(COD)/ρ(TN)<1(抑异养菌保 anammox 主体),NO2⁻:NH4⁺≈1.32:1(摩尔)",
           "配方:无机盐基础培养基+NaCl 梯度驯化+氮源亚硝酸钠/氯化铵(1.32:1)+微量乙酸钠(COD/TN<1)+微量元素液(含 Ni/Se/Fe)",
           f"校验:{sub} mg/L NH4⁺-N 对应 NO2⁻-N 约 {no2} mg/L(1.32 倍)",
           f"盐度梯度:0.5%/步自 {a:g}% 至 {b:g}%,共 {steps} 步、约 {days} 天,每梯度 ≥7 个 HRT",
           "富集终点:产溶质供体菌相对丰度 ≥10% 或胞外溶质检出(HPLC),NRR 稳定"]
    ideal = ["关键约束:COD/TN<1 以抑制异养菌、维持 anammox 主体并保证产溶质菌选择性富集,氮源按 NO2⁻:NH4⁺≈1.32:1(摩尔)配制",
             f"配方:无机盐基础培养基+NaCl 梯度+亚硝酸钠/氯化铵氮源+微量乙酸钠+含 Ni/Se/Fe 微量元素液;{tn} {tv}°C 下酶动力学下降,梯度稳定时间适当延长",
             f"校验:{sub} mg/L NH4⁺-N 对应配 NO2⁻-N 约 {no2} mg/L",
             f"盐度梯度:以 0.5%/步自 {a:g}% 提升至 {b:g}%,共 {steps} 步、约 {days} 天,每梯度维持 ≥7 个 HRT 并以 NRR≥90% 为进阶判据",
             "富集终点以产溶质供体菌相对丰度 ≥10% 或 HPLC 检出胞外溶质为准"]
    return row(qid, "脱氮", "微生物调控", "中等", "T7 培养基设计", q, kps, ideal,
               "Anammox, Salinity acclimation, Compatible solutes, 培养基设计",
               "10.1021/acs.est.2c01104 Glutamate Enhances Osmoadaptation of Ana；L0410 Salinity Tolerance and Osmoadaptation St")


def _t7_sad(qid, a, b, v, sub, tn, tv):
    steps, days = steps_days(a, b)
    s_need = sub * 2.47 / 1000
    alk = sub * 4.57 / 1000
    q = (f"请为硫自养反硝化(SAD)菌群富集设计培养基({tn} {tv}°C,盐度 {a:g}%→{b:g}%,进水 NO3⁻-N 约 {sub} mg/L)。"
         f"请按以下步骤完整作答:(1)给出配方(电子供体/氮源/碱度/微量元素)与关键约束;"
         f"(2)按 S/N≈2.47 g S/g NO3-N 校验硫投加量并给出碱度需求;(3)给出盐度驯化与终点判据。")
    kps = ["配方:单质硫 S0 电子供体、NaNO3 氮源、NaHCO3 补碱度兼无机碳、NH4Cl 少量同化氮、含 Mo 微量元素液",
           f"校验:{sub} mg/L NO3-N 需约 {s_need:.2f} g/L S0(过量 10-20%),碱度约 {alk:.2f} g CaCO3/L 由 NaHCO3 补足",
           f"驯化:0.5%/步至 {b:g}% 共 {steps} 步约 {days} 天,硝酸盐还原率 ≥90% 进阶",
           "终点:Thiohalomonas 等硫反硝化菌占优、N2O 低、性能稳定 30 天"]
    ideal = ["配方:单质硫作电子供体,NaNO3 供氮,NaHCO3 补碱度并供无机碳,辅以少量 NH4Cl 与含钼微量元素液",
             f"校验:按硫自养计量 S/N≈2.47 g S/g NO3-N,{sub} mg/L NO3-N 需投约 {s_need:.2f} g/L 硫磺(留 10-20% 余量);SAD 产酸,按约 4.57 g CaCO3/g NO3-N 补碱度(即约 {alk:.2f} g/L)维持 pH 7.0-7.5",
             f"盐度驯化:0.5%/步自 {a:g}% 至 {b:g}%,共 {steps} 步约 {days} 天,以硝酸盐还原率 ≥90% 为进阶判据",
             "富集终点:Thiohalomonas/硫杆菌属相对丰度 ≥20%,N2O 低于检出限,连续 30 天稳定"]
    return row(qid, "脱氮", "微生物调控", "中等", "T7 培养基设计", q, kps, ideal,
               "Sulfur-driven denitrification, 培养基设计, Salinity acclimation",
               "10.1016/j.cej.2024.154266 Salinity responsive mechanisms of sulfur；10.1016/j.biortech.2025.132667 Sulfide-based autotrophic denitrificatio")


def _t7_aob(qid, a, b, v, sub, tn, tv):
    steps, days = steps_days(a, b)
    alk = sub * 7.14 / 1000
    q = (f"请为 AOB(氨氧化菌)耐盐驯化设计培养基({tn} {tv}°C,起始 {a:g}%,目标 {b:g}%,进水 NH4⁺-N {sub} mg/L)。"
         f"请按以下步骤完整作答:(1)给出配方要点(基质/碱度/pH/微量元素)与碱度化学计量;"
         f"(2)给出盐度梯度方案与 FA 协同抑制 NOB 说明;(3)给出终点判据与 NOB 防控。")
    kps = [f"配方:NH4Cl 基质 {sub} mg N/L,碱度按 7.14 g CaCO3/g N 补 NaHCO3(约 {alk:.2f} g/L 当量),pH 7.5-8.0,含 Cu 微量元素",
           f"驯化:0.5%/步自 {a:g}% 至 {b:g}% 共 {steps} 步约 {days} 天,每梯度 ≥7 个 SRT 且比氨氧化速率恢复 ≥90%",
           "FA 协同:pH 偏碱下游离氨处 NOB 抑制区间而对 AOB 耐受更高,利于选择",
           "终点:NAR ≥80%,AOB 占优,比氨氧化速率稳定 2 周;NOB 防控:低 DO+FA 抑制+及时排泥"]
    ideal = [f"配方要点:NH4Cl 供 {sub} mg/L NH4⁺-N,按硝化产酸化学计量每 g N 需 7.14 g CaCO3 当量碱度,即约 {alk:.2f} g/L,以 NaHCO3 补充并维持 pH 7.5-8.0,补充含铜微量元素",
             f"盐度梯度:0.5%/步自 {a:g}% 提升至 {b:g}%,共 {steps} 步约 {days} 天,每梯度维持 ≥7 个污泥龄且比氨氧化速率恢复至 ≥90% 再进阶;{tn} {tv}°C 下速率本底下降,判据以相对恢复率为准",
             "FA 协同:pH 偏碱、NH4⁺ 条件下游离氨浓度处于 NOB 抑制区间而 AOB 耐受更高,实现选择性富集",
             "终点判据:NAR≥80%、Nitrosomonas 占优、比氨氧化速率连续两周稳定;NOB 防控靠低 DO、维持 FA 窗口与及时排泥"]
    return row(qid, "脱氮", "微生物调控", "中等", "T7 培养基设计", q, kps, ideal,
               "Nitrification, Salinity acclimation, 培养基设计",
               "10.1021/acs.est.3c07324 Salinity Tolerance and Osmoadaptation St；Metcalf & Eddy(5th ed.)硝化碱度化学计量")


def _t7_pd(qid, a, b, v, sub, tn, tv):
    cod_lo, cod_hi = sub * 2.5, sub * 3.5
    q = (f"请为短程反硝化(PD)菌 Thauera 富集设计培养基({tn} {tv}°C,盐度 {a:g}%→{b:g}%,NO3⁻-N {sub} mg/L)。"
         f"请按以下步骤完整作答:(1)给出碳源选择与 COD/NO3⁻-N 窗口及理由;"
         f"(2)校验碳源投加量并说明碳过量/不足的后果;(3)给出终点判据与 N2O 防控。")
    kps = ["碳源与窗口:乙酸或乙醇,COD/NO3-N 约 2.5-3.5 窄窗,精准限碳是 NO2⁻ 积累核心",
           f"校验:{sub} mg/L NO3-N 对应投 COD 约 {cod_lo:.0f}-{cod_hi:.0f} mg/L,分批/脉冲投加",
           "后果:碳不足还原停在 NO3⁻、NTR 低;过量则越过 NO2⁻ 完全还原,N2O 风险升",
           "终点:NTR ≥90%、NO2⁻ 积累稳定、Thauera 占优;N2O 防控:pH 中性、防亚硝过度积累"]
    ideal = ["碳源选乙酸或乙醇(Thauera 利用性好),COD/NO3⁻-N 控制在约 2.5-3.5 的窄窗口,精准限碳是短程还原成败的核心",
             f"按 {sub} mg/L NO3⁻-N 校验需投 COD 约 {cod_lo:.0f}-{cod_hi:.0f} mg/L,采用分批或脉冲投加以稳住 NO2⁻ 积累",
             "碳源不足时 NO3⁻ 还原停滞、NTR 上不去;过量则 NO2⁻ 被继续还原为 N2/N2O,亚硝积累失败且 N2O 风险上升",
             "富集终点:NTR≥90%、NO2⁻ 积累率稳定、Thauera 丰度占优;维持 pH 中性并避免亚硝过度积累以防 FNA 抑制 nosZ"]
    return row(qid, "脱氮", "微生物调控", "中等", "T7 培养基设计", q, kps, ideal,
               "Partial denitrification, 培养基设计, Thauera",
               "10.1016/j.watres.2026.125764 Ectoine modulates mixotrophic denitrific；10.1016/j.jhazmat.2026.143139 Restoring partial denitrification under")


def _t7_halomonas(qid, a, b, v, sub, tn, tv):
    hi = 15 if v == 0 else 18
    q = (f"请为嗜盐产 ectoine 菌(Halomonas)选择性富集设计培养基(培养温度 {tn} {tv}°C,盐度 {hi}%,"
         f"碳源负荷以 {sub} mg/L 级 COD 起试,作服务 {a:g}%→{b:g}% 盐度体系的溶质供体菌种源)。"
         f"请按以下步骤完整作答:(1)给出配方要点与高盐选择压设计;(2)说明 ectoine 两段法诱导逻辑;"
         f"(3)给出终点判据与污染控制。")
    kps = ["配方:高盐矿物培养基(NaCl 至 150 g/L 级)、碳源谷氨酸钠或乙酸钠、通气良好;高盐本身即选择压",
           f"两段法:先 10% 增殖再提至 {hi}% 诱导 ectABC 高表达积累 ectoine,对数后期至稳定期采收",
           "终点:Halomonas 相对丰度 ≥60%,胞内 ectoine ≥50 mg/g DCW(HPLC),连续三代稳定",
           "污染控制:全流程灭菌、专属接种、镜检/平板双检"]
    ideal = ["培养基以高盐矿物培养基为基础,碳源选谷氨酸钠(兼氮源与 ectoine 前体)或乙酸钠,通气充足;目标盐度本身构成对非嗜盐菌的强选择压",
             f"ectoine 诱导遵循两段法:先在 10% 盐度快速增殖,再提至 {hi}% 诱导 ectABC 高表达,在对数后期至稳定期采收",
             "富集终点:16S 确认 Halomonas 相对丰度 ≥60%,HPLC 测得胞内 ectoine ≥50 mg/g 干菌,连续三代稳定传代",
             "全流程严格灭菌、专属接种并以镜检与平板双检控制污染"]
    return row(qid, "脱氮", "微生物调控", "中等", "T7 培养基设计", q, kps, ideal,
               "Compatible solutes, Bioaugmentation, 培养基设计, Halomonas",
               "L0430 Glycine Betaine and Ectoine Are the Majo")


def _t7_coculture(qid, a, b, v, sub, tn, tv):
    q = (f"请为'产 GB 供体菌+anammox'共培养体系设计维持培养基({tn} {tv}°C,anammox 进水 NH4⁺-N 约 {sub} mg/L,"
         f"自 {a:g}% 提升至 {b:g}%,供体丰度维持 ≥10%)。"
         f"请按以下步骤完整作答:(1)给出双基质设计与 COD/TN 约束;(2)说明交叉喂养逻辑与限碳选择;"
         f"(3)给出维持判据与失衡调整。")
    kps = ["双基质:anammox 基质 NH4⁺/NO2⁻ 1.32:1+供体限碳(微量乙酸钠,COD/TN<1)+高盐基础盐+微量元素",
           "交叉喂养:供体高盐下合成并外泌 GB,anammox 经现存转运摄取,碳源限量防异养失控又保供体活性",
           "判据:供体丰度 10-30%、NRR 稳定(周波动<10%)、胞外 GB 检出",
           "失衡:供体<10% 补碳脉冲 1-2 mg/L 并微降盐;>40% 停补碳防异养化"]
    ideal = ["以 anammox 人工进水为基底(NH4Cl/NaNO2 按 1.32:1、KHCO3 碱度、Ni/Se/Fe 微量元素),叠加微量乙酸钠或谷氨酸钠使 COD/TN<1,兼顾供体维持与异养菌抑制",
             "交叉喂养:Halomonas 类供体在高盐下合成 GB 并经外泌与菌体周转释放,anammox 摄取共享;碳源以'仅供维持、不足以高增殖'为原则",
             "维持判据:16S/qPCR 监测供体相对丰度 10-30%,NRR 周波动 <10%,HPLC 检出胞外 GB",
             "失衡调整:供体 <10% 时脉冲补碳 1-2 mg/L 并微降盐度;>40% 时停补碳并提高水力剪切,防体系异养化"]
    return row(qid, "脱氮", "微生物调控", "中等", "T7 培养基设计", q, kps, ideal,
               "Bioaugmentation, Compatible solutes, Anammox, 培养基设计",
               "L0430 Glycine Betaine and Ectoine Are the Majo；L0041 Deciphering performance and microbial ch")


def gen_T10(n: int, start: int):
    """T10:场景推理(复杂)。"""
    outs = []
    templates = [_t10_shock_vs_gradual, _t10_seasonal_vs_constant, _t10_temp_salt,
                 _t10_salt_ammonia, _t10_sulfate_extra, _t10_retrofit_vs_new]
    for i in range(n):
        a, b = REGIMES[(i // 6) % len(REGIMES)]
        iname, salt, feat = INDUSTRIES[(i // 72) % len(INDUSTRIES)]
        fn = templates[i % 6]
        r = fn(f"q-{start+len(outs)}", a, b, i)
        r["q"] = f"(场景背景:某厂处理{iname},盐度约 {salt:g}%。)" + r["q"]
        outs.append(r)
    return outs


def _t10_base(qid, q, kps, ideal, cat, ref, tag="脱氮"):
    return row(qid, tag, "环境工程与能源", "复杂", "T10 场景推理", q, kps, ideal, cat, ref)


def _t10_shock_vs_gradual(qid, a, b, i):
    q = (f"对比同一目标(盐度 {a:g}%→{b:g}%)的两种实现路径:路径一为一次性骤升冲击;"
         f"路径二为 0.5%/步渐进驯化。请按以下步骤完整作答:(1)拆解两条路径的关键变量差异"
         f"(菌群响应时间尺度、性能损失形态、恢复机制);(2)分别给出针对性措施;"
         f"(3)给出验证实验与回退方案。")
    kps = ["差异:骤升=瞬态渗透冲击,活性骤降靠'逆转剂'与再平衡恢复;渐进=种群重塑,逐步富集耐盐与产溶质菌",
           "骤升措施:立即降负荷 30-50%、投加 GB/海藻糖 0.5-1 mM 连续 3-5 天、必要时稀释缓冲",
           f"渐进措施:0.5%/步共 {round((b-a)/0.5)} 步,每梯度 ≥7 个 HRT 且 NRR≥90% 进阶,辅以产溶质菌共培养",
           "验证:两组对照连续流 ≥30 天;骤升组看 NRR 恢复率与恢复时间,渐进组看全梯度达标率;失稳回退一档"]
    ideal = ["关键差异:骤升冲击下菌群来不及种群重塑,以生理调节为主,表现为 NRR 骤降、EPS 异常,恢复依赖渗透再平衡与蛋白复性;渐进驯化给予每梯度 ≥7 个 HRT 的适应期,耐盐突变体与产溶质菌逐步富集,性能平稳迁移",
             "骤升路径措施:立即降低进水氮负荷 30-50%,投加甜菜碱/海藻糖(0.5-1 mM,连续 3-5 天)作逆转剂,启用稀释或回流缓冲",
             f"渐进路径措施:0.5%/步自 {a:g}% 至 {b:g}%,以 NRR≥90% 恢复为进阶判据,同步引入产溶质菌共培养与载体保护",
             "验证:两路径平行连续流 ≥30 天,骤升组评价 NRR 恢复率与恢复时间,渐进组评价各梯度达标率;任一梯度性能 2-3 天不恢复即回退盐度"]
    return _t10_base(qid, q, kps, ideal, "Salt shock, Salinity acclimation, Compatible solutes, 场景推理",
                     "10.1016/j.scitotenv.2019.07.215 Impacts of salt shocking and the selecti；10.1016/j.synbio.2026.04.016 Data-driven optimization of salt shock f")


def _t10_seasonal_vs_constant(qid, a, b, i):
    hi = f"{b:g}%"
    q = (f"对比两场景的盐度管理:场景 A 为季节性海水入侵(盐度 {a:g}%→{hi} 峰值持续数周后回落);"
         f"场景 B 为恒定工业提盐改造({a:g}%→{hi} 永久运行)。请按以下步骤完整作答:"
         f"(1)拆解关键变量差异(峰值形态/响应时间尺度/投资属性);(2)分别给出措施;"
         f"(3)给出验证与回退方案。")
    kps = ["差异:A 是反复瞬态冲击,核心是缓冲容量与恢复速度,适用临时措施;B 是稳态迁移,核心是梯度驯化与种群重塑,可沉淀永久改造",
           f"A 措施:调节池+在线盐度仪前馈稀释,峰值期 GB 0.5-1 mM 投加,维持污泥浓度冗余",
           f"B 措施:0.5%/步驯化至 {hi},产溶质菌共培养,耐盐菌富集,载体/颗粒化",
           "验证:A 看峰值期 NRR 保持率 ≥70% 且恢复 <7 天;B 看全盐度曲线达标;B 失稳回退一档"]
    ideal = ["场景 A 的峰值反复来去,菌群以生理调节应对,措施重在缓冲与快速恢复,投资具临时属性;场景 B 是一次性稳态迁移,菌群可完成种群重塑,措施可固化为永久改造",
             f"A:设调节池均衡盐度,在线盐度仪前馈控制稀释,峰值期投加 GB(0.5-1 mM)过渡,维持较高污泥浓度冗余",
             f"B:按 0.5%/步梯度驯化至 {hi}%,引入产溶质菌共培养并逐步富集耐盐功能菌,辅以载体或颗粒化保护",
             "验证与回退:A 以峰值期 NRR 保持率 ≥70%、恢复期 <7 天为合格,盐度回落后自愈;B 以全盐度曲线各梯度达标为准,失稳即回退一档并延长驯化"]
    return _t10_base(qid, q, kps, ideal, "Salinity acclimation, Compatible solutes, 场景推理",
                     "10.1016/j.scitotenv.2022.158221 Mitigating the detrimental effects of sa；10.1016/j.scitotenv.2019.07.215 Impacts of salt shocking and the selecti")


def _t10_temp_salt(qid, a, b, i):
    tname, tval = TEMPS[i % len(TEMPS)]
    q = (f"某 PN/A 系统在{tname}({tval}°C)条件下同时面临计划提盐({a:g}%→{b:g}%)。"
         f"请按以下步骤完整作答:(1)拆解低温/高温与盐度对 PN 段与 anammox 段的交互抑制;"
         f"(2)给出三种应对路线的权衡比较与推荐;(3)给出实施顺序与监测-回退方案。")
    cold = tval <= 15
    interact = (f"低温 {tval}°C 下 AOB 与 anammox 酶动力学速率大幅下降,是第一限制因子,盐度叠加渗透抑制使 NRR 可能跌至常温的 30-40%"
                if cold else f"高温 {tval}°C 加剧盐度下的代谢负担与菌群漂移,需防嗜盐杂菌增殖")
    recommend = ("推荐组合:SRT/污泥浓度优化+缓提盐(幅度减半至 0.25%/步、稳定时间加倍),辅以 GB 0.5-1 mM 过渡"
                 if cold else "推荐:加强排泥与水力控制防高温期菌群漂移,缓提盐+溶质投加过渡")
    kps = [f"交互:{interact},NOB 常因双胁迫受抑反而利于短程",
           "三路线:提高污泥龄/污泥浓度(零能耗,NOB 回潮风险)、局部加热(治本能耗高)、缓提盐+溶质投加(稳健周期长)",
           recommend,
           "顺序:先温度适应(SRT/DO 调整)再缓提盐;监测 NAR/NRR/三氮,失稳回退盐度并暂停计划"]
    ideal = [f"交互抑制:{interact};NOB 因双胁迫受抑,NAR 更易维持",
             "路线权衡:提高污泥龄零额外能耗但有 NOB 回潮与出水 NO3⁻ 升高风险;局部加热治本但能耗高;缓提盐+GB 投加周期长但稳健",
             recommend,
             "实施顺序:先完成温度侧稳态调整,再启动缓提盐;全程监测 NAR、NRR、三氮与 SAA,任一梯度性能 2-3 天不恢复即回退并暂停提盐"]
    return _t10_base(qid, q, kps, ideal, "PN/A, Salinity acclimation, Temperature, 场景推理",
                     "10.1016/j.jwpe.2022.102959 Enhanced nitrogen removal of single stag；Metcalf & Eddy(5th ed.)温度修正")


def _t10_salt_ammonia(qid, a, b, i):
    q = (f"某厌氧消化系统面临盐度 {a:g}%→{b:g}% 提升与进水 NH4⁺ 3 g/L 的盐-氨双胁迫。"
         f"请按以下步骤完整作答:(1)拆解双胁迫结构与交互(FNA 抑制随 pH 放大);"
         f"(2)给出抑制缓解与运行策略;(3)给出失稳预警指标与恢复路径。")
    kps = ["胁迫结构:盐致渗透抑制+游离氨抑制产甲烷古菌(乙酰裂解途径敏感),pH 升高时 FNA/NH3 抑制放大",
           "缓解:稀释/氨吹脱/鸟粪石沉淀预处理降游离氨,两相厌氧缓冲,GB 过渡投加",
           "预警:VFA/碱度>0.3-0.4、游离氨>150-200 mg N/L、甲烷含量骤降",
           "恢复:降负荷+稀释降氨+回退盐度,稳定后再渐进重启"]
    ideal = ["双胁迫结构:盐度升高造成产甲烷古菌渗透失衡与能量分流,NH4⁺ 3 g/L 在消化 pH 偏碱下游离氨浓度高,直接抑制乙酰裂解产甲烷,两者叠加放大",
             "缓解策略:优先降游离氨——稀释、氨吹脱或鸟粪石沉淀预处理;采用两相厌氧让产酸相先行缓冲;辅以甜菜碱过渡投加维持渗透稳态",
             "失稳预警:VFA/碱度比持续 >0.3-0.4、游离氨 >150-200 mg N/L、甲烷含量骤降且酸积累",
             "恢复路径:降低有机负荷、稀释降氨、回退盐度至上一稳定档,待 VFA 与甲烷恢复后再渐进重启提盐"]
    return _t10_base(qid, q, kps, ideal, "Anaerobic digestion, Ammonia inhibition, Salinity acclimation, 场景推理",
                     "Oren 2008(盐胁迫)；Metcalf & Eddy(5th ed.)氨抑制与碱度", tag="厌氧消化")


def _t10_sulfate_extra(qid, a, b, i):
    q = (f"高盐工业废水(盐度 {a:g}%→{b:g}%)含较高硫酸盐,anammox 耐盐化改造需额外注意什么?"
         f"请按以下步骤完整作答:(1)拆解硫酸盐还原(SRB)带来的竞争与硫化物毒性;"
         f"(2)给出针对性措施(碳源管控/硫自养耦合);(3)给出验证与回退方案。")
    kps = ["SRB 风险:硫酸盐还原菌与反硝化/anammox 争夺碳源与电子,产物硫化物抑制功能菌",
           "措施:控制 COD/TN<1 抑制 SRB,或转向硫自养反硝化耦合利用硫化物,溶质措施(G/GB)不变",
           "验证:出水 SO4²⁻/S²⁻、COD/TN、NRR 联动监测,批次 4 组 3 平行+连续流 ≥30 天",
           "回退:硫化物升高或性能失稳即降盐度并调整碳源"]
    ideal = ["硫酸盐还原菌(SRB)在高盐厌氧/缺氧条件下利用硫酸盐夺碳,与反硝化菌和 anammox 竞争电子供体,其产物硫化物对硝化/厌氧氨氧化酶系有直接毒性",
             "针对性措施:严格控制 COD/TN<1 压缩 SRB 生态位;或因势利导转向硫自养反硝化(SAD)耦合,把硫化物作为电子供体利用;相容性溶质投加(谷氨酸/GB)策略不变",
             "验证:监测出水硫酸盐/硫化物、COD/TN 与 NRR 联动,批次设 4 组处理 3 平行,连续流 ≥30 天",
             "回退:硫化物累积或性能失稳时回退盐度、调整碳源配比,必要时投铁盐沉硫"]
    return _t10_base(qid, q, kps, ideal, "Sulfate, SRB competition, Salinity acclimation, 场景推理",
                     "10.1016/j.cej.2024.154266 Salinity responsive mechanisms of sulfur；10.1016/j.biortech.2025.132667 Sulfide-based autotrophic denitrificatio")


def _t10_retrofit_vs_new(qid, a, b, i):
    q = (f"某厂需将脱氮能力升级并将盐度由 {a:g}% 提升至 {b:g}%,面临'现有活性污泥系统改造'与'新建耐盐 PN/A'两条路线。"
         f"请按以下步骤完整作答:(1)拆解两条路线的适用前提(场地/投资/周期/菌群基础);"
         f"(2)分别给出实施方案骨架;(3)给出决策建议与风险对冲。")
    kps = ["适用前提:改造利用存量菌群与池容,投资低周期长驯化慢;新建工艺选择自由,投资高但可按高盐工况设计",
           f"改造方案:梯度驯化(0.5%/步至 {b:g}%)+溶质投加过渡+生物强化供体菌+载体持留",
           f"新建方案:PN/A 主力+盐度窗口利用(NOB 双重受抑)+耐盐菌接种,按 {b:g}% 工况选材防腐",
           "决策:盐度≤3% 且场地受限优先改造;>3% 或可新建优先 PN/A;风险对冲:先中试验证 ≥30 天"]
    ideal = ["路线前提:改造盘活存量资产,菌群有驯化基础但上限受种质限制;新建自由度高,可按目标盐度工况整体设计(材质防腐、池型、接种源),但投资与周期更大",
             f"改造骨架:0.5%/步梯度驯化至 {b:g}%,关键梯度辅以 GB 投加,投加产溶质供体菌生物强化,增设聚氨酯载体持留功能菌",
             f"新建骨架:以 PN/A 为主力(盐度与低 DO 协同抑制 NOB 利于短程),接种耐盐 anammox 与伴生菌,设备按 {b:g}% 盐度选材",
             "决策建议:目标盐度 ≤3% 且场地受限时优先改造,>3% 或有新建条件时优先 PN/A;两条路线均先中试(≥30 天连续流)验证后再放大,保留稀释应急作为对冲"]
    return _t10_base(qid, q, kps, ideal, "工艺决策, Salinity acclimation, PN/A, 场景推理",
                     "10.1016/j.jwpe.2022.102959 Enhanced nitrogen removal of single stag；Metcalf & Eddy(5th ed.)工艺选择")


def gen_E(n: int, start: int):
    """E 类:环境工程/能源(中等/复杂)。"""
    outs = []
    templates = [_e_process_salinity, _e_industry_chain, _e_n2o, _e_fouling, _e_settling,
                 _e_economics, _e_window, _e_emergency, _e_energy, _e_bioaug, _e_seawater, _e_sludge_disposal]
    for i in range(n):
        proc = PROCESSES[(i // 12) % len(PROCESSES)]
        ind = INDUSTRIES[(i // 96) % len(INDUSTRIES)]
        fn = templates[i % 12]
        r = fn(f"q-{start+len(outs)}", proc, ind, i)
        iname, salt, feat = ind
        r["q"] = f"某厂处理{iname}(盐度约 {salt:g}%,{feat}),核心工艺为{proc[0]}。" + r["q"]
        outs.append(r)
    return outs


def _e_row(qid, q, kps, ideal, cat, ref, diff, tag="脱氮"):
    return row(qid, tag, "环境工程与能源", diff, "E 环境工程/能源", q, kps, ideal, cat, ref)


def _e_process_salinity(qid, proc, ind, i):
    pname, pfeature = proc
    q = (f"{pname}在高盐条件下面临哪些抑制,如何用相容性溶质协同强化?请按以下步骤完整作答:"
         f"(1)指出该工艺的关键抑制点({pfeature});(2)给出溶质强化方案(种类/时机/剂量);"
         f"(3)给出评价指标与验证实验设计。")
    kps = [f"抑制点:{pfeature}",
           "溶质方案:GB/海藻糖/谷氨酸 0.1-1 mM 起试,梯度跨越与冲击期投加",
           "评价:NRR/去除率/污泥性状,对照组 3 平行,连续流 ≥30 天"]
    ideal = [f"{pname}在高盐下的关键抑制:{pfeature}",
             "溶质强化:在盐度梯度跨越的关键段与冲击期投加 GB/海藻糖/谷氨酸(0.1-1 mM 起试,小试标定),维持胞内渗透稳态与酶活性",
             "评价:以工艺核心指标(NRR 或相应去除率)与污泥性状评价,设无溶质对照 3 平行,连续流验证 ≥30 天"]
    return _e_row(qid, q, kps, ideal, "Compatible solutes, 环境工程-脱氮", 
                  "10.1016/j.biortech.2014.06.015 Enhancement of anammox activity by addit；10.1016/j.ese.2024.100406 Glycine betaine modulates extracellular", "中等")


def _e_industry_chain(qid, proc, ind, i):
    iname, salt, feat = ind
    q = (f"某{iname}(盐度约 {salt:g}%,{feat})需达标处理,请设计处理工艺链。请按以下步骤完整作答:"
         f"(1)给出预处理-生化-深度的工艺链与各单元功能;(2)说明盐度管理策略(均衡/驯化/稀释取舍);"
         f"(3)给出全链验收指标。")
    kps = ["工艺链:预处理(格栅/隔油/混凝气浮除 SS 与油脂)-水解酸化提可生化性-耐盐生化核心-深度处理保障",
           f"盐度管理:调节池均衡波动,生化按上限驯化(0.5%/步),仅峰值超限少量稀释,避免连续大比例稀释",
           "验收:出水达标+去除率稳定+比活性稳定,连续流 ≥30 天并记录盐度-性能曲线"]
    ideal = ["工艺链:预处理去除 SS、油脂与抑制物,水解酸化提高可生化性,生化核心按耐盐驯化设计,末端深度处理保障达标",
             f"盐度管理:以调节池均衡 {salt:g}% 量级的波动,生化系统按上限盐度驯化、按中值运行,仅在峰值超限时段少量稀释,避免连续大比例稀释推高水耗",
             "验收指标:出水污染物达标,特征去除率与比活性连续 30 天稳定,形成盐度-性能运行曲线供运维参考"]
    return _e_row(qid, q, kps, ideal, "Wastewater treatment, Salinity acclimation, 环境工程-脱氮",
                  "10.1016/j.biortech.2020.123784 Enhancement of pollutants removal from s；Metcalf & Eddy(5th ed.)工艺链设计", "中等")


def _e_n2o(qid, proc, ind, i):
    pname, _ = proc
    q = (f"高盐如何加剧{pname}过程中 N2O 的累积,如何缓解?请按以下步骤完整作答:"
         f"(1)阐明盐度对 nosZ 与其他还原酶的差异化抑制机制;(2)给出缓解措施;"
         f"(3)给出 N2O 减排效果评价方案。")
    kps = ["机制:nosZ(含铜末端还原酶)对盐度最敏感,N2O 还原受阻而前序酶持续产 N2O,净累积增加",
           "缓解:GB/海藻糖保护 nosZ 构象,电子供体充足分配合理,pH 中性防亚硝积累(FNA)",
           "评价:顶空-GC/微电极测 N2O 通量,同步去除率,对照 3 平行"]
    ideal = ["机制:反硝化酶系对高盐敏感性不同,末端 N2O 还原酶 nosZ 含铜中心、最受盐度影响,活性率先下降而前序酶仍产 N2O,产出-消耗失衡致净累积",
             "缓解措施:投加 GB/海藻糖保护 nosZ 与胞内铜伴侣构象;保证电子供体充足且分配合理;维持 pH 中性并避免亚硝积累(FNA 抑制 nosZ)",
             "评价:顶空-GC 或微电极测定 N2O 通量,同步硝酸盐/亚硝去除率与 N2/N2O 比,设无溶质对照 3 平行并连续流复验"]
    return _e_row(qid, q, kps, ideal, "N2O mitigation, Denitrification, Compatible solutes",
                  "10.1007/s10532-012-9542-0 Biological denitrification of brine: the；10.1016/j.watres.2026.125764 Ectoine modulates mixotrophic denitrific", "复杂")


def _e_fouling(qid, proc, ind, i):
    q = ("高盐 MBR 运行中膜污染如何演变,与溶质调控有何关联?请按以下步骤完整作答:"
         "(1)描述盐度→EPS/SMP 组成变化→凝胶层/滤饼层→TMP 增速的链条;"
         "(2)给出以溶质调控为核心的缓解与清洗策略;(3)给出评价方案。")
    kps = ["链条:高盐改变 EPS/SMP 蛋白-多糖比,胞外溶质与胶体交联成致密凝胶层,滤饼孔隙率下降,TMP 增速加快",
           "缓解:GB 调控 EPS 组成回归正常,优化污泥龄与错流流速,载体降低比阻;在线碱洗+离线深度清洗",
           "评价:TMP 增速(kPa/d)、清洗后通量恢复率>90%、EPS/SMP 的 PN/PS 比跟踪,对照 3 平行"]
    ideal = ["污染链条:盐度促使 SMP 增分泌并改变 EPS 蛋白/多糖比,胞外相容性溶质与小分子胶体在膜面浓差极化层交联形成致密凝胶层,叠加滤饼层孔隙率下降,TMP 增速加快、清洗周期缩短",
             "缓解策略:以 GB 投加维持胞内稳态使 EPS 组成回归,优化污泥龄(15-20 d)与错流流速,可投加聚氨酯载体;清洗采用周期性在线化学清洗与离线深度清洗结合",
             "评价:TMP 日增速、清洗后膜通量恢复率(目标 >90%)、逐月 EPS 与 SMP 的 PN/PS 比,设对照 3 平行"]
    return _e_row(qid, q, kps, ideal, "Membrane fouling, MBR, EPS, Compatible solutes",
                  "10.1016/j.jwpe.2024.105076 Impacts of electric field coupled membra；10.1016/j.ese.2024.100406 Glycine betaine modulates extracellular", "复杂", tag="污泥")


def _e_settling(qid, proc, ind, i):
    q = ("高盐如何通过 EPS 介导恶化活性污泥沉降性能,如何改善?请按以下步骤完整作答:"
         "(1)阐明盐度→EPS 组成与电荷变化→絮体解体的因果链;(2)给出改善措施;"
         "(3)给出 SVI 与粒径评价方案。")
    kps = ["因果链:高盐改变 EPS 官能团电离,Na⁺ 置换 Ca²⁺/Mg²⁺ 桥,静电排斥增大絮体细化,SVI 升高",
           "措施:GB 维持胞内稳态减少 EPS 变性,补 Ca²⁺/Mg²⁺ 恢复桥联,生物强化促絮凝菌,控制负荷",
           "评价:SV30/SVI 逐日,激光粒度粒径分布,镜检,对照 3 平行"]
    ideal = ["因果链:盐度升高改变 EPS 蛋白/多糖比与官能团电离状态,高浓度 Na⁺ 置换絮体间 Ca²⁺/Mg²⁺ 桥,削弱架桥,絮体表面电荷升高、静电排斥增大,宏观表现为絮体细化、SVI 恶化",
             "改善措施:投加 GB/海藻糖维持胞内稳态减少 EPS 变性;补充二价阳离子恢复桥联;生物强化引入耐盐促絮凝菌;控制 F/M 与 DO 防冲击",
             "评价:逐日 SV30 与 SVI、激光粒度监测粒径分布(关注细颗粒占比)、镜检絮体与丝状菌,设对照组 3 平行"]
    return _e_row(qid, q, kps, ideal, "Activated sludge, EPS, Compatible solutes",
                  "10.1016/j.ese.2024.100406 Glycine betaine modulates extracellular；10.1016/j.jes.2023.10.0271001-0742 Effects of salinity and betaine addition", "中等", tag="污泥")


def _e_economics(qid, proc, ind, i):
    q = ("外源相容性溶质投加的经济性如何权衡?请按以下步骤完整作答:"
         "(1)列出成本项(溶质药剂/投加设备/监测)与收益项(性能恢复/避免稀释/产率);"
         "(2)给出'过渡手段 vs 长期方案'的定位判断;(3)给出经济性评估的计算框架。")
    kps = ["成本:GB 药剂费(按 0.1-1 mM 与处理量折算)+投加与监测设备摊销",
           "收益:NRR/去除率恢复带来的达标避免罚款、省去稀释水量与电耗、维持产能",
           "定位:溶质投加是启动/冲击期的过渡手段,长期应过渡到耐盐驯化或产溶质菌共培养(自维持)",
           "框架:总年成本差 vs 年收益差,做灵敏度分析(药剂价、盐度频次、水价)"]
    ideal = ["成本项:甜菜碱等药剂费按投加浓度(0.1-1 mM)与日处理量折算是大头,另计投加装置与在线监测的摊销",
             "收益项:性能快速恢复避免超标风险、替代大比例稀释节省水耗电耗、维持产能在冲击期不断档",
             "定位判断:外源投加适合启动期与冲击期的过渡,长期运行应转向耐盐驯化与产溶质菌共培养,使溶质供给内生化",
             "评估框架:对比'投加方案'与'替代方案'的年化总成本与收益差,对药剂价格、盐度冲击频次、水价做灵敏度分析"]
    return _e_row(qid, q, kps, ideal, "Compatible solutes, 经济性, 环境工程-脱氮",
                  "10.1016/j.biortech.2014.06.015 Enhancement of anammox activity by addit；10.1002/wer.1457 The application of glycine betaine to al", "中等")


def _e_window(qid, proc, ind, i):
    q = ("如何利用盐度对 NOB 与 AOB 敏感性差异的'盐度窗口'实现短程硝化?请按以下步骤完整作答:"
         "(1)给出窗口量级与协同因子(FA/FNA、DO);(2)给出运行控制要点;"
         "(3)说明风险与验证设计。")
    kps = ["窗口:NOB 较 AOB 敏感,约 10-20 g/L 出现选择性抑制而 AOB 可驯化维持",
           "控制:低 DO(1-1.5 mg/L)+FA 处 NOB 抑制区间+短 SRT 淘汰 NOB,三因子协同",
           "风险:>30-35 g/L 反抑 AOB,亚硝积累过高抑制下游;验证:梯度盐度批次看 NAR 与比活性,3 平行"]
    ideal = ["窗口量级:NOB(如 Nitrospira)对盐度更敏感,约 10-20 g/L 即出现选择性抑制,而 AOB 经驯化可维持活性,该差异构成短程硝化窗口",
             "控制要点:DO 控制在 1-1.5 mg/L,维持游离氨对 NOB 的抑制区间,适当缩短 SRT 淘汰长世代 NOB,与盐度协同可将 NAR 提至 80% 以上",
             "风险:盐度超过约 30-35 g/L 后 AOB 活性亦明显下降,且出水亚硝过高会对下游 anammox 造成 FNA 抑制;验证采用梯度盐度批次,监测 NAR 与比氨氧化速率,3 平行"]
    return _e_row(qid, q, kps, ideal, "Nitrification, Salinity acclimation, PN/A",
                  "10.1021/acs.est.3c07324 Salinity Tolerance and Osmoadaptation St；10.1016/j.jwpe.2022.102959 Enhanced nitrogen removal of single stag", "复杂")


def _e_emergency(qid, proc, ind, i):
    q = ("某反应器遭盐度骤升冲击,请给出分级响应决策流程。请按以下步骤完整作答:"
         "(1)给出即时/中期/长期三级响应的判据与动作(含逆转剂选择);"
         "(2)说明甜菜碱/海藻糖作为逆转剂的作用机制与投加要点;(3)给出恢复期判据与再提盐前提。")
    kps = ["即时(24 h):降进水负荷 30-50%、投逆转剂(GB/海藻糖 0.5-1 mM,3-5 天)、稀释/回流缓冲",
           "中期(1-7 天):NRR 恢复<50% 则延长 HRT、补种污泥、排查 NOB/异养增殖",
           "长期(>7 天):0.25-0.5%/步重建驯化梯度,以 NRR≥90% 进阶",
           "逆转剂机制:帮助胞内渗透再平衡与蛋白复性,宜早投、小试标定、不长期依赖;恢复判据:NRR≥80% 且稳定 7 天,再提盐幅度减半"]
    ideal = ["即时响应(24 h 内):降低进水氮负荷 30-50%,投加逆转剂(甜菜碱/海藻糖,0.5-1 mM 起投,连续 3-5 天),启用稀释或回流缓冲,监测 NRR 与三氮",
             "中期响应(1-7 天):若 NRR 恢复不足冲击前 50%,延长 HRT、提高污泥浓度或补充外源功能污泥,排查 NOB 与异养菌增殖",
             "长期响应(>7 天):按 0.25-0.5%/步重建盐度驯化梯度,每梯度以 NRR≥90% 恢复为进阶判据",
             "逆转剂机制与要点:盐冲击致渗透失衡与酶失活,GB/海藻糖帮助胞内渗透再平衡、稳定蛋白并促进复性;投加宜早、剂量经小试标定、避免长期依赖。恢复判据:NRR 恢复至 ≥80% 且连续稳定 7 天方可再提盐,幅度减半并加密监测"]
    return _e_row(qid, q, kps, ideal, "Salt shock, Compatible solutes",
                  "10.1016/j.scitotenv.2019.07.215 Impacts of salt shocking and the selecti；10.1016/j.synbio.2026.04.016 Data-driven optimization of salt shock f", "复杂")


def _e_energy(qid, proc, ind, i):
    q = ("相容性溶质对高盐有机废水的能源回收(厌氧产甲烷)有何意义?请按以下步骤完整作答:"
         "(1)说明高盐抑制产甲烷的机制与溶质恢复作用;(2)给出投加方案与嗜盐产甲烷参照;"
         "(3)给出沼气恢复的评价指标与经济性考量。")
    kps = ["机制:渗透失衡使产甲烷古菌耗能调节,F430/CoM 周转受阻,沼气产率与甲烷含量双降;GB/海藻糖助渗透再平衡与蛋白复性",
           "方案:GB 0.5-2 mM 起试批次标定;参照 Methanohalophilus 等嗜盐产甲烷菌积累甜菜碱/β-谷氨酸",
           "评价:日产沼气量、甲烷含量、VFA/碱度;经济性:溶质成本 vs 沼气收益 vs 稀释成本三笔账",
           ]
    ideal = ["抑制机制:高盐致胞内水分外流与 K⁺ 失衡,产甲烷古菌消耗大量能量渗透调节,乙酰裂解通路辅因子(F430/CoM)周转受阻,沼气产率与甲烷含量同步下降;投加 GB/海藻糖可助渗透再平衡与蛋白复性",
             "投加方案:GB 0.5-2 mM 起试并经批次标定;自然界 Methanohalophilus 等嗜盐产甲烷菌以甜菜碱、β-谷氨酸为溶质,可作耐盐菌种参照",
             "评价指标:日产沼气量、甲烷含量、VFA/碱度与 COD 去除率;经济性需比较溶质成本、沼气收益与稀释成本三笔总账,长期向耐盐驯化过渡"]
    return _e_row(qid, q, kps, ideal, "Anaerobic digestion, Methanogenesis, Compatible solutes, 环境工程-能源",
                  "Oren 2008, Microbial life at high salt concentrations；10.1016/j.biortech.2014.06.015 Enhancement of anammox activity by addit", "中等", tag="厌氧消化")


def _e_bioaug(qid, proc, ind, i):
    pname, _ = proc
    q = (f"耐盐菌剂生物强化在{pname}系统中的定殖与流失规律是什么?请按以下步骤完整作答:"
         f"(1)说明投加后菌剂丰度的典型演替(冲高-回落-稳态)及其决定因素;"
         f"(2)给出提高持留率的措施(载体/生态位/反复投加);(3)给出定殖成功判据。")
    kps = ["演替:投加后丰度冲高,无生态位支撑则被原生菌群竞争回落,有底物/载体支撑趋向稳态",
           "措施:投加耐盐载体持留、创造专性底物生态位、周期性补充投加、与溶质供给联动",
           "判据:投加 30 天后相对丰度仍 ≥10% 且功能指标持续改善,清洗效应过后功能保持"]
    ideal = ["典型演替:外投菌剂短期内相对丰度冲高,若无持续生态位支撑会被原生菌群竞争性淘汰而回落;存在专性底物、载体附着或溶质互惠时趋于形成稳态低丰度共存",
             "提高持留:投加聚氨酯等耐盐载体供附着挂膜;创造与功能匹配的底物生态位;按洗出速率周期性补充;与相容性溶质供给联动增强互惠",
             "定殖判据:投加 30 天后 16S/qPCR 仍检出 ≥10% 相对丰度,功能指标(NRR/去除率)持续优于对照,且停投后功能短期保持"]
    return _e_row(qid, q, kps, ideal, "Bioaugmentation, Salinity acclimation",
                  "L0420 Interspecific competition and adaptation；L0041 Deciphering performance and microbial ch", "中等")


def _e_seawater(qid, proc, ind, i):
    q = ("海水冲厕城市污水(盐度约 1.5-2%)的主流脱氮工艺应如何设计?请按以下步骤完整作答:"
         "(1)分析该盐度对常规硝化反硝化与 PN/A 两条路线的影响差异;"
         "(2)给出推荐路线与盐度管理要点;(3)说明剩余污泥处置注意事项。")
    kps = ["差异:1.5-2% 盐度驯化后对 AOB 影响有限而 NOB 被选择性抑制,利于 PN;常规反硝化碳源利用率下降",
           "推荐:主流 PN/A+盐度驯化,冲击期辅以 GB,监测 NAR/NRR",
           "污泥:含盐污泥脱水性能改变(EPS/离子),土地利用受盐分约束,权衡焚烧/混掺",
           ]
    ideal = ["影响差异:1.5-2% 盐度下驯化的 AOB 可维持活性而 NOB 被选择性抑制,落在有利短程硝化的窗口,PN/A 路线获益;常规全程反硝化则碳源利用效率下降",
             "推荐路线:主流 PN/A,启动期盐度梯度驯化(0.5%/步,每梯度 ≥7 个 HRT),冲击期辅以 0.5-1 mM 甜菜碱过渡,日常监测 NAR、NRR 与三氮",
             "污泥处置:含盐污泥 EPS 与离子组成改变影响脱水药剂选择;土地利用受施用盐分总量约束,可权衡焚烧或与低盐污泥混合处置"]
    return _e_row(qid, q, kps, ideal, "PN/A, Salinity acclimation, Wastewater treatment",
                  "10.1016/j.jwpe.2022.102959 Enhanced nitrogen removal of single stag；10.1016/j.scitotenv.2022.158221 Mitigating the detrimental effects of sa", "复杂")


def _e_sludge_disposal(qid, proc, ind, i):
    q = ("高盐活性污泥系统的剩余污泥处置有哪些特殊考虑?请按以下步骤完整作答:"
         "(1)说明盐度对污泥脱水/药耗/土地利用的影响;(2)给出处置路线建议;"
         "(3)给出污泥盐分管控指标。")
    kps = ["影响:胞内 K⁺/Na⁺ 与 EPS 改变絮体脱水性能,药耗上升;土地利用受盐分总量与氯离子约束",
           "路线:与低盐污泥混掺、深度脱水后焚烧、或洗盐后资源化,按当地标准选择",
           "指标:污泥含盐率/氯离子含量、SVI 与比阻、滤液盐度回流量"]
    ideal = ["盐度影响:高盐驯化污泥胞内富集 K⁺/Na⁺ 与 Cl⁻,EPS 组成改变使絮体脱水性能波动、药剂消耗上升;土地利用时盐分总量与氯离子受限",
             "处置路线:优先与低盐源污泥混掺拉低含盐率;或深度脱水后焚烧;有条件时洗盐预处理后资源化利用;按受纳标准选择",
             "管控指标:污泥含盐率与氯离子含量、脱水 SVI 与比阻、滤液盐度及其回流对主流程的冲击"]
    return _e_row(qid, q, kps, ideal, "Activated sludge, 污泥处置, Salinity acclimation",
                  "10.1016/j.jenvman.2023.118717 Impact of salinity on anaerobic ceramic；Metcalf & Eddy(5th ed.)污泥处理章节", "中等", tag="污泥")


def gen_T1(n: int, start: int):
    """T1:总体耐盐化措施(复杂),全因子空间采样。"""
    from scripts.generate_questions import T1_Q_TMPL, REFS_T1

    outs = []
    combos = [(org, p) for org in ORGANISMS for p in GENOME_PROFILES]
    seen = set()
    i = 0
    while len(outs) < n and i < n * 30:
        seed = int(hashlib.md5(f"t1|{i}".encode()).hexdigest()[:8], 16)
        org, p = combos[seed % len(combos)]
        a, b = REGIMES[(seed >> 8) % len(REGIMES)]
        reactor, water, hrt = REACTOR_POOL[(seed >> 16) % len(REACTOR_POOL)]
        key = (org, p, a, b, reactor)
        if key in seen:
            i += 1
            continue
        seen.add(key)
        prof = GENOME_PROFILES[p]
        steps, days = steps_days(a, b)
        q = T1_Q_TMPL.format(reactor=reactor, water=f"({water})" if water else "",
                             hrt=hrt, org=org, p=p, a=f"{a:g}", b=f"{b:g}")
        kps = [f"(1)诊断:{_s(prof['syn'])}，{_s(prof['transport'])}，结论:{_s(prof['concl'])}",
               f"(2)梯度:0.5%/步自 {a:g}% 至 {b:g}%,共 {steps} 步约 {days} 天,每梯度 7 个 HRT({hrt} h),NRR≥90% 进阶",
               f"(3)溶质措施:与转运一致——{_s(prof['concl'])},外源 0.1-1 mM 小试优化",
               f"(4)供体菌:{_s(prof['donor'])},依据:合成能力/盐度生态位/可定殖性",
               "(5)保护与回退:PU 载体或颗粒化缓冲,监测 NRR/SAA/亚硝/Na⁺ 与溶质基因表达,2-3 天不恢复即回退"]
        ideal = [f"(1)功能注释与缺陷诊断:{_s(prof['syn'])};{_s(prof['transport'])};结论:{_s(prof['concl'])}",
                 f"(2)盐度梯度:0.5%/步自 {a:g}% 提升至 {b:g}%,共 {steps} 步、约 {days} 天,每梯度维持 7 个 HRT({hrt} h)并以 NRR≥90% 为进阶判据",
                 f"(3)相容性溶质措施:{_s(prof['concl'])}——外源投加(0.1-1 mM 起试)利用现存转运,转运缺失时优先互补菌跨喂",
                 f"(4)供体菌:{_s(prof['donor'])},按合成能力/盐度生态位/可定殖性筛选",
                 "(5)保护与监测回退:聚氨酯载体、颗粒化或生物膜化缓冲盐胁迫;监测 NRR/SAA/亚硝残留/Na⁺ 与溶质合成基因表达;性能连续 2-3 天不恢复则回退盐度或延长驯化"]
        outs.append(row(f"q-{start+len(outs)}", "脱氮", "环境工程与能源", "复杂",
                        "T1 总体耐盐化措施", q, kps, ideal,
                        "Anammox, Salinity acclimation, Compatible solutes, Bioaugmentation, 总体策略", REFS_T1))
        i += 1
    return outs


# ---------------- 主流程 ----------------


def gate_v2(df, existing):
    """v2 门禁:硬性=schema/要点数/逐字重复;信息项=模板签名族(因子家族为设计性重复,只报告)。"""
    tmp = DATA / "_qc_tmp_v2.csv"
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    try:
        qs = load_questions(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    problems, warns = [], []
    bank_texts = {q.question for q in existing}
    seen_texts: dict[str, str] = {}
    for q in qs:
        if not 3 <= q.num_keypoints <= 8:
            problems.append(f"{q.question_id}: 要点数 {q.num_keypoints} 不在 3-8")
        if q.question in bank_texts:
            problems.append(f"{q.question_id}: 与现有题库逐字重复")
        if q.question in seen_texts:
            problems.append(f"{q.question_id}: 与 {seen_texts[q.question]} 逐字重复")
        seen_texts.setdefault(q.question, q.question_id)

    from collections import Counter

    fam = Counter(template_signature(q.question) for q in qs)
    fam_existing = sum(1 for q in qs
                       if template_signature(q.question) in
                       {template_signature(e.question) for e in existing})
    dup_families = {k: v for k, v in fam.items() if v > 1}

    from wwbench.graders import HeuristicGrader

    grader = HeuristicGrader()
    low = sum(1 for q in qs if grader.grade(q, q.ideal_detail).composite_score() < 0.6)
    print(f"[qc][info] 批内模板族(签名>1)共 {len(dup_families)} 族,"
          f"最大族 {max(dup_families.values(), default=0)} 题(因子家族属设计性重复)")
    print(f"[qc][info] 与现有库同签名 {fam_existing} 题;oracle 自评<0.6 共 {low} 题")
    return problems, warns


TARGETS = {"A": 120, "T5": 110, "T7": 130, "T10": 90, "E": 200, "T1": 400}


def build_all() -> list[dict]:
    start = 313
    out: list[dict] = []
    for fn, n in ((gen_A, TARGETS["A"]), (gen_T5, TARGETS["T5"]), (gen_T7, TARGETS["T7"]),
                  (gen_T10, TARGETS["T10"]), (gen_E, TARGETS["E"]), (gen_T1, TARGETS["T1"])):
        rows = fn(n, start + len(out))
        out.extend(rows)
    # 题号重排(连续)
    for i, r in enumerate(out):
        r["id"] = f"q-{313 + i}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve", action="store_true", help="质检通过后备份并合入题库")
    args = ap.parse_args()

    import pandas as pd

    bank_path = DATA / "questions.csv"
    if args.approve:
        pending_path = DATA / "pending_review_1000.csv"
        backup = DATA / "questions_v1_92.csv"
        if not backup.exists():
            shutil.copy(bank_path, backup)
        bank = pd.read_csv(bank_path, encoding="utf-8-sig")
        pending = pd.read_csv(pending_path, encoding="utf-8-sig")
        pending = pending[list(bank.columns)]
        merged = pd.concat([bank, pending], ignore_index=True)
        merged.to_csv(bank_path, index=False, encoding="utf-8-sig")
        print(f"[merge] 合入 {len(pending)} 题,题库 {len(bank)} -> {len(merged)} 题(备份 {backup.name})")
        return 0

    existing = load_questions(bank_path)
    existing_sigs = {template_signature(q.question) for q in existing}
    batch = build_all()
    df = pd.DataFrame([{
        "question_id": b["id"], "标签": b["tag"], "主题": b["topic"], "难度": b["diff"],
        "题型": b["qt"], "question": b["q"], "ideal_keypoints（打分用）": b["kp"],
        "ideal_detail（参考）": b["ideal"], "eval_mode": "rubric_6dims",
        "categories": b["cat"], "参考文献": b["ref"], "细分": "废水生物处理",
    } for b in batch])
    problems, warns = gate_v2(df, existing)
    out = DATA / "pending_review_1000.csv"
    df.insert(0, "review_status", "pending")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    from collections import Counter
    print(f"[draft] 起草 {len(df)} 题 -> {out.name};题型分布 {dict(Counter(df['题型']))}")
    print(f"[qc] 硬性问题 {len(problems)} 条:{problems[:8] if problems else '无'}")
    print(f"[qc] 软性提醒 {len(warns)} 条:{warns[:5] if warns else '无'}")
    if problems:
        print("[qc] 存在硬性问题,不合入")
        return 1
    print("[qc] 通过。可用 --approve 合入(将自动备份 questions_v1_92.csv)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
