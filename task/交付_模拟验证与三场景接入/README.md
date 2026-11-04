# 交付说明（revised）：ThetaVerse 0.3.0 更新后复验与修订

交付日期：2026-10-23。基线：`task\交付_模拟验证与三场景接入_20261020\`（10-20 版）。
触发事件：`ThetaVerse\` 更新至 **0.3.0**（工作树大规模修改，新增 mag/taxonomy/integrate/enzyme/strain 等子系统）。
任务要求：以科学严谨态度重审 10 月 20 日全部工作，基于更新后的内容做适当修改，输出可交付文件夹。

**复验总结论：六项核心指标与 10-20 版完全一致；三场景全部在新版本下重跑通过；一处上游断裂已适配并留证。**

---

## 一、变更影响矩阵（第零步产物）

| 组件 | 依赖的 0.3.0 接口 | git 级判定 | 实测动作 | 结果 |
|---|---|---|---|---|
| A 模拟验证 | external.PyrodigalBridge | external 包断裂（见下） | 适配层直连 pyrodigal 重跑 | 指标全部一致 |
| B mag 场景 | 同上 + io.read_kegg_hits | external 断裂；io 未改 | 同上重跑 | 4.2s 通过，行为一致 |
| B 16s 场景 | io.read_biom、tl.core_metrics、io.read_newick | io/_biom 未改；tl/_diversity 与 io/_tree 有修改 | 重跑 | 3.6s 通过，34×770 不变 |
| B taxon 场景 | NCBI 链 + A1 | external 断裂 | 适配后重跑 | 71.2s 通过（含今日网络重下载） |
| C Agent 流程文档 | 引用接口行为 | — | 逐接口实测核对 | 接入点不变，已加复验头注 |
| D 经验库 | 不依赖 thetaverse | — | 重建对账 | 6/6 PASS |
| E 专利 OCR | 无关 | — | 文件完整性核验 | 三件齐全，未做无谓动作 |

**关键发现（上游断裂，已适配留证）**：thetaverse.external 包在 0.3.0 导入即失败——
`external/_runner.py` 等 5 个文件引用 `core.exceptions.ExecutableNotFoundError`，而该异常在 0.3.0
重构后的 core.exceptions 中已不存在（ImportError 复现 + 全源检索定位）。这是 ThetaVerse 主线的
重构同步遗漏，建议上游修复（在 core.exceptions 恢复该异常或更新 external 引用）。
本交付不修改 ThetaVerse 源码，以适配层绕行：`scripts\gene_caller_adapter.py`
（优先 external，ImportError 时退回 pyrodigal 3.7.1 直连，参数与 PyrodigalBridge 逐一同值）。

## 二、A 复验：新旧指标对照（真值同一套，seed=42 不变）

| 指标 | 0.2.0（10-20） | 0.3.0（10-23 直连 pyrodigal） | 结论 |
|---|---|---|---|
| 预测基因数 | 33 | 33 | 一致 |
| V1 基因召回 | 0.9667 | 0.9667 | 一致 |
| V1 精确率 | 0.8788 | 0.8788 | 一致 |
| V2 精确匹配 | 29 | 29 | 一致 |
| V2 正确/误配 | 29 / 0 | 29 / 0 | 一致 |
| V3 KO 层 | 受阻（三证据） | 受阻（三证据与版本无关） | 口径不变 |

出处：`A_模拟验证\validation_metrics_030.json`（对照旧值见 10-20 版 validation_metrics.json）。
基因预测行为与版本解耦得到实证；唯一变化是调用方描述（适配层路径），已在 stats 与本表如实记录。

## 三、B 三场景复验

| 场景 | 10-20 耗时 | 10-23 耗时 | 产物一致性 |
|---|---|---|---|
| mag | 4.5s | 4.2s | 基因预测+受阻口径一致 |
| 16s | 2.4s | 3.6s | ThetaData 34×770、alpha 三指标、PCoA 全部一致 |
| taxon | 20.0s | 71.2s | 同一组装 GCF_000786775.1；耗时差异来自当日 NCBI 网络下载速度 |

出处：`B_三场景接入\运行演示\<场景>\运行摘要.json`（revised 版）。

## 四、D/E 复验

- D：幂等重建，对账 6/6 PASS（genomes 58,171、env_conditions 58,171、ko 64、transDB 77）。
- E：与 thetaverse 无关，三件移交产物核验齐全后原样归档（ZIP 159,534 B + MD5 + 说明）。

## 五、交付物与复现

```
A_模拟验证\          mock 基因组/真值/参考库 + mock_pyrodigal.faa + validation_metrics_030.json
B_三场景接入\        三场景 revised 运行摘要与产物
C_Agent流程\         流程文档（复验头注版）
D_经验库\            盐湖经验库.db + 建库对账.json
E_专利移交\          三件核验归档
scripts\             gene_caller_adapter.py + *_revised 管线与入口 + 本批全部日志
```

复现：
```bat
python scripts\A_run_validation_revised.py
python scripts\analyze_input_revised.py --input <输入>
python scripts\D_build_experience_db_revised.py
python scripts\run_QA_v3.py
```

## 六、QA

`scripts\QA报告_v3.txt`：含 thetaverse 版本断言（0.3.0）、A 新旧一致性断言、三场景摘要断言、
D 对账断言、E 完整性断言，全部 PASS（结果见文件尾行）。
