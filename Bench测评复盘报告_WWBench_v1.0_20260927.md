# WWBench v1.0 及项目配套素材 · Bench 对标测评与复盘报告

| 项 | 内容 |
|---|---|
| 报告编号 | WWB-BENCH-20260927-01 |
| 测评对象 | `WWBench_v1.0`（核心）；关联对象：52 题源题库、三份顶层设计文档、`literature_downloader`/`lit_workspace`、`ThetaVerse-main`、基因组素材 |
| 测评执行 | 独立第三方视角（AI 测评员），基于文件夹内全部素材 + 现场实测（含可复现性实跑验证） |
| 测评日期 | 2026-09-27 |
| 证据可复现性 | 本报告全部数字均可由报告附录所列命令/文件位置重新推导；发布包完整性做了 SHA-256 抽检（5/5 通过）；harness 冒烟测试做了开箱实测与最小修复后复测 |
| 综合评级 | **8.1 / 10 · A⁻（优秀，距可发表/可分发状态差一轮 P0 收口）** |

---

## 1. 测评背景

WWBench 是"高盐废水 anammox / 相容性溶质"研究项目的评测基础设施，定位仿照 BixBench（FutureHouse 生信智能体基准）：**题库（dataset）、评测框架（harness）、校准结果（results）三件分离**。它同时承担三重角色：

1. **论文资产**：证明 ExtremeSelect V4.0 领域 Agent 系统有效性的证据链载体；
2. **研发仪表盘**：为 Agent 系统逐模块开发提供回归测试；
3. **公共基准**：以 MIT 许可对外分发的领域评测基准（CITATION.cff v1.0.0，2026-09-24 发布）。

本次测评的触发背景：题库已经历 52 题（v0）→ 1142 题（v1.0）的约 22 倍扩张，并完成了三档离线校准；但截至测评日**尚无任何真实模型成绩**，且文档存在疑似版本漂移。测评目的：在投入下一阶段（真实模型评测）之前，摸清资产质量底数、暴露阻断性问题、给出可核验的整改清单。

## 2. 测评依据

### 2.1 素材依据（全部现场核验，非转述）

| 证据源 | 核验内容 |
|---|---|
| `dataset/questions.csv`（1142 行 × 12 列） | 逐行统计：分层计数、要点数分布、题面长度、空值、重复 ID |
| `dataset/questions-verified-52.csv` | 与根目录 52 题源文件做 MD5 比对；与全集做子集关系核验 |
| `dataset/capsules/*.zip`（1142 个） | 抽样解包 q-061 / q-313 / q-1362，检查实际内容物 |
| `MANIFEST.sha256`（1228 条） | 抽样 5 个文件重算 SHA-256 比对 |
| `results/{oracle_calibration, oracle_degraded50, mock_smoke}/summary.json` | 全量提取 overall / per_dim / dataset_stats / config 指标 |
| `harness/`（10 个核心模块 + 6 脚本 + 6 配置） | 静态审阅 README/架构声明；**动态实跑 `tests/test_smoke.py`** |
| 顶层文档三件套 | `20260916introduction.docx`、`20260916讨论.pptx`（9 页文字+备注）、`agent.pptx`（9 页文字 + 9 张图片全部提取识读） |
| `literature_downloader/`（README/PROMPT/移交书/任务日志）与 `lit_workspace/logs/` | 下载进度与熔断决策记录 |
| 根目录 52 题源 CSV | 与 verified-52 做哈希同一性验证 |

### 2.2 对标标准（横向）

| 标准 | 对标要点 | 本项目对应物 |
|---|---|---|
| **BixBench**（arXiv:2503.00096，直接模板） | capsule 数据环境 / 智能体工具循环 / LLM judge / 多次复跑投票 / Verified 子集 | 逐项均有对应实现（见 §5.2 对照表） |
| **Datasheets for Datasets**（Gebru et al., CACM 2021） | 数据集动机、构成、采集过程、维护计划的文档化 | `dataset/provenance.md` 承担 datasheet 职能 |
| **ML 可复现性清单**（Pineau et al. 惯例） | 随机种子、温度、模型版本、环境全量记录 | 每次运行 `config` 全部落盘进 summary.json |
| **评测科学惯例** | judge 与 solver 异源、judge 一致性（kappa）审计、防训练泄露 | 框架具备（audit_judges.py），**但尚未产出结果** |
| **数据发布完整性** | 哈希清单、许可、引用文件 | MANIFEST.sha256 + MIT + CITATION.cff |

### 2.3 纵向对比基准

- **v0（52 题源 CSV）→ v1.0（当前发布）**：题量 ×22、单层 → 四层分级、无质检 → 五道质检门禁、无附件约定 → capsule 机制、无判分 → 双轨评分器、无结果 → 三档全量校准；
- **harness 内部版本痕迹**：harness README 停留在"92 题 / 418 要点"的中间版本，而框架代码已适配 1142 题（冒烟实测输出 `1142 题 / 4644 要点`）——迭代速度甩开文档的直接证据；
- **系统侧对照**：agent.pptx 架构图自标 V3.0 → V4.0 实体新增（GrowthTrait、EpistasisRecord），说明 bench 未来需覆盖的系统能力在持续膨胀。

## 3. 测评维度与权重

| # | 维度 | 权重 | 考什么 |
|---|---|---|---|
| D1 | 内容质量 | 20% | 题库数据本身的专家性、无脏值、可溯源 |
| D2 | 逻辑框架 | 20% | 三件分离、分层披露、评分体系设计的合理性 |
| D3 | 完整度 | 15% | 对宣称范围的覆盖缺口（附件、口径、成绩） |
| D4 | 精准度 | 15% | 数字/口径的内部一致性 |
| D5 | 落地性 | 20% | 开箱可复现、断点续跑、脚本工具链完备 |
| D6 | 规范与合规 | 10% | 许可、引用、哈希清单、工作区卫生 |

## 4. 详细测评数据（实测）

### 4.1 题库数据集

**规模与结构**（来源：`dataset/questions.csv` 逐行统计 + 冒烟测试输出）：

| 指标 | 实测值 | 判定 |
|---|---|---|
| 题目总数 | 1142（q-061 … q-1362） | 与 README 一致 ✔ |
| 列数 | 12，与 README 字段说明一致 | ✔ |
| 分层 | L0=52 / L1=28 / L2=12 / L3=1050 | 与 provenance.md 完全一致 ✔ |
| 要点总数 | **4644**（harness 权威解析；均值 4.07/题） | 与 README 一致 ✔ |
| 要点数分布 | **最少 1 条 / 最多 5 条** | ⚠ 与 provenance"质检门禁 3-8 条"矛盾（见 P1-6） |
| 重复题号 | 0 | ✔ |
| 空参考文献 / 空参考答案 | 0 / 0 | ✔ |
| 题面长度 | 86–460 字符，均值 266（金标准 52 题均值 309，专家题更详尽） | ✔ |

**金标准同一性**：`questions-verified-52.csv` 与根目录 52 题源文件 **MD5 完全一致**；且 52 个 ID 全部包含于全集 L0 层——"金标准锚点"可溯源、未被改动。这是数据治理上的加分项。

**分布健康度**（来源：summary.json `dataset_stats`，三个 run 内部一致）：

- 标签：脱氮 1026（89.8%）/ 污泥 80 / 厌氧消化 36 —— 偏科明显但与声明的"子基准"定位一致（P2-12）；
- 题型六类齐全：T1×442、E×223、T7×143、A×123、T5×116、T10×95；
- T1 因子设计：5 属 × 8 基因组档案 = 40 个 .fna 文件名，题量 3–19 题/文件（Kuenenia-P2 仅 3 题、Jettenia-P8 达 19 题，**因子格不均衡**）；盐度区间 12 档（46 至 28 题/档）；
- 类别频次 Top4：Compatible solutes 922、Salinity acclimation 699、Bioaugmentation 618、Anammox 610 —— 与研究主题高度聚焦 ✔。

### 4.2 发布完整性

- `MANIFEST.sha256` 共 **1228 条**（1142 capsule + 86 其他文件），抽样重算 5/5 **全部通过**；
- `CITATION.cff` v1.0.0 / MIT / 2026-09-24 齐备，但作者字段为 "WWBench Contributors" 占位（P2-10）。

### 4.3 capsule 内容物（抽样实测）

q-061 / q-313 / q-1362 三个 capsule **均只含 `Data/references.txt`**，且引文存在**截断**（如 "L0430 Glycine Betaine and Ectoine Are the Majo"——在源 CSV 就被 45 字符截断）。更关键的是：**442 道 T1 题面声称"附件 Kuenenia-P1.fna"等基因组文件，但 capsule 内没有任何 .fna**（P0-2 的直接证据）。

### 4.4 三档校准结果（全量 1142 题 × 2 次复跑 = 2284 次/档）

| 指标 | oracle_calibration | oracle_degraded50 | mock_smoke |
|---|---|---|---|
| mean_score | **0.9423** | **0.5251** | **0.0534** |
| 逐次达标率（≥0.6） | 1.0000（Wilson 95%: 0.9983–1.0） | 0.0342（0.0274–0.0424） | 0.0000（≤0.0017） |
| 多数达标率 | 1.0000 | 0.0342 | 0.0000 |
| 要点覆盖率 | 0.9842 | 0.5763 | 0.0653 |
| 六维归一 | 0.9005 | 0.4740 | 0.0415 |
| 数值召回 | 1.0000 | 0.5847 | 0.2045 |
| 拒答率 | 0 | 0 | 0.1042 |
| 评估完整性 | 1142/1142，缺失 0，未知题号 0 | 同左 | 同左 |

**判读**：三档分离度极好——满分档压在 0.94，半分档均值 0.5251 恰好落在 0.6 阈值之下导致达标率骤降至 3.4%，弱模型档贴近 0。这说明**阈值 + 要点/六维五五开的综合分公式具有良好的判别力**，"尺子"本身可用。

**但发现两个评分体系问题**：

1. **evidence 维度系统性失效**：oracle 档六维中 accuracy/completeness=1.0、mechanism/feasibility/rigor=0.9676，唯独 **evidence=0.5**（degraded 档 0.4229，mock 档 0.0）——闭卷模式 + 启发式判分下，该维度被机械打在中间值，无区分度（P1-7）；
2. **校准档 judge 用的是启发式评分器**（config: `judge.provider=heuristic`），LLM judge 的校准尚未做；且复跑数为 2，与 README 宣称的"5 次复跑"口径不一致（P1-9）。

### 4.5 可复现性实测（本次测评的关键动作）

**开箱实测**：`python tests/test_smoke.py` **失败**——
`FileNotFoundError: harness\data\questions.csv 不存在`。发布版把题库放在上层 `dataset/`，harness 仍按旧布局 `harness/data/` 寻址（P1-4）。

**最小修复后复测**：补入 `harness/data/questions.csv` 后再次运行，11 项检查通过，又暴露第二个缺失 fixture（`data/pending_review.csv`）；补入最小 fixture 后第三次运行——**16/16 全部通过**：

> dataset 1142 题/4644 要点 ✔ nan 污染防护 ✔ prompts ✔ grader 自评 0.96 ✔ LLM judge 解析 ✔ 数值校验 1.0/0.0 ✔ Wilson 区间与交互统计 ✔ 多数投票口径 ✔ judge 审计探针 ✔ 智能体工具解析 ✔ 工作区边界 ✔ 审批门禁 ✔ 扩库重编号 ✔ 智能体全流程（轨迹落盘）✔ 端到端管线 ✔ **"全部冒烟测试通过 ✔"**

**定性**：这是**发布打包缺陷而非代码缺陷**。代码在数据就位后一次全绿，工程质量高；但"按 README 快速开始必踩坑"对公共基准是不可接受的（P1-4）。测评中已就地补入两个文件完成修复验证（见 §8 P1-4 的处置记录）。

### 4.6 顶层文档三件套（文本 + 9 张图片全量识读）

| 文档 | 定位 | 质量判定 |
|---|---|---|
| `20260916introduction.docx` | 论文 Abstract + Introduction 初稿 | 逻辑链完整（抗逆瓶颈→溶质机会→领域空白→Agent 方案→实证设计），文献引用具体到作者年份，明确宣称 Crossref 核验。**但"4300 余篇"与下载台账 3834/3721 口径不符**（P2-11） |
| `20260916讨论.pptx` | 组会汇报（背景/场景/分工） | 每页标注"来源：引言第 X 段"+ 完整演讲备注，制作规范；三大应用场景与 bench 题型高度对应；标题页"汇报人：________"空白（草稿态）；落款"2026年8月"与文件名 0916 矛盾（P2-11） |
| `agent.pptx` | ExtremeSelect V4.0 系统设计稿 | 技术密度最高：五智能体流水线、CSA 四维评分及两档权重（<3%: 0.40/0.25/0.20/0.15；≥3%: 0.30/0.30/0.15/0.25）、LV-Sim 验证层、GrowthTraitDB 三级估计链、ρ≈0.5 诚实性声明、参考系统调研（ReactionSeek/KG4DT/ECOMATS）。**但引用的"方案 8.2.4"文档与 `rrndb_copy_number.py` 脚本均不在文件夹**（P2-11）；**其 CSA 排序与 LV-Sim 能力在 bench 中没有任何对应题型**（P0-2 的系统性后果） |

### 4.7 配套资产

- `literature_downloader`：工程设计优秀（熔断/冷却/断点/合规红线俱全），且有过硬的决策记录——用 Unpaywall 分层抽样证实全队列 0% OA 后**主动停跑**，避免 40 小时空转污染断点日志。但现状是 **2790 篇队列 0 篇落地**（试跑 5/5 blocked），知识库与开卷消融均无米下锅（P0-3）；
- `ThetaVerse-main`：bench 智能体模式未来最重要的"领域工具"候选，本身工程质量高（190+ 测试文件、163 篇 ADR），但 `example/Anammox_analysis.py` 依赖的 `transport_system.txt` 不在仓库（影响 GDA 型客观题的金标准生产）；
- 工作区卫生：`dir/`、`mkdir/` 两个空文件夹（命令行误建）；`literature_downloader/.env` 含本机配置，若对外分发需先行脱敏核查（P2-14）。

## 5. 对标分析

### 5.1 横向（vs BixBench 与业界惯例）

| BixBench 设计要素 | WWBench v1.0 对应实现 | 对标结论 |
|---|---|---|
| capsule（数据+notebook） | capsule zip（**暂仅 references.txt**） | 机制有、内容空，**落后于模板** |
| Aviary 智能体 3 工具 | 4 工具（run_python/read_file/list_workdir/submit_answer）+ 轨迹落盘 | **超越**（轨迹审计 BixBench 未强调） |
| LLM judge + range verifier | rubric_6dims LLM judge + 5% 数值容差 + 拒答双保险 | **超越**（数值校验是 BixBench 没有的客观层） |
| 5 次复跑 + majority | 框架支持，校准实跑 2 次 | 持平（口径需对齐，P1-9） |
| Verified-50 子集 | verified-52（与源文件 MD5 同一） | **持平偏强**（可溯源更严） |
| —（无） | oracle/degraded/mock 三档校准 + audit_dataset/judges + MANIFEST | **WWBench 独有增强** |
| Datasheets 惯例 | provenance.md 含分层、生成方式、可信度定位、缺陷披露 | **达到甚至超出惯例**（主动披露 L3 模板族相关性） |

### 5.2 对宣称范围的完整性缺口（纵切）

| 宣称 | 实测 | 缺口 |
|---|---|---|
| "每题工作区材料 capsule" | 仅 references.txt 且引文截断 | .fna 附件缺位 |
| "智能体模式自动分发附件" | 分发机制冒烟验证通过 | 无真实附件可分发 |
| "LLM judge" | 校准档全为 heuristic | LLM judge 校准未跑 |
| "5 次复跑" | 校准 2 次 | 口径不一 |
| "WWBench 评 ExtremeSelect" | 现有题型全部是知识/方案 QA | CSA 排序、LV-Sim 模拟、FDP 注释判定**均无客观题型**（bench 与系统能力错位，这是比任何单条 bug 都重要的结构性缺口） |

## 6. 现存问题汇总（P0=阻断发布/论文，P1=损害可信度，P2=打磨项）

| 编号 | 级别 | 问题 | 证据定位 |
|---|---|---|---|
| P0-1 | 阻断 | **零真实模型成绩**：三档均为离线校准，benchmark 没有 headline 数字 | `results/comparison_report.md` 仅含 oracle/degraded/mock |
| P0-2 | 阻断 | **442 道 T1 题附件缺位 + 能力链题型缺失**：题面声称的 .fna 不在 capsule；系统核心的注释判定/供体排序/模拟验证无客观题型，bench 目前只能考"知识"不能考"能力" | capsule 抽样解包；summary.json by_genome_file（442 题）；agent.pptx CSA/LV-Sim 设计 |
| P0-3 | 阻断 | **知识库零落地**：2790 篇文献 0 篇下载（0% OA 已证实，卡机构 SSO），开卷消融与回顾性预测题无法启动 | `lit_workspace/logs/authorized_browser_download_v2.csv`（5/5 blocked）；任务日志 §8.3 |
| P1-4 | 高 | **发布包开箱即坏**：冒烟测试缺 2 个数据文件（`harness/data/questions.csv` 布局错位 + `pending_review.csv` fixture 未随包）；已现场最小修复并验证 16/16 通过 | 本次实测（§4.5）；harness README "快速开始"段 |
| P1-5 | 高 | **文档版本漂移**：harness README 写"92 题/418 要点"，实际 1142/4644；引用的 `PPT_THEME_ALIGNMENT_AUDIT.md` 不存在 | harness/README.md 开头；全文件夹检索无此文件 |
| P1-6 | 高 | **质检口径与数据不符**：provenance.md 称门禁"要点数 3-8"，实测 1–5（最少 1 条） | provenance.md vs 本次逐行统计 |
| P1-7 | 高 | **evidence 维度无区分度**：闭卷+启发式判分下系统性 0.5（oracle 档六维中唯一失真项） | oracle summary.json per_dim |
| P1-8 | 中 | capsule 引文截断（"…Are the Majo"），references.txt 可用性受损 | q-313.zip 解包实测 |
| P1-9 | 中 | 复跑口径：校准 replicates=2，README 宣称 5 次复跑投票 | summary.json config vs harness README |
| P2-10 | 低 | CITATION.cff 作者为占位符 | CITATION.cff |
| P2-11 | 低 | 上层文档引用悬空与口径差：方案 8.2.4、rrndb_copy_number.py 缺失；4300 vs 3834/3721；PPT 时间标注矛盾 | agent.pptx 第 6-7 页、introduction.docx、下载台账 |
| P2-12 | 低 | 题域偏科（脱氮 89.8%）——定位声明已做，但对外报告必须坚持"子基准"口径并给出独立题面分层 | summary.json by_tag；README 范围声明 |
| P2-13 | 低 | L3 模板族"独立题面口径"有审计工具、未进 results 层 | audit_dataset.py 存在；results 无对应字段 |
| P2-14 | 低 | 工作区卫生：dir/、mkdir/ 空文件夹；.env 需脱敏核查后方可分发 | 文件夹实测 |

## 7. 核心优劣总结

### 优势（有据可依的强项）

1. **评分尺子已被证明可用**：三档校准分离度极佳（0.94 / 0.53 / 0.05），阈值 0.6 恰好把半分质量挡在门外——多数自建 benchmark 死在"满分档只有 0.7"，本项目不在此列；
2. **数据治理超出同类惯例**：四层 provenance 主动披露缺陷、金标准 MD5 同一性、MANIFEST 抽检 5/5、零空值零重复、哈希级发布完整性；
3. **框架工程成熟**：两阶段断点续跑、judge/solver 异源设计、judge 审计脚本、智能体轨迹落盘、工作区沙箱边界校验——冒烟 16 项一次全绿；
4. **两个 BixBench 没有的增强**：数值容差校验（客观层）与三档校准方法学；
5. **与系统的亲缘关系**：T1 题族的五步作答要求（诊断→梯度→措施→供体→监测）与 ExtremeSelect 流水线（GDA→SSMA→CSA→RVA）逐段对应，升级为能力链 benchmark 的地基已经打好。

### 劣势（同样有据可依）

1. **三件 P0 全部是"最后一公里"缺位**：没有真实成绩、没有真附件、没有文献库——设计图纸 A+，交付物尚未闭环；
2. **bench 与系统能力错位**：现有 1142 题全部是"对专家答案"型，ExtremeSelect 最难被模仿的能力（机器可验的基因组判定、四维排序、种群模拟）一个都没考到；
3. **文档落后实现一个版本**（92→1142），对外分发会立刻损害专业形象；
4. **evidence 维度与复跑口径两处评分体系瑕疵**，需在真实模型跑之前修正，否则返工。

## 8. 精准优化方案（按 P0→P2，每条含动作与验收标准）

**P0-1 跑出真实成绩**
动作：修完 P1-4/5/7/9 后，52 题金标准子集 × 三档模型（国际一档 / 国产一档 / 开源一档）× 双模式（单轮/智能体），judge 用异厂商模型。
验收：`results/` 出现首个真实模型 run；comparison_report.md 出现非校准行。

**P0-2 补附件 + 增设客观题型层**
动作：① 40 个 T1 基因组 .fna 入 `data/attachments/<qid>/`（机制已预留）；② 用 ThetaVerse/可信管线对 8 个参考基因组跑注释，产出机器金标准缺陷谱；③ graders.py 增加 `fdp_check` 评分器（基因在/缺逐项比对）与 `rank_check`（供体排序 NDCG + 硬约束违规即挂）。
验收：抽样 10 题 capsule 含 .fna；≥40 道"基因组诊断题"实现零评委判分；排序题给出 NDCG 指标。

**P0-3 打通文献权限**
动作：完成出版商 SSO 登录 → 金标准 DOI 验证 → `start_full_run.cmd` 无人值守；下载完成后清除断点黑名单重跑。
验收：`lit_workspace/literature/` PDF 数 > 0；总览表已下载数从 1044 上升。

**P1-4 修复发布打包**（已部分处置）
处置记录：本次测评已就地补入 `harness/data/questions.csv`（自 `dataset/` 复制）与最小 `pending_review.csv` fixture，冒烟 16/16 通过。
动作：修改 `scripts/build_release.py`——打包时自动同步题库到 `harness/data/` 并附带 fixture；或在 `dataset.py` 增加向 `../dataset/` 的回退查找。
验收：全新解压发布包，`python tests/test_smoke.py` 首跑即全绿。

**P1-5 文档对齐**：harness README 的"92 题/418 要点"改为 1142/4644，补 `PPT_THEME_ALIGNMENT_AUDIT.md` 或删除引用。验收：README 数字与 summary.json dataset_stats 完全一致。

**P1-6 统一要点口径**：复核生成器门禁（是"要点条目 3-8"还是"分号片段 3-8"），要么修数据（给 min=1 的题补要点），要么修文档。验收：provenance 声明与逐行统计一致。

**P1-7 修 evidence 维度**：闭卷模式下将 evidence 维度权重置零或按模式归一；开卷（with_refs）消融时再启用。验收：oracle 档六维无系统性常数。

**P1-8 修引文截断**：从源数据恢复完整标题（截断发生在源 CSV 导出，需回溯源表）。验收：capsule 内 references.txt 无以断词结尾的条目。

**P1-9 统一复跑口径**：README 注明"校准档 2 次、真实评测 5 次"，或校准补跑到 5 次（heuristic 离线，成本极低）。

**P2 打包**：CITATION 补真实作者；补齐方案 8.2.4 / rrndb_copy_number.py 归档；统一 4300/3834 口径；清理 dir/、mkdir/；.env 脱敏核查。

## 9. 迭代改进建议（v1.0 → v1.1 → v2.0）

**v1.1（1~2 周，收口发布）**：P1 全清 + P0-1 的 52 题首跑。卖点措辞："首个相容性溶质领域 LLM 基准，三档校准 + 数值容差 + 哈希级完整性"。

**v2.0（1~2 月，能力链升级）**——把 bench 从"考知识"升级为"考能力链"：
1. **五站题型**：A 基因组诊断（客观）→ B 溶质映射（客观）→ C 工程计算（客观）→ D 供体排序（半客观）→ E 全场景报告（评委兜底），与 GDA/SSMA/CSA/RVA 一站对一站；
2. **五级消融阶梯**：裸 LLM → +文献 RAG → +通用工具 → +ThetaVerse → 完整 ExtremeSelect，每个模块的贡献变成可量化台阶；
3. **回顾性预测题 30~50 道**：从下载完成的文献库抽取已发表生物强化实验，以"实验前情境"出题、以**真实结局**判卷——这是审稿人无法反驳的金标准；
4. **防泄露三件套**：独立题面口径进入 results、模型发布日后的 held-out 题组、头部模型逐字命中检查；
5. **诚实性指标**：该说不知道时说了不知道加分、编造基因名/文献扣分（可机检），呼应系统的 ρ≈0.5 诚实性规范。

**长期（v2.x）**：把 `BioaugmentationOutcome` 回传闭环接入 bench——系统推荐 → 用户实验 → 结果回流 → 权重更新的数据飞轮，使 benchmark 从静态考卷进化为在线评测基础设施。

## 10. 最终综合评级

| 维度 | 权重 | 得分/10 | 评分依据（证据锚点） |
|---|---|---|---|
| D1 内容质量 | 20% | **8.5** | 金标准 MD5 同一、零空值零重复、专家题更详尽（均值 309 vs 266 字符）；扣分：引文截断、要点 1 条的题存在 |
| D2 逻辑框架 | 20% | **9.0** | 三件分离、四层 provenance 主动披露、双轨评分+数值校验、阈值判别力被三档校准证实；扣分：evidence 维度失效、与系统能力错位 |
| D3 完整度 | 15% | **7.0** | 对宣称范围有三处实质缺口（附件/LLM judge/真实成绩）；题域偏科已声明 |
| D4 精准度 | 15% | **8.0** | 1142/4644/2284 等核心数字三档 run 内部完全自洽；扣分：README 版本漂移、3-8 vs 1-5、2 vs 5 次复跑 |
| D5 落地性 | 20% | **7.5** | 代码一次全绿、断点续跑/审计工具齐备；扣分：开箱即坏（实测复现并已修复）、快速开始必踩坑 |
| D6 规范与合规 | 10% | **8.5** | MANIFEST 抽检 5/5、MIT、CITATION 齐备；扣分：作者占位、工作区卫生 |

### 加权总分：**8.1 / 10**　综合等级：**A⁻**

> **评级判词**：这是一套**方法论自觉远超平均水准**的领域基准——主动披露缺陷、哈希级完整性、三档校准、数值容差层，均为同类自建 benchmark 中罕见的设计；其短板不在"造得不好"，而在"还没发出去"：三件 P0（真实成绩、真附件、文献库）全部是执行层最后一公里，且有现成轨道可依。修完 P1 打包与口径问题后即具备对外分发音量；完成 v2.0 能力链升级后，具备支撑一篇方法论文的核心证据链。

---

### 附录：本次测评的可复现核验方式

- 题库统计：`pandas.read_csv("dataset/questions.csv")` 逐行计数（1142 行；要点按 harness 权威解析 4644，按全角分号朴素切分为 4537——口径差异已在 §4.1 注明）；
- 同一性验证：`MD5(questions-verified-52.csv) == MD5(根目录52题CSV)` = True；
- 完整性：对 `MANIFEST.sha256` 中 5 个条目重算 SHA-256 全部一致；
- 校准指标：`results/*/summary.json` 的 overall/per_dim/dataset_stats/config 全字段提取；
- 可复现性：`cd harness && python tests/test_smoke.py`（开箱失败复现 → 补 2 个数据文件 → 16/16 通过，输出"全部冒烟测试通过 ✔"）；
- capsule 抽样：解包 q-061/q-313/q-1362 检查内容物与引文截断。

*测评现场处置披露：为完成可复现性验证，已在 `WWBench_v1.0/harness/data/` 下补入 `questions.csv`（复制自 `dataset/`）与最小 `pending_review.csv` fixture 两件文件；该处置即 P1-4 的临时修复，正式修复应落在 `build_release.py`。*

---

## 附录：整改终态更新（2026-09-27 同日）

本报告 §6 所列 14 条问题已完成一轮分类整改，发布版本升至 **v1.0.1**。要点：

- **已闭环 8 条**：P1-4（build_release.py 根因修复，开箱冒烟 **19/19**）、P1-5/6/9（文档口径全部对齐实测，三档校准按 5 复跑重跑 n_runs=5710）、P1-7（evidence 维根因=映射系数 1.2，修复后 0.5→1.0/0.4965/0.0749，oracle 均分升至 0.9840）、P1-8（Crossref 回填管线，金标准试点 35/36）、另有整改中新发现并修复的 2 个代码缺陷（rank_check IDCG 公式、空评分表报告崩溃）；
- **P0-1 链路 100% 就绪**：占位 Key 实跑验证至 GLM 端点 401 边界，优雅降级；唯一剩余=合法 API Key；
- **P0-2 阶段闭环**：fdp_check/rank_check 客观校验器 + 附件分发机制 + 3 株真实基因组随包；金标准数据入 v2.0；
- **P0-3 未变**：文献库仍待 SSO。

逐条根因→动作→验收数据见《WWBench_v1.1_整改台账与验收报告_20260927.md》。本报告评级基准保持 v1.0 现场实测口径不变，作为整改前基线存档。
