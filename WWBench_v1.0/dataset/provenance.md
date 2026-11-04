# 题目来源分层(provenance)

| 层 | 题号区间 | 数量 | 生成方式 | 可信度定位 |
|---|---|---|---|---|
| L0 专家原题 | q-061~q-200 | 52 | 领域专家撰写(用户提供) | 金标准,评测口径锚点 |
| L1 AI 手写 | q-201~q-252 | 28 | 按文献要点逐题撰写,引用题库既有 DOI | 高,建议专家抽审 |
| L2 因子模板 | q-301~q-312 | 12 | 8 基因组档案 × 新盐度区间组合 | 同 T1 家族口径 |
| L3 大规模程序化 | q-313~q-1362 | 1050 | 30+ 模板 × 正交因子轴组合生成,数值按化学计量推导 | 中,用于扩容与分层统计 |

全部题目经过统一质检门禁:schema 校验、条目内无分号、逐字查重
(对金标准与批内双向)、oracle 自评一致性。模板族相关性由 audit_dataset.py 如实
报告(独立题面数与簇规模),不在发布数据中隐藏。

**打分要点数口径(v1.0.1 实测修正):** 原表述"要点数 3-8"系生成器配置注释,
与发布数据不符;对 1142 题逐行复核实测为 **1~5 条/题(均值 4.07,总计 4644)**。
生成门禁约束 L1~L3 生成题;L0 专家原题(52 题)不经过该门禁。

## capsules 约定(对应 BixBench 的 data_folder)

`capsules/<question_id>.zip` 内含 `Data/references.txt`(该题参考文献线索)。

**已知限制(v1.0.1 披露):**
1. 引文取自题库"参考文献"列,部分条目在源数据导入时即被截断为约 45 字符
   (如 "L0430 Glycine Betaine and Ectoine Are the Majo");DOI 前缀条目可用
   `harness/scripts/repair_references.py` 经 Crossref 回填完整标题。
2. T1 题面声称的 `*.fna` 基因组附件为因子设计占位名(P1~P8 与真实 NCBI
   基因组的映射尚未建立);3 株真实厌氧氨氧化菌参考基因组(Brocadia sinica
   MAG_7 / Kuenenia stuttgartiensis HKUEN01 / Scalindua sp.AMX11)发布于
   `harness/data/attachments/_shared/genomes/`,经智能体模式 `_shared`
   分发机制进入每题工作区。
