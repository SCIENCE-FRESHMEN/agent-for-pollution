"""WWBench 出题流水线:起草 → 自动质检 → 待审队列 → 批准合入。

方法学来源(检索生物 AI 领域 benchmark 构建方法后提炼):
- LAB-Bench / ScienceAgentBench:题目源自可溯源的文献/专家材料,金标准解必须自洽;
- BixBench:LLM 起草 → 专家审改 → LLM 三次去重 → 人工核实后入库;
- SEED-Bench:按评测维度定向生成 + 自动质量过滤。

种子分层:
- L1 已验证文献要点:引用题库既有 DOI/内部编号(最高可信);
- L2 教科书级共识:明确标注来源(Metcalf & Eddy 等),不编造 DOI;
- L3 因子模板扩展:T1 家族的 8 个基因组档案 × 新盐度区间(程序化,槽位来自既有数据)。

用法:
  python scripts/generate_questions.py                     # 起草+质检 → data/pending_review.csv
  python scripts/generate_questions.py --approve-all       # 校准通过后合入题库(自动备份)
  python scripts/generate_questions.py --start-id 313       # 用新题号起草下一批,仍走同一质检流程
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wwbench.dataset import load_questions, split_keypoints  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# ---------- L1/L2 人工起草批次(28 题,补齐非 T1 题型与污泥/厌氧消化标签) ----------
# 字段:(id, 标签, 主题, 难度, 题型, 题面, 打分要点, 参考答案, categories, 参考文献)
R = "rubric_6dims"
AUTHORED: list[dict] = [
    dict(id="q-201", tag="脱氮", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="高盐废水如何利用盐度窗口实现短程硝化(PN)?请按以下步骤完整作答:(1)说明 AOB 与 NOB 对盐度敏感性的差异及可利用的盐度窗口量级(以 g NaCl/L 计);(2)给出以盐度协同 FA/FNA 抑制 NOB 的运行控制要点(DO、pH、SRT 的协同);(3)说明该策略的风险(盐度过高反抑 AOB、亚硝累积毒性)与验证实验设计。",
         kp="1.盐度窗口:NOB 较 AOB 对盐度更敏感,约 10-20 g/L 开始被选择性抑制而 AOB 仍保持活性;2.控制要点:低 DO(<1.5 mg/L)+盐度协同、维持 FA 对 NOB 的抑制区间、控制 SRT 富集 AOB;3.风险:>30 g/L 时 AOB 亦受抑,亚硝积累抑制厌氧氨氧化;4.验证:梯度盐度批次试验,监测亚硝积累率(NAR)与氨氧化速率,设 3 平行",
         ideal="NOB(如 Nitrospira)对盐度的敏感性显著高于 AOB,约 10-20 g/L NaCl 即出现选择性抑制,而 AOB(Nitrosomonas)在适度盐度下可经驯化维持活性,该差异构成短程硝化的盐度窗口。运行控制:控制 DO 在 1-1.5 mg/L、维持游离氨(FA)对 NOB 的抑制区间(约 0.1-1.0 mg N/L 视菌而异)、适当缩短 SRT 淘汰生长慢的 NOB,三者与盐度协同可将亚硝积累率提升至 80% 以上。风险:盐度超过约 30-35 g/L 后 AOB 活性也明显下降,且出水亚硝过高会对下游 anammox 造成 FNA 抑制。验证设计:设置 5/10/15/20 g/L 梯度盐度批次试验,监测 NAR、比氨氧化速率与 NOR,每组 3 平行,连续流验证 ≥30 天。",
         cat="Nitrification, Salinity acclimation, 环境工程-脱氮, PN/A",
         ref="10.1021/acs.est.3c07324 Salinity Tolerance and Osmoadaptation St；10.1016/j.jwpe.2022.102959 Enhanced nitrogen removal of single stag；Metcalf & Eddy, Wastewater Engineering(5th ed.)硝化动力学章节"),
    dict(id="q-202", tag="脱氮", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="短程反硝化-厌氧氨氧化(PD-A)耦合系统在高盐条件下如何维持稳定的亚硝酸盐供给?请按以下步骤完整作答:(1)指出高盐下 PD 菌(如 Thauera)与 anammox 菌各自的关键抑制点;(2)给出碳源投加与 C/N 控制策略(说明为何高盐下碳源投加需更精准);(3)给出 NO2⁻ 供给-消耗平衡的监测指标与失衡时的调整方案。",
         kp="1.PD 菌抑制点:Nar/Nir 酶活下降、碳源代谢偏移导致 NO3⁻→NO2⁻ 转化不完全;anammox 抑制点:联氨合成受阻、NRR 下降;2.C/N 策略:高盐下碳源利用效率降低但过量碳源会增殖异养菌,需将 COD/NO3⁻ 控制在刚好满足短程还原的窄区间并小频次精准投加;3.监测:出水 NO2⁻/NO3⁻/NH4⁺ 三氮逐日监测,NRR 与 NTR(硝酸盐转化率)联动判断;失衡时先调碳源再调 HRT",
         ideal="高盐下 PD-A 系统的关键抑制点:PD 菌的 Nar/Nir 还原酶在高盐下构象与活性下降,且碳代谢通量偏移会使 NO3⁻ 还原停在 NO2⁻ 之前或过度还原至 N2O/N2;anammox 侧则表现为 NRR 与 SAA 下降、联氨中间体积累。碳源策略:高盐降低碳源利用效率,但碳过量将增殖异养反硝化菌并与 anammox 争夺 NO2⁻,故 COD/NO3⁻-N 应控制在满足短程还原的窄窗口(约 2.5-3.5,以乙酸计需小试标定)并采用多点小剂量精准投加,可辅以 GB/海藻糖等溶质缓解酶失活。监测:逐日出水三氮(NH4⁺/NO2⁻/NO3⁻),以 NTR(≥90%)与 NRR 联动判断供给-消耗平衡;失衡时优先微调碳源投加量,其次调整 HRT 或回流比,并核查盐度是否超出驯化窗口。",
         cat="Anammox, Partial denitrification, Compatible solutes, 环境工程-脱氮",
         ref="10.1016/j.watres.2026.125764 Ectoine modulates mixotrophic denitrific；10.1016/j.jhazmat.2026.143139 Restoring partial denitrification under；10.1016/j.biortech.2026.133976 Optimal glycine betaine threshold for en"),
    dict(id="q-203", tag="脱氮", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="硫自养反硝化(SAD)处理高盐含硝酸盐废水时面临哪些双重胁迫,如何用相容性溶质协同强化?请按以下步骤完整作答:(1)拆解高盐+硫化物双重胁迫的作用机制(分别对硫氧化与反硝化酶系);(2)给出溶质强化方案(种类、投加时机)与碱度/ pH 管理要点;(3)给出评价指标(含 N2O)与验证实验设计。",
         kp="1.机制:高盐致渗透失衡与酶失活(Nar/Nir/Sor 等),硫化物抑制细胞色素氧化酶并毒害 NOB/反硝化酶;2.溶质方案:谷氨酸(兼氮源与渗透保护)或 GB 投加,批次与连续流均在高梯度盐度段投加;碱度:SAD 产酸需补碱度(NaHCO3),维持 pH 7.0-7.5;3.评价:硝酸盐还原率、硫化物去除率、出水 SO4²⁻、N2O 排放;批次 3 平行+连续流 ≥30 天",
         ideal="双重胁迫机制:高盐引起渗透失衡、胞内 K+/谷氨酸流失,使硫氧化与反硝化酶(Sor、Nar、Nir)构象改变失活;硫化物则与细胞色素氧化酶的铁结合产生毒性,并抑制反硝化末端酶,两者叠加时 N2O 累积加剧。溶质强化:投加谷氨酸(兼作氮源与相容溶质)或甘氨酸甜菜碱,在盐度梯度跨越的关键段(如每级提盐后 48 h 内)投加以缓冲渗透冲击;同时 SAD 以 NaHCO3 补充碱度、维持 pH 7.0-7.5,避免产酸进一步抑制菌群。评价:硝酸盐还原速率与去除率、硫化物去除率、出水硫酸盐、N2O 排放通量;设计批次小试(4 组处理:无溶质对照/GB/谷氨酸/组合,每组 3 平行)+ 连续流验证 ≥30 天。",
         cat="Sulfur-driven denitrification, Compatible solutes, Salinity acclimation, 环境工程-脱氮",
         ref="10.1016/j.biortech.2025.132667 Sulfide-based autotrophic denitrificatio；10.1016/j.jenvman.2025.128082 Unlocking long-term hypersalinity stress；10.1016/j.cej.2024.154266 Salinity responsive mechanisms of sulfur"),
    dict(id="q-204", tag="厌氧消化", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="高盐对厌氧消化产甲烷的抑制机制是什么,如何用相容性溶质恢复?请按以下步骤完整作答:(1)阐明高盐抑制产甲烷古菌的机制(渗透调节失衡、K+ 策略、关键酶如 F430/CoM 相关代谢受阻);(2)给出溶质投加方案(甜菜碱/海藻糖等)与嗜盐产甲烷案例(如 Methanohalophilus);(3)说明该措施对高盐有机废水能源回收(沼气)的意义与经济性考量。",
         kp="1.机制:胞外渗透压升高致水分外流、K+ 被动外排,产甲烷古菌需消耗大量能量做渗透调节,乙酰裂解与氢营养产甲烷通量下降;2.溶质方案:投加 GB(0.5-2 mM 起试)或海藻糖缓解渗透冲击;嗜盐产甲烷菌(如 Methanohalophilus portucalensis)自身积累甜菜碱/β-谷氨酸;3.意义:恢复沼气产率与甲烷含量,减少稀释水量;经济性:GB 成本需与沼气收益及稀释成本比较,长期宜转向耐盐驯化或共培养",
         ideal="高盐抑制机制:胞外渗透压骤升使产甲烷古菌胞内水分外流、K+ 与代谢物泄漏,细胞为维持渗透平衡消耗大量 ATP,乙酰裂解产甲烷的关键辅因子(F430、CoM)周转与合成受阻,表现为沼气产率与甲烷含量同步下降、VFA 累积。溶质恢复:外源投加甘氨酸甜菜碱(0.5-2 mM 起试,批次标定)或海藻糖,帮助胞内渗透再平衡与蛋白复性;自然界嗜盐产甲烷菌(如 Methanohalophilus)以积累甜菜碱、β-谷氨酸等溶质适应高盐,可为工程菌种选择提供参照。意义:在高盐有机废水(腌制、水产加工)中恢复能源回收效率、省去大量稀释水;经济性上 GB 投加属应急/过渡手段,长期应比较溶质成本-沼气收益-稀释成本三者的总账,并逐步过渡到耐盐驯化或耐盐共培养体系。",
         cat="Anaerobic digestion, Compatible solutes, Methanogenesis, 环境工程-能源",
         ref="Oren 2008, Microbial life at high salt concentrations(综述)；10.1016/j.biortech.2014.06.015 Enhancement of anammox activity by addit(溶质投加剂量参照)"),
    dict(id="q-205", tag="厌氧消化", topic="环境工程与能源", diff="中等", qt="E 环境工程/能源",
         q="某腌制废水含盐约 4%(40 g/L)、COD 约 15 g/L,拟采用厌氧消化回收能源。请按以下步骤完整作答:(1)判断该盐度对产甲烷的抑制等级并说明依据(给出轻度/中度/重度抑制的盐度量级);(2)比较三种路线:稀释后常规厌氧、两相厌氧(产酸相耐盐)、直接耐盐厌氧驯化,给出推荐与理由;(3)给出推荐路线的启动方案与失效判据。",
         kp="1.抑制等级:约 10 g/L 起轻度抑制、20-35 g/L 中度(可驯化)、>35-40 g/L 重度(活性显著下降);2.比较:稀释耗水量大且降低容积负荷;两相厌氧可让产酸相先行缓冲盐度与酸化,产甲烷相负荷降低;直接驯化周期长(2-3 个月)但长期最优;推荐两相+耐盐驯化组合;3.启动:接种耐盐消化污泥、盐度 0.5%/周逐步提升、监测 VFA/碱度/甲烷含量;失效判据:VFA/碱度>0.4 或甲烷含量骤降 10 天不恢复则回退盐度",
         ideal="抑制等级判断:文献量级为 NaCl 约 10 g/L 起对产甲烷出现轻度抑制,20-35 g/L 为中度抑制(可经驯化适应),超过约 35-40 g/L 活性显著下降;该废水 40 g/L 处于中-重度边界,不宜直接常规厌氧。三种路线比较:①稀释后常规厌氧需大量稀释水、容积负荷被摊薄,经济性差;②两相厌氧将产酸相前置,产酸菌耐盐性强,可缓冲盐度与有机酸冲击,产甲烷相进水已酸化、负荷可控;③直接耐盐驯化省水但启动周期长达 2-3 个月且初期失败率高。推荐两相厌氧并在产甲烷相同步耐盐驯化(可辅以甜菜碱过渡)。启动方案:接种耐盐颗粒/消化污泥,盐度以每周 ≤0.5% 幅度提升,逐日监测 VFA、碱度、甲烷含量与 COD 去除率;失效判据:VFA/碱度比持续 >0.4、沼气甲烷含量骤降且 10 天内不恢复,则回退一档盐度并延长驯化。",
         cat="Anaerobic digestion, Salinity acclimation, 环境工程-能源",
         ref="Oren 2008(高盐微生物综述)；Metcalf & Eddy(5th ed.)厌氧抑制章节"),
    dict(id="q-206", tag="脱氮", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="海水冲厕城市污水(如滨海城市,盐度约 1.5-2%)的主流脱氮工艺应如何设计?请按以下步骤完整作答:(1)分析该盐度对常规硝化反硝化与 PN/A 两条路线的影响差异;(2)给出推荐工艺路线与盐度管理要点;(3)说明剩余污泥处置需注意的盐度问题。",
         kp="1.影响差异:1.5-2% 盐度对已驯化硝化菌影响有限但对 NOB 有选择性抑制,反而有利于 PN;常规全程反硝化碳源需求高且高盐下效率下降;PN/A 更契合;2.推荐:主流 PN/A+盐度驯化,辅以 GB 等溶质在冲击期投加;监测 NAR、NRR;3.污泥:含盐污泥脱水性能变化(胞内 K+/Na+ 与 EPS),土地利用盐分限制,焚烧/填埋权衡",
         ideal="影响差异:1.5-2%(15-20 g/L)盐度下,经驯化的 AOB 可维持活性而 NOB 被选择性抑制,恰好落在有利短程硝化的窗口,使 PN/A 路线获益;常规硝化反硝化路线则面临反硝化碳源利用率下降、整体脱氮效率受抑的问题。推荐路线:主流 PN/A,启动期进行盐度梯度驯化(0.5%/步、每梯度 ≥7 个 HRT),盐度冲击期(台风季、潮位异常)辅以 0.5-1 mM 甜菜碱过渡,日常监测 NAR、NRR、出水三氮与污泥沉降性。污泥处置:海水冲厕污泥胞内富集 Na+/K+ 与 Cl-,絮体 EPS 组成改变影响脱水药剂选择;土地利用受施用量盐分总量约束,滨海厂可权衡焚烧或与低盐污泥混合处置。",
         cat="PN/A, Salinity acclimation, Wastewater treatment, 环境工程-脱氮",
         ref="10.1016/j.jwpe.2022.102959 Enhanced nitrogen removal of single stag；10.1016/j.scitotenv.2022.158221 Mitigating the detrimental effects of sa"),
    dict(id="q-207", tag="脱氮", topic="环境工程与能源", diff="中等", qt="E 环境工程/能源",
         q="某水产加工废水盐度 3-8% 波动、COD 8 g/L、TN 300 mg/L,请设计处理工艺链。请按以下步骤完整作答:(1)给出预处理-生化-深度处理的工艺链及各单元承担的功能;(2)说明生化单元的盐度管理策略(均衡、驯化、稀释的取舍);(3)给出全链验收指标。",
         kp="1.工艺链:格栅/隔油/混凝气浮预处理(除 SS 与油脂)-水解酸化(提高可生化性)-耐盐硝化反硝化或 PN/A 生化-深度脱氮(如硫自养反硝化滤池);2.盐度管理:设调节池均衡盐度波动,生化按上限盐度驯化,仅在超限峰值守稀释;避免连续大比例稀释推高水耗;3.验收:出水 NH4⁺/TN/COD 达标,TN≥80% 去除,硝化速率稳定,连续 ≥30 天",
         ideal="工艺链设计:预处理采用格栅+隔油+混凝气浮去除 SS、油脂与部分胶体蛋白;水解酸化单元提高废水可生化性并缓冲有机负荷;生化核心采用耐盐驯化的硝化反硝化(或 PN/A)反应器,盐度驯化目标按上限 8% 分级实施(0.5%/步,每梯度 ≥7 个 HRT);深度处理设硫自养反硝化滤池保障 TN 达标(无需外加碳源)。盐度管理:设置足够容积调节池均衡 3-8% 的盐度波动,生化系统按上限盐度驯化、按波动中值运行,仅在峰值超限时段少量稀释,避免连续大比例稀释推高水耗与容积负荷。验收指标:出水 NH4⁺-N、TN、COD 达排放标准,TN 去除率 ≥80%,比硝化速率与 NRR 稳定,连续流运行 ≥30 天,记录盐度-性能对应曲线。",
         cat="Wastewater treatment, Salinity acclimation, 环境工程-脱氮",
         ref="10.1016/j.biortech.2020.123784 Enhancement of pollutants removal from s；Metcalf & Eddy(5th ed.)工艺链设计"),
    dict(id="q-208", tag="污泥", topic="环境工程与能源", diff="中等", qt="E 环境工程/能源",
         q="高盐如何通过 EPS 介导恶化活性污泥的沉降与絮凝性能,如何改善?请按以下步骤完整作答:(1)阐明盐度→EPS 组成与电荷变化→絮体解体/压缩的因果链;(2)给出改善措施(溶质调控、生物强化、工艺参数);(3)给出 SVI 与絮体粒径的评价方案。",
         kp="1.因果链:高盐使胞外多糖/蛋白比例与官能团电荷改变,二价阳离子桥被 Na+ 置换,絮体静电排斥增大、结构松散,SVI 升高;2.措施:投加 GB/海藻糖维持微生物胞内稳态减少 EPS 变性,补充 Ca2+/Mg2+ 恢复桥联,生物强化促 EPS 分泌菌,控制污泥负荷;3.评价:SV30/SVI 逐日,激光粒度测粒径分布,镜检丝状菌,设对照 3 平行",
         ideal="因果链:盐度升高改变 EPS 中蛋白质/多糖比例与官能团电离状态,高浓度 Na+ 将 EPS 分子间及絮体间的 Ca2+/Mg2+ 桥置换,削弱架桥与吸附,絮体表面电荷升高、静电排斥增大,宏观表现为絮体细化、沉降压缩变慢、SVI 恶化,严重时污泥膨胀随丝状菌增殖叠加。改善措施:①溶质调控——投加 GB/海藻糖维持菌体胞内渗透稳态,减少为应对盐胁迫而发生的 EPS 过量分泌与变性;②补充二价阳离子(Ca2+/Mg2+,按 Ca/N 比投加)恢复桥联;③生物强化引入耐盐促絮凝菌;④控制 F/M 与 DO,避免冲击负荷。评价方案:逐日 SV30 与 SVI、激光粒度仪测粒径分布(关注 <50 μm 细颗粒占比)、显微镜观察絮体与丝状菌丰度,设无措施对照组,每组 3 平行,连续流 ≥30 天。",
         cat="Activated sludge, EPS, Compatible solutes, 环境工程-污泥",
         ref="10.1016/j.ese.2024.100406 Glycine betaine modulates extracellular；10.1016/j.jes.2023.10.0271001-0742 Effects of salinity and betaine addition"),
    dict(id="q-209", tag="污泥", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="高盐 MBR 运行中膜污染如何演变,与溶质调控有何关联?请按以下步骤完整作答:(1)描述盐度→EPS/SMP 组成变化→滤饼层与凝胶层污染→TMP 增速的链条;(2)给出以溶质调控为核心的缓解方案与膜清洗策略;(3)给出跨膜压差与膜通量恢复率的评价方案。",
         kp="1.链条:高盐下 EPS 与 SMP 中蛋白/多糖比改变,胞外溶质与胶体结合形成凝胶层,滤饼层孔隙率下降,TMP 增速加快;2.缓解:GB 调控 EPS 组成(蛋白/多糖比回落)、优化污泥龄与错流流速、惰性载体降低污泥比阻;清洗:碱洗+柠檬酸/NaClO 周期维护;3.评价:TMP 增速(kPa/d)、通量恢复率(>90%)、EPS/PN-PS 比跟踪,对照 3 平行",
         ideal="污染演变链条:盐度升高促使微生物分泌更多 SMP 并改变 EPS 的蛋白/多糖比,胞外相容性溶质与小分子胶体在膜面浓差极化层中交联形成致密凝胶层,叠加滤饼层孔隙率下降,宏观表现为 TMP 增速加快、清洗周期缩短。缓解方案:以溶质调控为核心——投加 GB 维持胞内稳态、使 EPS 组成回归正常区间(蛋白/多糖比回落),同时优化污泥龄(15-20 d)与错流流速、可投加聚氨酯载体降低污泥比阻;清洗策略采用周期性在线化学清洗(NaClO 碱洗+柠檬酸)与离线深度清洗结合,避免 TMP 越限后不可逆污染。评价:TMP 日增速(kPa/d)、清洗后膜通量恢复率(目标 >90%)、逐月 EPS 与 SMP 的 PN/PS 比跟踪,设无投加对照组,3 平行。",
         cat="Membrane fouling, MBR, EPS, Compatible solutes, 环境工程-污泥",
         ref="10.1016/j.jwpe.2024.105076 Impacts of electric field coupled membra；10.1016/j.jenvman.2023.118717 Impact of salinity on anaerobic ceramic；10.1016/j.ese.2024.100406 Glycine betaine modulates extracellular"),
    dict(id="q-210", tag="脱氮", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="某 anammox 反应器遭盐度从 2%骤升至 6%的冲击,请给出分级响应决策流程。请按以下步骤完整作答:(1)将冲击响应分为即时/中期/长期三级,给出每级的判据与动作(含'逆转剂'选择);(2)说明甜菜碱/海藻糖作为逆转剂的作用机制与投加要点;(3)给出恢复期判据与再次提盐的前提条件。",
         kp="1.分级:即时(24 h 内)降低进水负荷、投加逆转剂、开启稀释;中期(1-7 天)若 NRR 恢复<50%则延长 HRT、补种污泥;长期(>7 天)重建盐度驯化梯度;2.逆转剂:甜菜碱/海藻糖帮助胞内渗透再平衡与蛋白复性,冲击后 0.5-1 mM 起投,连续 3-5 天;3.恢复判据:NRR 恢复至冲击前 ≥80% 且稳定 7 天方可再次提盐,且提盐幅度减半",
         ideal="分级响应:①即时(24 h 内)——降低进水氮负荷 30-50%、启用稀释或回流缓冲,同步投加'逆转剂'(甜菜碱/海藻碱,0.5-1 mM 起投,连续 3-5 天),监测 NRR 与三氮;②中期(1-7 天)——若 NRR 恢复不足冲击前 50%,延长 HRT、提高污泥浓度或补充外源 anammox 污泥,排查 NOB 与异养菌增殖;③长期(>7 天)——按 0.25-0.5%/步重建盐度驯化梯度,每梯度以 NRR≥90% 恢复为进阶判据。逆转剂机制:盐冲击造成渗透失衡与酶(联氨合酶/脱氢酶)失活,甜菜碱/海藻糖作为相容性溶质帮助胞内渗透压再平衡、稳定蛋白与膜结构并促进复性,投加宜早(冲击后立即)、剂量经小试标定、避免长期依赖。恢复判据与再提盐前提:NRR 恢复至冲击前 ≥80% 且连续稳定 7 天、污泥沉降性与 EPS 指标正常,方可提盐,且幅度减半、监测加密。",
         cat="Anammox, Salt shock, Compatible solutes, 环境工程-脱氮",
         ref="10.1016/j.scitotenv.2019.07.215 Impacts of salt shocking and the selecti；10.1016/j.synbio.2026.04.016 Data-driven optimization of salt shock f"),
    dict(id="q-211", tag="脱氮", topic="环境工程与能源", diff="复杂", qt="E 环境工程/能源",
         q="高盐为什么会加剧反硝化过程 N2O 的累积,如何缓解?请按以下步骤完整作答:(1)阐明盐度对 nosZ(与其他反硝化还原酶 Nar/Nir/Nor)差异化抑制导致 N2O 累积的机制;(2)给出缓解措施(溶质、电子供体、运行参数);(3)给出 N2O 减排效果的评价方案。",
         kp="1.机制:高盐对各还原酶抑制程度不同,末端还原酶 nosZ 对盐度最敏感,N2O 还原受阻而前步 Nar/Nir/Nor 仍产 N2O,净累积增加;2.缓解:投加 GB/海藻糖保护 nosZ 构象,保证电子供体充足(碳源/S),控制 pH 中性与避免亚硝积累;3.评价:顶空-GC/微电极测 N2O 通量,硝酸盐/亚硝去除率同步,对照组 3 平行",
         ideal="机制:反硝化四步还原酶(Nar/Nir/Nor/Nos)对高盐的敏感性不同,末端 N2O 还原酶 nosZ 含铜中心、对盐度与渗透胁迫最敏感,活性率先下降;而前序酶仍持续将 NO3⁻/NO2⁻还原产生 N2O,产出-消耗失衡造成 N2O 净累积。缓解措施:①投加 GB/海藻糖等相容性溶质保护 nosZ 与胞内铜伴侣蛋白构象;②保证电子供体充足且分配合理(碳源足量但不过量、硫体系保证 S/N 比),避免末端电子竞争;③运行上控制 pH 中性、避免亚硝积累(FNA 抑制 nosZ)与低 C/N。评价方案:密闭顶空-GC 或微电极阵列测定液相/气相 N2O 通量,同步硝酸盐还原率、亚硝积累与 N2/N2O 比,设无溶质对照,每组 3 平行,连续流复验。",
         cat="N2O mitigation, Denitrification, Compatible solutes, 环境工程-脱氮",
         ref="10.1007/s10532-012-9542-0 Biological denitrification of brine: the；10.1016/j.watres.2026.125764 Ectoine modulates mixotrophic denitrific"),
    dict(id="q-212", tag="厌氧消化", topic="环境工程与能源", diff="中等", qt="E 环境工程/能源",
         q="相容性溶质投加对高盐厌氧消化与高盐好氧脱氮两类体系的意义有何异同?请按以下步骤完整作答:(1)比较两类体系受盐抑制的关键菌群与功能酶差异;(2)比较适用的溶质种类与投加策略差异;(3)给出两体系各自的效果评价指标。",
         kp="1.菌群差异:厌氧消化关键为产甲烷古菌(F430/CoM 代谢),好氧脱氮为硝化/反硝化/anammox 菌(AMO/HAO、Nar/Nir、联氨合酶);2.溶质策略:两类均可用 GB/海藻糖,厌氧体系兼可考虑谷氨酸;投加均应短期过渡、避免长期依赖;3.指标:厌氧看沼气产率/甲烷含量/VFA;好氧脱氮看 NRR/NAR/三氮/N2O",
         ideal="关键菌群与酶差异:高盐厌氧消化的功能核心是产甲烷古菌,抑制表现为乙酰裂解与氢营养通路(F430、CoM 辅因子周转)受阻、VFA 累积;高盐好氧脱氮的功能核心是硝化菌(Amo/Hao)、反硝化菌(Nar/Nir/Nor/Nos)或 anammox 菌(联氨合成/氧化),抑制表现为氨氧化速率与 NRR 下降、N2O 累积。溶质策略异同:两类体系均可用 GB/海藻糖做渗透保护与蛋白稳定,厌氧体系还可利用谷氨酸兼作氮源;投加均定位为短期过渡(启动/冲击期),长期均应转向耐盐驯化或功能菌共培养,剂量均需小试标定(0.5-2 mM 量级起)。评价指标:厌氧消化看日产沼气量、甲烷含量、VFA/碱度;好氧脱氮看 NRR/NAR、出水三氮、N2O 排放,均设无投加对照并做连续流验证。",
         cat="Anaerobic digestion, Compatible solutes, 环境工程-脱氮, 环境工程-能源",
         ref="10.1016/j.biortech.2014.06.015 Enhancement of anammox activity by addit；Oren 2008(溶质通用机制)"),
    # ---------- T7 培养基设计(7 题) ----------
    dict(id="q-221", tag="脱氮", topic="微生物调控", diff="中等", qt="T7 培养基设计",
         q="请为硫自养反硝化(SAD)菌群富集设计培养基/进水方案(目标盐度 2.0%,基质 NO3⁻ 约 300 mg/L)。请按以下步骤完整作答:(1)给出培养基配方(电子供体、氮源、碱度、微量元素)与关键约束;(2)用给定数值校验 S/N 当量比与碱度是否满足(给出计算过程);(3)给出盐度梯度驯化方案与富集终点判据。",
         kp="1.配方:单质硫(S0)作电子供体、NaNO3 氮源(约 2.14 mmol/L)、NaHCO3 补碱度(约 3.14 g/L 维持 pH)、NH4Cl 少量氮源、微量元素液、NaCl 梯度至 20 g/L;2.校验:脱氮当量 S/N≈2.47 g S/g NO3-N(按硫自养计量式),300 mg/L NO3-N 需约 0.74 g/L S0;碱度需求约 4.57 g CaCO3/g NO3-N 由 NaHCO3 提供;3.驯化:0.5%/步,每梯度 ≥7 个 HRT,以硝酸盐还原率 ≥90% 进阶;终点:Thiohalomonas 等硫反硝化菌丰度占优且 N2O 低",
         ideal="培养基配方:电子供体用单质硫(S0 或硫铁复合),氮源 NaNO3(300 mg/L NO3⁻-N 折合约 2.14 mmol/L),辅以少量 NH4Cl 供同化,碱度用 NaHCO3(约 3.14 g/L,兼无机碳源),基础无机盐培养基(KH2PO4、MgSO4 等)+微量元素液(含 Mo,钼是硝酸盐还原酶辅因子),NaCl 按梯度驯化至 20 g/L。当量校验:硫自养反硝化计量式下每还原 1 g NO3-N 约需 2.47 g S0,故 300 mg/L NO3-N 需投加约 0.74 g/L 硫磺,过量 10-20% 保障完全还原;产碱?实际 SAD 产酸(每 g NO3-N 约需 4.57 g CaCO3 当量碱度),由 NaHCO3 按化学计量补足并维持 pH 7.0-7.5。驯化方案:盐度 0.5%/步、每梯度稳定 ≥7 个 HRT 且硝酸盐还原率 ≥90% 方可进阶;富集终点以 Thiohalomonas/硫杆菌属相对丰度占优(≥20%)、N2O 排放低于检测限、连续 30 天性能稳定为准。",
         cat="Sulfur-driven denitrification, 培养基设计, Salinity acclimation",
         ref="10.1016/j.cej.2024.154266 Salinity responsive mechanisms of sulfur；10.1016/j.biortech.2025.132667 Sulfide-based autotrophic denitrificatio"),
    dict(id="q-222", tag="脱氮", topic="微生物调控", diff="中等", qt="T7 培养基设计",
         q="请为主流低基质条件下的 anammox 菌维持培养设计进水方案( NH4⁺ 与 NO2⁻ 各约 30-50 mg/L,目标盐度 1.0%)。请按以下步骤完整作答:(1)给出进水配方与关键约束(NO2⁻:NH4⁺ 比、DO 抑制、COD/TN);(2)校验基质比并说明低基质下的 SAA 维持策略(饥饿-恢复策略);(3)给出维持培养的监测与衰退判据。",
         kp="1.配方:人工进水 NH4Cl+NaNO2 按 1.32:1(摩尔)配比、KHCO3 碱度、微量元素(Ni/Se/Fe)、NaCl 至 10 g/L;DO <0.1 mg/L、COD/TN<1;2.校验:30 mg/L NH4 对应 NO2 约 39.6 mg/L(1.32 倍);低基质 SAA 维持:周期性短时高基质'脉冲喂养'+控制 HRT 防洗出;3.监测:NRR、三氮、污泥红色/活性;衰退判据:NRR 连续 2 周下降 >30% 或 NO3 产生比异常",
         ideal="进水配方:NH4Cl 与 NaNO2 按 anammox 化学计量 NO2⁻:NH4⁺≈1.32:1(摩尔)配制,基质各 30-50 mg/L 级;以 KHCO3/NaHCO3 提供碱度与无机碳,补充含 Ni、Se、Fe 的微量元素液(anammox 酶系辅因子),NaCl 按目标调至 10 g/L。关键约束:DO 控制在 0.1 mg/L 以下(严防氧抑制与 NOB 增殖),有机物 COD/TN<1 以防异养菌竞争基质。校验:30 mg/L NH4⁺-N 对应配 NO2⁻-N 约 39.6 mg/L(1.32 倍),按进水体积折算药品量;低基质维持策略:采用周期性短时高基质'脉冲喂养'(每日 2-4 h 提升至 100 mg/L 级)刺激 SAA 维持,控制 HRT 防止菌体洗出,定期补充少量 anammox 颗粒污泥。监测与衰退判据:逐日三氮与 NRR、污泥颜色(红褐)与沉降性;NRR 连续两周降幅 >30%、NO3⁻ 产生比偏离计量比或污泥发黑,即判衰退,需恢复脉冲喂养并排查 DO/温度异常。",
         cat="Anammox, 培养基设计, Mainstream",
         ref="10.1021/acs.est.2c01104 Glutamate Enhances Osmoadaptation of Ana；L0410 Salinity Tolerance and Osmoadaptation St"),
    dict(id="q-223", tag="脱氮", topic="微生物调控", diff="中等", qt="T7 培养基设计",
         q="请为嗜盐产 ectoine 菌(以 Halomonas 为代表)的选择性富集设计培养基(目标盐度 15%,作溶质供体菌种源)。请按以下步骤完整作答:(1)给出配方要点(盐基础、碳源、C/N、诱导条件)与选择压设计;(2)说明 ectoine 合成的诱导逻辑(盐度梯度、生长相)与产量提升要点;(3)给出富集终点判据与污染控制。",
         kp="1.配方:高盐基础培养基(NaCl 150 g/L 级、MgSO4/KCl/蛋白胨微量)、碳源谷氨酸钠或乙酸钠(C/N 适中)、通气良好;选择压:15% 盐抑制非嗜盐菌;2.诱导:ectoine 随外盐度上调积累,采对数后期-稳定期菌;碳源充足时产率更高,可分段盐度刺激;3.终点:Halomonas 相对丰度 ≥60%、HPLC 检出胞内 ectoine ≥50 mg/g DCW;防污染:严格灭菌与专属接种",
         ideal="培养基配方:以高盐矿物培养基为基础(NaCl 至 150 g/L、MgSO4·7H2O、KCl、微量蛋白胨或酵母粉),碳源选谷氨酸钠(兼氮源,利于 ectoine 前体谷氨酸供应)或乙酸钠,C/N 控制在适中偏低区间避免杂菌过快增殖;通气充足供好氧生长。选择压设计:15% 盐度本身即强选择压,中度嗜盐的 Halomonas 优势生长而常规异养菌被抑制。ectoine 诱导逻辑:ectABC 操纵子表达随外源渗透压上调,胞内 ectoine 在对数后期至稳定期大量积累;工程上采用'两段法'——先在 10% 盐度快速增殖,再提至 15-18% 诱导积累,并保证碳源充足。富集终点:16S 测序确认 Halomonas 相对丰度 ≥60%,HPLC 检测胞内 ectoine 含量 ≥50 mg/g DCW(干菌),连续三代稳定传代;污染控制:全流程严格灭菌、专属接种与镜检/平板双检。",
         cat="Compatible solutes, Bioaugmentation, 培养基设计, Halomonas",
         ref="L0430 Glycine Betaine and Ectoine Are the Majo；10.1016/j.watres.2026.126010 Freshwater anammox bacteria leverage mix"),
    dict(id="q-224", tag="脱氮", topic="微生物调控", diff="中等", qt="T7 培养基设计",
         q="请为 AOB(氨氧化菌)的耐盐驯化设计培养基/进水方案(起始盐度 0.5%,目标 3.0%,进水 NH4⁺ 200 mg/L)。请按以下步骤完整作答:(1)给出配方要点(基质、碱度、pH、微量元素)与碱度化学计量校验;(2)给出盐度梯度驯化方案(步长、判据)与 FA 双重抑制作用说明;(3)给出富集终点判据与 NOB 防控。",
         kp="1.配方:NH4Cl 基质 200 mg N/L、NaHCO3 碱度(7.14 g CaCO3/g N 化学计量)维持 pH 7.5-8.0、微量元素(Cu);2.驯化:0.5%/步、每梯度 ≥7 个 SRT 且氨氧化速率恢复 ≥90% 进阶;说明高 pH/高 NH4 下 FA 抑制 NOB 的量级与 AOB 耐受差异;3.终点:NAR ≥80%、AOB 丰度占优、比氨氧化速率稳定;NOB 防控:低 DO+FA 抑制+及时排泥",
         ideal="配方要点:NH4Cl 提供 200 mg/L NH4⁺-N 基质,碱度按硝化产酸化学计量补 NaHCO3——每氧化 1 g NH4⁺-N 消耗约 7.14 g CaCO3 当量碱度,200 mg/L 即需约 1.43 g/L CaCO3 当量(以 NaHCO3 计约 1.7 g/L),维持 pH 7.5-8.0;补充微量元素(尤其 Cu,氨单加氧酶辅因子)与磷源;NaCl 从 5 g/L 起步。驯化方案:盐度 0.5%/步,每梯度维持 ≥7 个污泥龄且比氨氧化速率恢复至上一梯度 ≥90% 再进阶;同时利用 FA 游离氨抑制 NOB——pH 偏碱、NH4⁺ 200 mg/L 下 FA 约处 NOB 抑制区间(>0.1-1.0 mg N/L 视菌而异)而对 AOB 耐受更高,实现选择性富集。终点判据:NAR(亚硝积累率)≥80%、AOB(Nitrosomonas)丰度占优、比氨氧化速率连续 2 周稳定;NOB 防控:控制 DO 1-1.5 mg/L、维持 FA 抑制窗口、及时排泥缩短 SRT 淘汰长世代 NOB。",
         cat="Nitrification, Salinity acclimation, 培养基设计",
         ref="10.1021/acs.est.3c07324 Salinity Tolerance and Osmoadaptation St；Metcalf & Eddy(5th ed.)硝化碱度化学计量"),
    dict(id="q-225", tag="脱氮", topic="微生物调控", diff="中等", qt="T7 培养基设计",
         q="请为短程反硝化(PD)菌 Thauera 富集设计培养基(目标:NO3⁻→NO2⁻ 转化率 ≥90%,盐度 2.0%)。请按以下步骤完整作答:(1)给出配方要点(碳源选择、COD/NO3⁻ 比、氮磷)与关键约束;(2)校验 C/N 并说明为何碳源量是 PD 成败关键(不足→还原停滞,过量→完全反硝化);(3)给出富集终点判据与 N2O 防控。",
         kp="1.配方:碳源乙酸/乙醇(COD/NO3-N 约 2.5-3.5)、KNO3 基质、磷盐、微量元素、NaCl 20 g/L;约束:精准限碳是实现 NO2 累积的核心;2.校验:按 300 mg/L NO3-N,投 COD 约 750-1050 mg/L;碳不足还原停在 NO3,过量则越过 NO2 完全还原;3.终点:NTR ≥90%、NO2 积累率高、Thauera 丰度占优;N2O 防控:pH 中性、避免亚硝过度积累",
         ideal="配方要点:碳源选乙酸或乙醇(Thauera 利用性好、代谢路径短),KNO3 提供 NO3⁻ 基质(约 300 mg/L NO3⁻-N 级),按微生物需求配磷盐(BOD5:N:P≈100:5:1 量级)与微量元素液,NaCl 调至 20 g/L;核心约束是碳源精准限量——COD/NO3⁻-N 控制在约 2.5-3.5 的窄窗口。C/N 校验:300 mg/L NO3⁻-N 对应投加 COD 约 750-1050 mg/L(以乙酸计折算药品量);碳源不足时 NO3⁻ 还原停滞、NTR 上不去,过量则 NO2⁻ 被继续还原为 N2/N2O,亚硝积累失败,故需小试标定精确窗口并采用分批/脉冲投加。富集终点:NTR(硝酸盐→亚硝转化率)≥90%、NO2⁻ 积累率稳定、16S 确认 Thauera 丰度占优;N2O 防控:维持 pH 中性、避免 NO2⁻ 过度积累(FNA 抑制 nosZ),监控气相 N2O。",
         cat="Partial denitrification, 培养基设计, Thauera",
         ref="10.1016/j.watres.2026.125764 Ectoine modulates mixotrophic denitrific；10.1016/j.jhazmat.2026.143139 Restoring partial denitrification under"),
    dict(id="q-226", tag="脱氮", topic="微生物调控", diff="中等", qt="T7 培养基设计",
         q="请为'产 GB 供体菌+anammox'共培养体系设计维持培养基(供体为耐盐 Halomonas,目标盐度 2.0%,供体丰度维持 ≥10%)。请按以下步骤完整作答:(1)给出配方要点(双基质:供体碳源限量+anammox 基质)与 COD/TN 约束;(2)说明交叉喂养设计逻辑(供体产 GB 释放-anammox 摄取或共享)与限量碳源的选择;(3)给出共培养维持判据与失衡调整。",
         kp="1.配方:anammox 基质 NH4+/NO2- 1.32:1+Halomonas 限碳(微量乙酸钠,COD/TN<1)+高盐基础盐+微量元素;2.交叉喂养:供体在高盐下合成并外泌/死亡释放 GB,anammox 经现存转运摄取;碳源限量防异养菌失控又保供体活性;3.判据:供体丰度 10-30% 区间、NRR 稳定、GB 检出;失衡:供体<10% 补碳脉冲,>40% 降碳防异养化",
         ideal="配方要点:以 anammox 人工进水为基底(NH4Cl/NaNO2 按 1.32:1 摩尔配比、KHCO3 碱度、Ni/Se/Fe 微量元素、NaCl 至 20 g/L),叠加供体菌限碳营养——微量乙酸钠(或谷氨酸钠,兼 GB 前体)使 COD/TN<1,既供 Halomonas 维持代谢又不致异养菌爆发。交叉喂养设计:Halomonas 在高盐下合成 GB,通过主动外泌与菌体周转(死亡裂解)向环境释放 GB/ectoine,anammox 菌经其转运系统(或经互补菌提供的胞外溶质池)摄取,实现溶质共享;碳源选择以'仅供维持、不足以高增殖'为原则,谷氨酸钠还可直接为体系补充氮型溶质前体。维持判据:16S/定量 PCR 监测 Halomonas 相对丰度维持 10-30% 区间、NRR 稳定(周波动 <10%)、胞外 GB 可检出(HPLC);失衡调整:供体 <10% 时脉冲补碳 1-2 mg/L 乙酸并微降盐度,供体 >40% 时停止补碳、提高曝气/水力剪切控制生物量,警惕体系异养化。",
         cat="Bioaugmentation, Compatible solutes, Anammox, 培养基设计",
         ref="L0430 Glycine Betaine and Ectoine Are the Majo；L0041 Deciphering performance and microbial ch"),
    dict(id="q-227", tag="污泥", topic="微生物调控", diff="中等", qt="T7 培养基设计",
         q="请为高盐好氧颗粒污泥(目标盐度 2.0%)的培养设计进水与运行方案。请按以下步骤完整作答:(1)给出进水配方要点与颗粒化驱动条件(水力剪切、沉降时间选择压、 Feast-Famine);(2)说明盐度在颗粒化中的双面作用(促密实 vs 抑活性)与管理;(3)给出颗粒成熟判据与培养终点。",
         kp="1.配方:人工废水(碳/氮/磷+微量元素+NaCl 梯度)、表面气速 ≥1.2 cm/s、沉降时间从 10-15 min 递减至 2-5 min、低碳期饥饿;2.双面作用:适度盐促 EPS 分泌与颗粒密实,过高盐抑活性与沉降;管理:0.5%/步驯化+GB 缓冲;3.判据:粒径 ≥200 μm、SVI30/SVI5<0.8、MLSS 稳定、去除率达标",
         ideal="进水与运行:人工废水(乙酸钠碳源、NH4Cl/磷盐按 BOD:N:P=100:5:1、微量元素液),NaCl 自 5 g/L 按 0.5%/步驯化至 20 g/L;反应器采用 SBR,表面气速 ≥1.2 cm/s 提供水力剪切,沉降时间由启动初 10-15 min 逐周递减至 2-5 min 形成选择压淘汰絮体,采用好氧 Feast-Famine(短时高负荷进食+缺氧饥饿)交替刺激 EPS 分泌与颗粒密实。盐度双面作用:适度盐胁迫促进微生物分泌 EPS、加快颗粒化并提高密实度;但超过菌群耐受窗后活性下降、颗粒解体风险上升——管理上以 0.5%/步梯度驯化、关键梯度辅以 0.5-1 mM GB 缓冲、监测 SVI 与破碎率。成熟判据:平均粒径 ≥200 μm 且分布稳定、SVI30/SVI5 <0.8、MLSS 与沉降污泥稳定、COD/TN 去除达标并维持 30 天,镜检颗粒轮廓清晰、无丝状菌优势。",
         cat="Aerobic granular sludge, Salinity acclimation, 培养基设计, 环境工程-污泥",
         ref="10.1016/j.jes.2023.10.0271001-0742 Effects of salinity and betaine addition；10.1016/j.biortech.2024.131758 Potential role of N-acyl homoserine lact"),
    # ---------- T5 菌株选择(4 题) ----------
    dict(id="q-231", tag="脱氮", topic="微生物调控", diff="中等", qt="T5 菌株选择",
         q="某 anammox 体系(目标盐度 3.0%)经基因组诊断:溶质摄取转运系统(BetT/ProP/ProU/Opu)全部缺失但合成途径部分保留。请推荐溶质供给方案。请按以下步骤完整作答:(1)给出供体菌或溶质供给方案并说明为何'跨喂'优先于'外源投加';(2)列出三条筛选依据(合成能力/盐度生态位/可定殖性);(3)给出富集与定殖验证要点。",
         kp="1.方案:互补菌跨喂为主(引入 Halomonas/Chromohalobacter 等产 ectoine/GB 菌),外源投加因转运缺失而效率受限,仅作小试对照;2.依据:合成能力(ectABC/betBA 齐全)、盐度生态位匹配(1-5% 适生)、可定殖性(能在反应器挂膜/持留,16S 网络同现);3.验证:16S/qPCR 回测供体丰度 ≥10%,HPLC 检出胞外 GB/ectoine,NRR 对比提升",
         ideal="供给方案:以'互补菌跨喂'为主——引入能合成 ectoine/GB 的耐盐菌(如 Halomonas elongata、Chromohalobacter salexigens),在体系内就地产生并释放相容性溶质;由于该 anammox 菌株溶质摄取转运系统全部缺失,直接外源投加溶质无法被有效摄取,仅作为小试对照验证。筛选三依据:①合成能力——候选菌 ectABC(ectoine)或 betBA(甜菜碱)基因齐全且高盐下高表达;②盐度生态位匹配——菌株适生盐度覆盖体系运行区间(1-5%),非极端嗜盐以免低盐段失活;③可定殖性——能在反应器生物膜/颗粒中持留增殖(文献 16S 共现网络或挂膜实验支撑)。验证要点:富集后 16S/qPCR 回测供体菌相对丰度 ≥10%,HPLC 检出胞外 GB/ectoine(≥0.1 mM 级),体系 NRR 较无供体对照显著提升,连续流维持 ≥30 天。",
         cat="Bioaugmentation, Compatible solutes, Anammox, 菌株选择",
         ref="L0430 Glycine Betaine and Ectoine Are the Majo；L0420 Interspecific competition and adaptation"),
    dict(id="q-232", tag="脱氮", topic="微生物调控", diff="中等", qt="T5 菌株选择",
         q="为高盐(目标 2.0%)主流短程硝化(PN)系统选择耐盐辅菌(与 AOB 共生、提供渗透保护的伴生菌)。请按以下步骤完整作答:(1)给出候选菌与选择逻辑;(2)列出三条筛选依据;(3)给出共生效果验证要点。",
         kp="1.候选:耐盐产溶质好氧菌(如 Halomonas 属中低盐适生种、Marinobacter 等),与 AOB 需氧/ pH 生态位兼容,不争夺基质(无机自养/低有机需求);2.依据:产 GB/海藻糖能力、1-3% 盐度适生、非硝化菌不产生 NO2 竞争、可定殖;3.验证:AOB 比活性提升对比、辅菌丰度、NAR 维持",
         ideal="候选菌选择:耐盐产溶质好氧菌,优先 Halomonas 属的低-中盐适生种及 Marinobacter 等海洋伴生菌——它们与 AOB 在需氧环境与近中性-弱碱 pH 上生态位兼容,代谢以有机物异养为主但不与 AOB 争夺 NH4⁺/NO2⁻ 基质,可在高盐下合成 GB/海藻糖并向环境释放,为 AOB 提供渗透保护。筛选三依据:①产溶质能力(GB/海藻糖基因齐全且高盐诱导表达);②盐度生态位匹配(1-3% 适生,与体系一致);③可定殖性与安全性(能在生物膜持留、非致病、不过度增殖引发污泥膨胀)。验证要点:设投加/不投加对照组,比较 AOB 比氨氧化速率与 NAR 维持率,qPCR/16S 跟踪辅菌丰度(目标 5-20%),HPLC 检出胞外溶质,连续流 ≥30 天确认 NAR 稳定。",
         cat="Bioaugmentation, Compatible solutes, Nitrification, 菌株选择",
         ref="10.1021/acs.est.3c07324 Salinity Tolerance and Osmoadaptation St；L0419 Rapid adaptation and enrichment of salt-"),
    dict(id="q-233", tag="脱氮", topic="微生物调控", diff="中等", qt="T5 菌株选择",
         q="为高盐硫自养反硝化(SAD)体系(目标盐度 3.0%)选择'供溶质硫氧化菌'。请按以下步骤完整作答:(1)给出候选菌与选择逻辑;(2)列出三条筛选依据;(3)给出功能验证要点。",
         kp="1.候选:Thiohalomonas denitricans 等嗜盐硫氧化反硝化菌(兼具脱氮功能与溶质积累),或 Halomonas+硫杆菌组合;2.依据:硫氧化+反硝化双功能、3% 盐度适生、产 ectoine/GB 能力、可定殖;3.验证:硝酸盐还原率与硫化物氧化率同步、胞内溶质检出、N2O 低",
         ideal="候选菌选择:优先 Thiohalomonas denitricans 等中度嗜盐的硫氧化反硝化菌——它天然栖息于高盐环境,兼具硫氧化与反硝化功能,胞内积累 ectoine/GB 自我保护并可外泌共享,实现'功能菌即供体';备选 Halomonas(供溶质)+硫杆菌(供功能)的组合方案。筛选三依据:①功能匹配——硫氧化(Hdr/Sox 途径)与反硝化(Nar/Nir)基因齐全,能以 S0 为电子供体还原 NO3⁻;②盐度生态位——3%(30 g/L)盐度处于其最适生长区间;③可定殖性——可在硫填料/生物膜上持留。功能验证:批次比较硝酸盐还原率与硫化物/单质硫氧化速率是否同步、胞内 ectoine/GB 的 HPLC 检出、N2O 排放低于对照,连续流 ≥30 天性能稳定。",
         cat="Sulfur-driven denitrification, Bioaugmentation, Compatible solutes, 菌株选择",
         ref="10.1016/j.cej.2024.154266 Salinity responsive mechanisms of sulfur；L0419 Rapid adaptation and enrichment of salt-"),
    dict(id="q-234", tag="污泥", topic="微生物调控", diff="中等", qt="T5 菌株选择",
         q="为高盐活性污泥/颗粒污泥体系选择'促 EPS 分泌功能菌'以维持絮体与颗粒结构。请按以下步骤完整作答:(1)给出候选菌类型与作用逻辑(耐盐且高产 EPS/信号分子);(2)列出三条筛选依据;(3)给出强化效果验证要点。",
         kp="1.候选:耐盐 EPS 高产菌(如 Zobellella、耐盐 Thauera/Zoogloea 类)及产 AHL 信号菌,促进群体感应与胞外多糖分泌;2.依据:EPS 产量(胞外多糖/蛋白)、盐度生态位、与原生菌群相容性(不致病不膨胀);3.验证:SVI 改善、粒径分布、EPS 组分(PN/PS)与 AHL 检出、对照组 3 平行",
         ideal="候选菌:耐盐且高产胞外聚合物的功能菌——包括耐盐 Thauera/Zoogloea 类(好氧颗粒形成的关键菌,分泌胞外多糖粘结基质)与产 AHL 群体感应信号的伴生菌(如耐盐的 Zobellella 类),两者通过'多糖骨架+信号协调'维持絮体与颗粒结构在高盐下的稳定。筛选三依据:①EPS 产量与组分——高盐培养下胞外多糖/蛋白产量高、组分利于架桥;②盐度生态位匹配——目标 1-3% 盐度下保持活性;③菌群相容性——非致病、不引发丝状菌膨胀、不与脱氮功能菌冲突(16S 共现网络或共培养验证)。验证要点:设投加组与对照组(各 3 平行),比较 SVI、絮体/颗粒粒径分布(激光粒度)、EPS 的 PN/PS 比与总量(苯酚-硫酸法/考马斯亮蓝)、AHL 信号分子检出(LC-MS),连续流观察结构稳定性 ≥30 天。",
         cat="Bioaugmentation, EPS, Aerobic granular sludge, 菌株选择, 环境工程-污泥",
         ref="10.1016/j.biortech.2024.131758 Potential role of N-acyl homoserine lact；10.1016/j.ese.2024.100406 Glycine betaine modulates extracellular"),
    # ---------- T10 场景推理(3 题) ----------
    dict(id="q-241", tag="脱氮", topic="微生物调控", diff="复杂", qt="T10 场景推理",
         q="对比两场景的盐度管理策略差异:场景 A 为滨海厂季节性海水入侵(雨季盐度 0.5%→2.5% 峰值,持续数周后回落);场景 B 为接纳高盐工业废水的恒定盐度提升改造(0.5%→2.5% 永久运行)。请按以下步骤完整作答:(1)拆解两场景的关键变量差异(峰值形态、菌群响应时间尺度、投资回收期);(2)分别给出针对性措施;(3)给出各自的验证与回退方案。",
         kp="1.差异:A 是反复瞬态冲击,核心是缓冲容量与恢复速度;B 是稳态迁移,核心是梯度驯化与种群重塑;A 适用临时性措施,B 适用永久性改造;2.A:调节池/在线盐度仪前馈稀释、冲击期 GB 投加、维持污泥浓度冗余;B:0.5%/步驯化+产溶质菌共培养+耐盐菌富集;3.A 验证:峰值期 NRR 保持率;B 验证:全盐度曲线达标;回退:A 回落即自愈,B 失稳回退一档盐度",
         ideal="关键变量差异:场景 A 是反复的瞬态冲击——峰值持续数周、回落后又重来,菌群来不及完成种群重塑,响应以生理调节(渗透保护)为主,设施投资的回收期短且需应对不确定性;场景 B 是一次性稳态迁移——菌群有充足时间经梯度驯化完成种群重塑(耐盐突变体/供体菌富集),措施可沉淀为永久性改造。针对性措施:A 场景设足够容积调节池+在线盐度仪前馈控制稀释,峰值期投加 GB(0.5-1 mM)做临时渗透保护,日常维持较高污泥浓度冗余与短 SRT 恢复力;B 场景按 0.5%/步、每梯度 ≥7 个 HRT 梯度驯化,引入产溶质菌共培养,逐步富集耐盐功能菌群并优化载体/颗粒化。验证与回退:A 以峰值期 NRR 保持率 ≥70%、恢复期 <7 天为合格,盐度回落后系统自愈无需回退;B 以全盐度曲线(0.5→2.5%)各梯度性能达标为准,任一梯度失稳(性能 2-3 天不恢复)即回退一档并延长驯化。",
         cat="Salinity acclimation, Compatible solutes, 场景推理, 环境工程-脱氮",
         ref="10.1016/j.scitotenv.2019.07.215 Impacts of salt shocking and the selecti；10.1016/j.scitotenv.2022.158221 Mitigating the detrimental effects of sa"),
    dict(id="q-242", tag="脱氮", topic="环境工程与能源", diff="复杂", qt="T10 场景推理",
         q="北方冬季某 PN/A 系统面临低温(12°C)+计划提盐(1.0%→2.0%)双重胁迫。请按以下步骤完整作答:(1)拆解低温与盐度对 PN 段与 A 段的交互抑制(谁先受限、如何叠加);(2)给出三种应对路线(提高污泥龄/局部加热/溶质投加+缓提盐)的权衡比较与推荐;(3)给出实施顺序与监测-回退方案。",
         kp="1.交互:低温先限 AOB 与 anammox 酶动力学(活性近乎减半),盐度再叠加渗透抑制,PN 段 NOB 可能因低温+盐度受抑反而利于短程;2.权衡:提高 SRT 零能耗但易 NOB 回潮+出水 NO3;局部加热能耗高但治本;缓提盐+GB 投加最稳妥但周期长;推荐缓提盐+SRT 优化组合,加热仅作保底;3.顺序:先低温适应(SRT/DO 调整)再缓提盐(0.25%/步);监测 NAR/NRR/三氮,失稳回退盐度并暂停提盐",
         ideal="交互抑制拆解:低温 12°C 下 AOB 氨氧化与 anammox 的酶动力学速率大幅下降(AOB 温度系数 θ≈1.1,每降 10°C 活性近乎减半),是第一限制因子;盐度在此之上叠加渗透抑制,PN/A 总体 NRR 可能跌至常温的 30-40%。有利面:低温+盐度对 NOB 的双重抑制反而巩固短程硝化,NAR 更易维持。三种路线权衡:①提高污泥龄/污泥浓度——零额外能耗,但长 SRT 有 NOB 回潮与出水 NO3⁻ 升高风险;②局部加热(仅 A 段提温至 15-20°C)——治本但能耗与投资高,冬季电耗显著;③缓提盐+溶质投加——将提盐幅度减半(0.25%/步)、每梯度加倍稳定时间,辅以 GB 0.5-1 mM 过渡,周期长但稳健。推荐 ①+③ 组合,②作为极端冬季保底。实施顺序:入冬前先完成 SRT/DO 调整使系统低温稳态,再启动缓提盐;全程监测 NAR、NRR、三氮与污泥活性(SAA);任一梯度性能 2-3 天不恢复即回退盐度、暂停提盐计划直至春末。",
         cat="PN/A, Salinity acclimation, Temperature, 场景推理, 环境工程-脱氮",
         ref="10.1016/j.jwpe.2022.102959 Enhanced nitrogen removal of single stag；Metcalf & Eddy(5th ed.)温度修正"),
    dict(id="q-243", tag="厌氧消化", topic="环境工程与能源", diff="复杂", qt="T10 场景推理",
         q="对比两类厌氧消化的盐度管理差异:场景 A 为高盐高氨鸡粪沼液(盐度 2%、NH4⁺ 3 g/L);场景 B 为市政污泥(盐度 0.3%、NH4⁺ 1 g/L)计划掺入 30% 高盐厨余。请按以下步骤完整作答:(1)拆解两场景的胁迫结构差异(盐-氨交互 vs 单盐胁迫、缓冲体系);(2)分别给出抑制缓解与运行策略;(3)给出各自的失稳预警指标与恢复路径。",
         kp="1.差异:A 是盐-氨双胁迫(游离氨抑制产甲烷+高渗),B 是单盐渐增且有机负荷/酸化风险更高;A 的 NH3 抑制随 pH 升高放大;2.A:稀释/氨吹脱预处理降游离氨、两相厌氧、GB 过渡;B:控制掺混比例渐进、产酸相缓冲、监测 VFA;3.预警:A 看 VFA/碱度与 NH3;B 看 VFA 陡升与甲烷含量;恢复:降负荷-停掺混-回退盐度",
         ideal="胁迫结构差异:场景 A 为盐-氨双重胁迫——2% 盐度造成渗透抑制的同时,3 g/L NH4⁺ 在消化 pH 偏碱条件下游离氨(NH3)浓度高,直接抑制产甲烷古菌(乙酰裂解途径尤其敏感),且两者抑制存在叠加放大;场景 B 为单盐渐增胁迫,主要风险来自厨余掺入带来的有机负荷冲击与酸积累(VFA 激增压垮产甲烷相),盐本身升幅温和。缓解与运行:A 场景优先降游离氨——稀释、氨吹脱或鸟粪石沉淀预处理,采用两相厌氧(产酸相耐盐耐氨先行)+GB 过渡投加;B 场景控制厨余掺混比例渐进提升(10%→30%,每级 ≥2 个 HRT),产酸相前置缓冲,维持碱度冗余。预警与恢复:A 以 VFA/碱度 >0.3-0.4、游离氨 >150-200 mg N/L、甲烷含量骤降为预警,恢复路径为降负荷+稀释降氨+回退盐度;B 以 VFA 陡升、丙酸积累、pH 下滑为预警,恢复路径为暂停掺混、降有机负荷、补碱度,稳定后再渐进重启。",
         cat="Anaerobic digestion, Ammonia inhibition, Salinity acclimation, 场景推理",
         ref="Oren 2008(盐胁迫)；Metcalf & Eddy(5th ed.)(氨抑制与碱度管理)"),
    # ---------- A 盐度-主导溶质(2 题,简单) ----------
    dict(id="q-251", tag="脱氮", topic="高盐胁迫", diff="简单", qt="A 盐度-主导溶质",
         q="中度嗜盐反硝化菌在高盐(约 3-5%)环境下的主导相容性溶质是什么?请按以下步骤完整作答:(1)指出主导溶质;(2)说明其被选择的原因(保护能力与合成能耗权衡);(3)举一种代表微生物并说明其合成或摄取途径。",
         kp="1.主导溶质:四氢嘧啶(ectoine)与海藻糖为主;2.选择原因:对蛋白与酶构象保护力强、合成能耗适中,优于仅靠 K+/谷氨酸的策略;3.代表菌:Halomonas elongata 以 ectABC 合成 ectoine;Chromohalobacter salexigens 同理;海藻糖经 otsAB 合成",
         ideal="主导溶质:在中度嗜盐反硝化菌中,胞内主要积累四氢嘧啶(ectoine)与海藻糖(trehalose)。选择原因:两者对蛋白质水合层与酶构象的保护力强('水化壳'稳定),不影响胞内大分子功能;相比单纯积累 K+/谷氨酸的'盐入策略',ectoine/海藻糖虽合成耗能更高,但允许胞内酶系在宽盐度范围维持活性,是保护能力与合成能耗的折中最优——氮源充足时偏向含氮的 ectoine,氮受限时偏向无氮的海藻糖。代表微生物与途径:Halomonas elongata 经 ectA/ectB/ectC 三步酶促合成 ectoine(天冬氨酸-β-半醛途径);Chromohalobacter salexigens 同样以 ectABC 为核心;海藻糖可经 otsA/otsB(海藻糖合成)或 TreY/TreZ 途径产生,部分菌还可经转运体直接摄取胞外海藻糖。",
         cat="Compatible solutes, Denitrification, 盐度-主导溶质",
         ref="10.1007/s10532-012-9542-0 Biological denitrification of brine: the；L0430 Glycine Betaine and Ectoine Are the Majo"),
    dict(id="q-252", tag="厌氧消化", topic="高盐胁迫", diff="简单", qt="A 盐度-主导溶质",
         q="嗜盐产甲烷古菌在高盐环境下的主导渗透调节溶质有哪些?请按以下步骤完整作答:(1)指出主导溶质(含'盐入'策略与有机溶质两层);(2)说明古菌溶质策略与细菌的差异;(3)举一种代表微生物并说明其积累途径。",
         kp="1.主导溶质:先以 K+ 积累('盐入')快速响应,再积累甜菜碱、β-谷氨酸、二肌醇磷酸等有机相容溶质;2.差异:古菌(无肽聚糖、酶系对盐适应不同)更多依赖 KCl 平衡+特化溶质(β-谷氨酸/NeSPA),细菌以 ectoine/海藻糖/GB 为主;3.代表:Methanohalophilus portucalensis 积累甜菜碱(可摄取外源 GB)",
         ideal="主导溶质:嗜盐产甲烷古菌采用两层策略——瞬时响应靠胞内 K+ 大量积累('盐入'策略,伴随酶系对高 KCl 内环境的适应);稳态适应则积累甜菜碱(GB)、β-谷氨酸(β-glutamate)、β-谷氨酰胺与二肌醇磷酸(NeSPA)等有机相容溶质置换 K+。与细菌的差异:细菌(如 Halomonas)以 ectoine/海藻糖/GB 为主且经 ectABC 等合成;古菌因细胞结构(假肽聚糖/S-层)与酶系嗜盐特化不同,更依赖 KCl 内平衡与'特化溶质'(β-谷氨酸、NeSPA 等细菌中罕见的氨基酸衍生物),且不少嗜盐产甲烷菌优先直接摄取外源 GB 而非从头合成。代表微生物:Methanohalophilus portucalensis(极端嗜盐产甲烷菌)高盐下胞内以甜菜碱为主导溶质,可经转运体摄取外源甜菜碱,并伴随 β-谷氨酸/NeSPA 协同积累。",
         cat="Compatible solutes, Methanogenesis, 盐度-主导溶质",
         ref="Oren 2008, Microbial life at high salt concentrations；L0430 Glycine Betaine and Ectoine Are the Majo"),
]

# ---------- L3 因子模板:T1 基因组档案表(自既有 52 题的参考答案反向整理) ----------
GENOME_PROFILES = {
    "P1": dict(syn="四氢嘧啶(ectoine)/羟基四氢嘧啶/葡萄糖基甘油酸合成缺失,甘氨酸甜菜碱合成不完整(仅 betA,缺 betB),海藻糖与谷氨酸/谷氨酰胺合成齐全",
               transport="溶质摄取转运系统(ProP/ProU、Opu、BetT、Ehu)全部缺失(仅 Nha+ 钠/氢反向转运)",
               concl="优先「互补菌跨喂」",
               donor="Halomonas、Thiocapsa、Rhodohalobacter 等产 ectoine/甘氨酸甜菜碱菌"),
    "P2": dict(syn="四氢嘧啶合成齐全(ectA/ectB/ectC),甘氨酸甜菜碱合成缺失,海藻糖合成齐全",
               transport="Opu 转运系统存在,ProP/ProU 缺失",
               concl="外源投加(利用现存转运系统)+互补菌跨喂",
               donor="产甘氨酸甜菜碱的盐单胞菌(Halomonas)/Thiocapsa 等"),
    "P3": dict(syn="四氢嘧啶合成缺失,甘氨酸甜菜碱合成齐全(betA/betB),海藻糖合成缺失",
               transport="ProU 转运系统存在,Opu/BetT/Ehu 缺失",
               concl="外源投加(利用现存转运系统)+互补菌跨喂",
               donor="产 ectoine 的 Halomonas/Chromohalobacter;海藻糖需外源补充或诱导"),
    "P4": dict(syn="除谷氨酸/谷氨酰胺外全部相容性溶质合成缺失",
               transport="BetT 转运系统存在,外源甜菜碱可摄取",
               concl="外源投加+长期产溶质菌共培养",
               donor="Halomonas 等产溶质菌"),
    "P5": dict(syn="四氢嘧啶合成不完整(仅 ectA),甘氨酸甜菜碱合成齐全,海藻糖合成齐全",
               transport="转运系统全部缺失",
               concl="优先「互补菌跨喂」",
               donor="产 ectoine 菌(如 ZC4RG17、UBA10518 等样本库 MAG)"),
    "P6": dict(syn="四氢嘧啶/甘氨酸甜菜碱/海藻糖合成齐全",
               transport="转运系统缺失(仅 Nha+)",
               concl="以梯度驯化诱导内源合成基因(ectABC/otsAB/betAB)表达为主",
               donor="内源诱导为主,关键梯度辅以外源低剂量相容性溶质缓冲渗透冲击"),
    "P7": dict(syn="四氢嘧啶/甘氨酸甜菜碱/海藻糖合成均缺失",
               transport="Opu 与 ProU 转运系统存在",
               concl="外源投加+长期产溶质菌共培养",
               donor="Halomonas 等产溶质菌"),
    "P8": dict(syn="四氢嘧啶合成缺失,甘氨酸甜菜碱合成不完整(仅 betA),海藻糖合成齐全",
               transport="仅 ProU 转运系统部分存在",
               concl="外源投加(利用现存转运系统)+互补菌跨喂",
               donor="Halomonas/Thiocapsa 等供体菌跨喂为主"),
}
ORG_PROFILES = {"Kuenenia": ["P1", "P3", "P6"], "Brocadia": ["P2", "P4", "P7"],
                "Jettenia": ["P3", "P5", "P8"], "Scalindua": ["P1", "P4", "P6"],
                "Anammoxoglobus": ["P2", "P5", "P7"]}
REACTORS = [("MBR 膜生物反应器", "城市污水", 24), ("SBR 颗粒污泥反应器", "消化液侧流", 18),
            ("一体式 PN/A(部分亚硝化-厌氧氨氧化)", "城市污水主流", 24),
            ("UASB 上升流反应器", "高氨氮工业废水", 36), ("主流移动床生物膜 MBBR", "海水入侵滨海厂", 12),
            ("序批式生物膜反应器", "食品加工高盐废水", 24), ("连续流厌氧氨氧化反应器", "油气田采出水", 48),
            ("盐湖卤水富集培养体系", "接种源筛选", 0)]
NEW_REGIMES = [(2.0, 4.0), (2.0, 6.0), (0.5, 3.0), (1.5, 5.5)]
REFS_T1 = ("L0430 Glycine Betaine and Ectoine Are the Majo；L0410 Salinity Tolerance and Osmoadaptation St；"
           "L0041 Deciphering performance and microbial ch；L0419 Rapid adaptation and enrichment of salt-")

T1_Q_TMPL = (
    "某 {reactor}{water}(HRT {hrt} h)以 {org} 为优势厌氧氨氧化菌。用户提供该菌的基因组序列"
    "(附件 {org}-{p}.fna,未经功能注释)或仅提供其属级分类学注释(可从 NCBI 下载参考 anammox 基因组)。"
    "用户希望把体系改造成耐盐体系、将运行盐度从 {a}% 提升到 {b}% 并稳定运行。"
    "请先对提供的基因组进行功能注释并诊断其耐盐功能缺陷,再给出具体措施(措施中必须提及相容性溶质的利用方式)。"
    "请按以下步骤完整作答:(1)先对提供的基因组完成功能注释,再诊断该菌株在目标盐度下的相容性溶质功能缺陷"
    "(合成缺失+转运缺失两方面);(2)按 0.5%/步、每梯度 7 天,计算从当前盐度升至目标盐度的总步数与总时长;"
    "(3)给出相容性溶质措施(外源投加或互补菌跨喂)并说明与转运状态一致的选择依据;"
    "(4)推荐溶质供体菌,并给出三条筛选依据(合成能力/盐度生态位/可定殖性);"
    "(5)设定进梯度判据、监测指标与性能不恢复时的回退方案。"
)


def _s(x: str) -> str:
    """要点串以分号(全/半角)作为条目分隔,字段内部出现的一律换成逗号。"""
    return x.replace("；", "，").replace(";", "，")


def build_factorial_questions(start_id: int = 301) -> list[dict]:
    """按新盐度区间 ×(菌属,档案)对生成 T1 因子变体(槽位表来自既有题目,不新造事实)。"""
    import hashlib

    out = []
    combos = [(org, p) for org, ps in ORG_PROFILES.items() for p in ps]
    used_pairs: set[tuple[str, str]] = set()  # 保证(反应器,菌属)全局不重复,避免模板签名撞车
    for r_idx, (a, b) in enumerate(NEW_REGIMES):
        rotated = combos[r_idx % len(combos):] + combos[: r_idx % len(combos)]
        for org, p in rotated[:3]:  # 每档盐度取 3 个组合,共 4×3=12 题
            seed = int(hashlib.md5(f"{org}|{p}|{a}".encode()).hexdigest()[:8], 16)
            k = seed
            while True:
                reactor, water, hrt = REACTORS[k % len(REACTORS)]
                if (reactor, org) not in used_pairs or k - seed >= len(REACTORS):
                    break
                k += 1
            used_pairs.add((reactor, org))
            steps = round((b - a) / 0.5)
            days = steps * 7
            prof = GENOME_PROFILES[p]
            q = T1_Q_TMPL.format(reactor=reactor, water=f"({water})" if water else "",
                                 hrt=hrt, org=org, p=p, a=f"{a:g}", b=f"{b:g}")
            kp = (f"1.(1)功能注释与缺陷诊断:{_s(prof['syn'])}，{_s(prof['transport'])}，结论:{_s(prof['concl'])}；"
                  f"2.(2)盐度梯度:以 0.5%/步自 {a:g}% 提升至 {b:g}%，共 {steps} 步、约 {days} 天，"
                  f"每梯度维持 7 个 HRT({hrt} h)并以脱氮性能恢复(如 NRR≥90%)为进梯度判据；"
                  f"3.(3)相容性溶质措施(必须):与转运状态一致——{_s(prof['concl'])}，"
                  f"外源投加起始 0.1-1 mM 经小试优化；"
                  f"4.(4)菌群强化与供体菌:{_s(prof['donor'])}，筛选依据:合成能力/盐度生态位/可定殖性；"
                  f"5.(5)物理保护与监测回退:聚氨酯(PU)载体、颗粒化或生物膜化缓冲盐胁迫，"
                  f"监测 NRR/SAA/亚硝残留/Na⁺ 与溶质合成基因表达，性能连续 2-3 天不恢复则回退盐度或延长驯化")
            ideal = (f"(1)功能注释与缺陷诊断:{prof['syn']};{prof['transport']};结论:{prof['concl']}。"
                     f"(2)盐度梯度:以 0.5%/步自 {a:g}% 提升至 {b:g}%,共 {steps} 步、约 {days} 天,"
                     f"每梯度维持 7 个 HRT({hrt} h)并以脱氮性能恢复(如 NRR≥90%)为进梯度判据。"
                     f"(3)相容性溶质措施(必须):{prof['concl']}——引入或投加与转运状态匹配的方案,"
                     f"外源投加(甘氨酸甜菜碱/海藻糖/四氢嘧啶,起始 0.1-1 mM 经小试优化)利用现存转运系统摄取,"
                     f"转运缺失时优先互补菌跨喂。"
                     f"(4)菌群强化与供体菌:{prof['donor']};筛选依据:合成能力/盐度生态位/可定殖性。"
                     f"(5)物理保护与监测回退:聚氨酯(PU)载体、颗粒化或生物膜化缓冲盐胁迫;"
                     f"监测 NRR/SAA/亚硝残留/Na⁺ 与溶质合成基因表达;性能连续 2-3 天不恢复则回退盐度或延长驯化。")
            out.append(dict(id=f"q-{start_id + len(out)}", tag="脱氮", topic="环境工程与能源",
                            diff="复杂", qt="T1 总体耐盐化措施", q=q, kp=kp, ideal=ideal,
                            cat="Anammox, Salinity acclimation, Compatible solutes, Bioaugmentation, 总体策略",
                            ref=REFS_T1))
    return out


# ---------- 质检与合入 ----------
from scripts.audit_dataset import template_signature  # noqa: E402


def rows_to_frame(batch: list[dict]):
    import pandas as pd

    return pd.DataFrame([{
        "question_id": b["id"], "标签": b["tag"], "主题": b["topic"], "难度": b["diff"],
        "题型": b["qt"], "question": b["q"], "ideal_keypoints（打分用）": b["kp"],
        "ideal_detail（参考）": b["ideal"], "eval_mode": R, "categories": b["cat"],
        "参考文献": b["ref"], "细分": "废水生物处理",
    } for b in batch])


def renumber_batch(batch: list[dict], start_id: int) -> list[dict]:
    """Assign a contiguous question-id range without mutating the source drafts."""
    return [
        {**row, "id": f"q-{start_id + index}"}
        for index, row in enumerate(batch)
    ]


def quality_gate(
    df, existing_sigs: set, existing_ids: set[str] | None = None
) -> tuple[list[str], list[str]]:
    """三道质检:schema 可解析、要点充分、签名不与现有库重复。"""
    problems, warns = [], []
    tmp = DATA / "_qc_tmp.csv"
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    try:
        qs = load_questions(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    qmap = {q.question_id: q for q in qs}
    for _, row in df.iterrows():
        qid = row["question_id"]
        q = qmap[qid]
        if q.num_keypoints < 3:
            problems.append(f"{qid}: 打分要点<3 条")
        if len(q.ideal_detail) < 100:
            problems.append(f"{qid}: 参考答案过短")
        sig = template_signature(row["question"])
        if sig in existing_sigs:
            problems.append(f"{qid}: 与现有题目模板签名重复")
    # 起草批内部去重
    seen: dict[str, str] = {}
    for _, row in df.iterrows():
        if existing_ids and row["question_id"] in existing_ids:
            problems.append(f"{row['question_id']}: 与正式题库 question_id 重复")
        sig = template_signature(row["question"])
        if sig in seen:
            problems.append(f"{row['question_id']}: 与 {seen[sig]} 互为模板重复")
        seen.setdefault(sig, row["question_id"])
    # oracle 校准:keypoints 与 ideal 的词汇一致性(起草自洽性)
    from wwbench.graders import HeuristicGrader

    grader = HeuristicGrader()
    for q in qs:
        score = grader.grade(q, q.ideal_detail).composite_score()
        if score < 0.75:
            warns.append(f"{q.question_id}: oracle 自评分偏低({score:.2f}),建议核对要点与答案一致性")
    return problems, warns


def validate_pending_for_approval(bank, pending) -> tuple[list[str], list[str]]:
    """Re-run structural and content checks immediately before mutating the gold bank."""
    problems, warns = [], []
    required = list(bank.columns)
    missing = [column for column in required if column not in pending.columns]
    if missing:
        problems.append(f"pending_review.csv 缺少题库列: {missing}")
        return problems, warns
    if pending.empty:
        problems.append("pending_review.csv 为空")
        return problems, warns

    ids = pending["question_id"].astype(str).str.strip()
    if ids.duplicated().any():
        problems.append("pending_review.csv 内 question_id 重复")
    bank_ids = set(bank["question_id"].astype(str).str.strip())
    overlap = sorted(set(ids) & bank_ids)
    if overlap:
        problems.append(f"pending_review.csv 与题库 question_id 重复: {overlap[:10]}")

    existing = load_questions(DATA / "questions.csv")
    existing_sigs = {template_signature(question.question) for question in existing}
    gate_problems, gate_warns = quality_gate(
        pending[required].copy(), existing_sigs, set(bank["question_id"].astype(str).str.strip())
    )
    problems.extend(gate_problems)
    warns.extend(gate_warns)
    return problems, warns


def main() -> int:
    ap = argparse.ArgumentParser(description="WWBench 出题流水线")
    ap.add_argument("--approve-all", action="store_true", help="将 pending_review.csv 全部合入题库(先备份)")
    ap.add_argument("--start-id", type=int, default=None,
                    help="起草时从该整数开始重新分配连续题号(例如 313),避免覆盖已有题号")
    args = ap.parse_args()

    import pandas as pd

    if args.approve_all:
        pending_path = DATA / "pending_review.csv"
        bank_path = DATA / "questions.csv"
        if not pending_path.exists():
            print("[merge] 无待审文件")
            return 1
        backup = DATA / "questions_v0_52.csv"
        if not backup.exists():
            shutil.copy(bank_path, backup)
            print(f"[merge] 原题库已备份 -> {backup.name}")
        bank = pd.read_csv(bank_path, encoding="utf-8-sig")
        pending = pd.read_csv(pending_path, encoding="utf-8-sig")
        problems, warns = validate_pending_for_approval(bank, pending)
        if problems:
            print(f"[merge] 质量门禁失败 {len(problems)} 条: {problems}")
            if warns:
                print(f"[merge] 软性提醒 {len(warns)} 条: {warns[:5]}")
            return 1
        merged = pd.concat([bank, pending[list(bank.columns)]], ignore_index=True)
        merged.to_csv(bank_path, index=False, encoding="utf-8-sig")
        print(f"[merge] 合入 {len(pending)} 题,题库 {len(bank)} -> {len(merged)} 题")
        return 0

    existing = load_questions(DATA / "questions.csv")
    existing_sigs = {template_signature(q.question) for q in existing}
    existing_ids = {q.question_id for q in existing}
    batch = AUTHORED + build_factorial_questions()
    if args.start_id is not None:
        if args.start_id < 1:
            print("[draft] --start-id 必须为正整数")
            return 1
        batch = renumber_batch(batch, args.start_id)
    df = rows_to_frame(batch)
    collisions = sorted(set(df["question_id"].astype(str)) & existing_ids)
    if collisions:
        print(
            f"[draft] 拒绝覆盖待审队列:本次生成的 {len(collisions)} 个 question_id 已存在于正式题库"
            f"(示例 {collisions[:8]}).请更新起草批次 ID 或建立 revision 流程。"
        )
        return 1
    problems, warns = quality_gate(df, existing_sigs, existing_ids)

    df.insert(0, "review_status", "pending")
    out = DATA / "pending_review.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[draft] 起草 {len(df)} 题(手写 {len(AUTHORED)} + 因子扩展 {len(df) - len(AUTHORED)}) -> {out.name}")
    print(f"[qc] 硬性问题 {len(problems)} 条:{problems if problems else '无'}")
    print(f"[qc] 软性提醒 {len(warns)} 条:{warns[:5] if warns else '无'}")
    if problems:
        print("[qc] 存在硬性问题,暂不合入;修复后重跑")
        return 1
    print("[qc] 通过。人工复核 pending_review.csv 后执行 --approve-all 合入")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
