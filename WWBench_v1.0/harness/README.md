# WWBench —— 废水生物处理领域 LLM 评测基准

仿照 [BixBench](https://arxiv.org/abs/2503.00096)(FutureHouse 的生信智能体基准)的形式搭建的领域评测框架:
**结构化题库 → 模型作答(单轮或智能体工具循环,N 次复跑)→ judge 按评分细则打分 + 数值容差校验 → 分层指标与报告**。

当前题库:`data/questions.csv`(v1.0.1 实测口径:**1142 题 / 4644 个打分要点**,主题覆盖 anammox 高盐耐受、相容性溶质调控、
耐盐化工程措施等;难度:复杂 637 / 中等 441 / 简单 64;题型 6 类)。专家撰写的 52 题金标准随包发布于
`../dataset/questions-verified-52.csv`(开发布局中为 `data/questions_v0_52.csv`)。

**范围声明：** 当前 WWBench 是研究主题中的“高盐废水/anammox/相容性溶质”评测子基准，
不是完整覆盖盐湖宏基因组、污染环境修复、固废资源化、文献检索 Agent、功能互作模型和实验验证的平台。
与 `20260916讨论.pptx` 的逐项对齐审计文件暂未随包归档,将在 v1.1 收口时补充。

## 与 BixBench 的设计对应

| BixBench | WWBench |
|---|---|
| capsule(数据 + notebook + 假设/结果元数据) | 题目(题面 + 打分要点 + 参考答案 + 元数据) |
| Aviary 智能体脚手架,3 工具(edit cell / list workdir / submit answer) | `solver.agent` 模式,4 工具(run_python / read_file / list_workdir / submit_answer) |
| 每题独立 Docker 环境 + 数据分发 | 每题独立工作区,`data/attachments/<qid>/**` 自动分发 |
| LLM judge + range/str verifier 双轨评分 | rubric_6dims LLM judge + `numeric_check` 数值容差校验 |
| 5 次复跑 + majority voting | 同款(`replicates` 可配,真实评测默认 5;随包三档校准基线 v1.0.1 起同为 5 次复跑);另给出精确二项计算的"投票数-准确率"曲线 |
| 纯记忆基线、拒答/图片消融 | closed vs with_refs 消融、拒答识别、oracle/degraded/mock 校准档 |
| 题目 LLM 去重质检、Verified 子集 | `audit_dataset.py` 模板簇审计 + 完整性检查 |
| 多模型对比图(图 4) | `compare_runs.py` 排行榜表 + 分组柱状图 |

## 目录结构

```
wwbench/
├── data/questions.csv        # 题库(当前文件实际 12 列:题面、打分要点、参考答案、元数据…)
├── data/attachments/         # (可选)每题附件:<qid>/** 分发给该题,_shared/** 全体共享
├── wwbench/                  # 核心包
│   ├── dataset.py            #   题库加载/校验/要点解析
│   ├── agent.py              #   智能体模式:工具循环/工作区 staging/轨迹落盘
│   ├── providers.py          #   模型后端:openai 兼容 / oracle / mock
│   ├── prompts.py            #   求解与评分提示词(单轮 + 智能体 + 六维 rubric)
│   ├── runner.py             #   两阶段运行器(作答→评分),支持断点续跑
│   ├── graders.py            #   评分器:rubric_6dims(LLM)/ heuristic / numeric_check
│   ├── metrics.py            #   指标:accuracy / stable / precision / 拒答率 / 投票曲线 / 分层
│   └── report.py             #   report.md + summary.json + 图表
├── configs/                  # 运行配置(单轮/智能体 × 离线校准/真实 API)
├── scripts/
│   ├── run_bench.py          # 主 CLI
│   ├── audit_dataset.py      # 题库审计:模板簇 + 完整性
│   ├── audit_judges.py       # judge 自洽性/交叉/kappa/偏差审计
│   └── compare_runs.py       # 多 run 排行榜对比
├── tests/test_smoke.py       # 离线冒烟测试(不需要 API key)
└── outputs/<run_name>/       # 每次运行的完整产物(含 trajectories/ 与 workspaces/)
```

## 快速开始

```bash
# 0) 离线冒烟测试(数据、提示词、评分、智能体、数值校验、全流程)
python tests/test_smoke.py

# 1) 离线校准三件套(v1.0.1 复跑后实测:mean_score 0.9423 / 0.5251 / 0.0534)
python scripts/run_bench.py --config configs/run_oracle.yaml          # 满分上界 ≈0.94
python scripts/run_bench.py --config configs/run_oracle_degraded.yaml # 半分档 ≈0.53
python scripts/run_bench.py --config configs/run_mock.yaml            # 弱模型 ≈0.05
python scripts/run_bench.py --config configs/run_agent_oracle.yaml    # 智能体模式(工具循环)

# 2) 题库体检:模板簇/附件缺失/要点过少
python scripts/audit_dataset.py

# 2b) judge 自洽性/双 judge/kappa/长度顺序偏差审计(基于已有 responses.csv)
python scripts/audit_judges.py --config configs/run_oracle.yaml --repeats 3

# 3) 多 run 排行榜对比(表 + 柱状图)
python scripts/compare_runs.py

# 4) 真实评测:编辑 configs/run_openai.yaml(单轮)或 run_openai_agent.yaml(智能体)后
export GLM_API_KEY=sk-xxx        # 或 OPENAI_API_KEY,取决于配置
python scripts/run_bench.py --config configs/run_openai_agent.yaml --limit 5   # 先试 5 题
python scripts/run_bench.py --config configs/run_openai_agent.yaml             # 全量 1142 题
```

常用参数:`--stage answer|grade|report|all`(分阶段)、`--replicates N`(覆盖复跑数)、
`--limit N`(只跑前 N 题)、`--no-resume`(丢弃旧结果重跑)。

**断点续跑**:answers/grades 都按 `(question_id, replicate, 模型名)` 去重,中断后重跑同一命令即续。

## 评分体系(rubric_6dims)

每条回答由 judge 评出三部分:

| 组成 | 说明 |
|---|---|
| `keypoint_hits` | 逐条判定题库"打分要点"是否被实质性覆盖(意思等价即可) |
| `dim_scores` | 六维各 0-2 分:accuracy 准确性 / completeness 完整性 / mechanism 机制深度 / feasibility 工程可操作性 / evidence 依据支撑 / rigor 逻辑严谨 |
| `refused / overall` | 拒答识别(正则 + judge 双保险)与总评 |

- **综合分** = `kp_weight × 要点覆盖率 + (1-kp_weight) × 六维归一分`,默认 0.5/0.5,拒答记 0
- **达标(correct)** = 综合分 ≥ `pass_threshold`(默认 0.6)
- **数值容差校验**(始终开启,仿 BixBench 的 range-verifier):从参考答案抽取全部数值,
  检验作答是否给出等值数字(相对容差 `numeric_tolerance`,默认 5%),产出 `numeric_recall` 指标
- 六维定义可在配置 `rubric.dims` 覆盖

judge 建议用与求解模型**不同的**模型(BixBench 用 Claude 评 GPT、反之),避免自评偏置。
`heuristic` 评分器(要点词汇覆盖率 ≥40% 判命中)完全离线,用于冒烟测试与 LLM judge 的交叉校验。

## 智能体模式(solver.agent)

配置 `solver.agent` 后,模型在**每题独立工作区**中按工具循环自由探索(对应 BixBench 的
notebook + capsule 数据环境):

- 工具:`list_workdir`(递归列目录)/ `read_file`(读文件,限制在工作区内)/
  `run_python`(子进程执行代码,超时可控)/ `submit_answer`(提交并结束)
- 工作区分发:`data/attachments/<question_id>/**` 只给该题(T1 题的 .fna 基因组放这里),
  `data/attachments/_shared/**` 全体共享;`stage_references: true` 时参考文献写入 `references.txt`
- 轨迹完整落盘 `trajectories/<qid>_r<N>.jsonl`(每步工具调用与观察),工作区保留在 `workspaces/`
- 提示词为 BixBench 式五步脚手架:看目录 → 读文件 → 小步算(数值必须用代码)→ 提交
- **安全提示**:`run_python` 在本机执行模型生成的代码,评测不可信模型时请在 Docker 内运行
  (BixBench 即用预构建 Docker 镜像隔离)

## 指标口径(对应 BixBench)

| 指标 | 口径 | BixBench 对应 |
|---|---|---|
| accuracy(逐次达标率) | 全部 N×Q 次运行中达标的比例 | run-level accuracy |
| stable_accuracy(多数达标率) | 某题 ≥50% 复跑达标才算通过 | majority voting |
| precision_on_answered | 非拒答作答的平均分 | precision(剔除 refusal) |
| refusal_rate | 明确拒答的比例 | refusal 消融 |
| numeric_recall | 参考答案数值在作答中命中的比例(容差内) | range-verifier |
| accuracy_vs_votes | k=1..N 抽样多数通过的精确概率曲线 | 图 5 投票曲线 |
| mean_score / keypoint_coverage / dim_norm | 连续细粒度分 | —(本 bench 特有) |

分层报告按以下维度切分,附最易/最难 Top10:

- **元数据列**:标签 / 主题 / 难度 / 题型 / 细分
- **题面解析的因子轴**(T1 的 442 题是 5 优势菌 × 12 盐度区间 × 8 基因组档案的受控因子设计,
  加载时自动从题面抽取):优势菌 / 目标盐度 / 基因组档案——可直接回答
  "模型在哪种菌/多高盐度上表现更差"这类问题
- **categories 多标签**(一题可属多组):Anammox / Compatible solutes / Bioaugmentation 等逐标签聚合

## 产物说明(`outputs/<run_name>/`)

| 文件 | 内容 |
|---|---|
| `responses.csv` | 每条回答:题号、复跑序号、模型、模式(single/agent)、提示词、回答、轨迹路径 |
| `trajectories/*.jsonl` | 智能体模式:每步工具调用与观察(对应 BixBench 的轨迹数据) |
| `workspaces/` | 智能体模式:每题工作区(含分发的附件与 staged 文件) |
| `grades.csv` | 每条评分:要点命中、六维分、综合分、数值校验、拒答、judge 理由 |
| `question_level.csv` | 按题聚合:均分、达标率、拒答率、stable_pass |
| `summary.json` | 总体指标 + 投票曲线 + 分层 + 配置 + 题库统计 |
| `report.md` + `plots/` | 人读报告与图表(六维、投票曲线、题目难度分布、分层柱状图) |
| `judge_audit/` | judge 重复性、交叉一致性、偏差探针证据 |

## 扩展指南

- **加题**:必须通过 `scripts/generate_questions.py` 生成 `data/pending_review.csv`,完成自动质检与人工审核后再用 `--approve-all` 合入;
  不要直接编辑 `data/questions.csv`(正式题库当前 12 列;要点用 `1.xxx；2.xxx` 分号分隔)
- **子集评测**:`filters:` 里按 `difficulty/qtype/tag/topic` 过滤
- **消融实验**:`context_mode: with_refs` 把题库参考文献线索注入上下文(闭卷 vs 开卷对照,
  对应 BixBench 的纯记忆基线消融);`solver.degrade` 可制造受控的部分正确样本
- **换模型**:任何 OpenAI 兼容端点(OpenAI / GLM / DeepSeek / Qwen / vLLM 自部署)改
  `base_url + model + api_key_env` 即可

## 出题流水线(scripts/generate_questions.py)

方法学取自 LAB-Bench / ScienceAgentBench / BixBench(检索后的共识:题目须可溯源、
金标准自洽、自动质检、专家终审),分四道关:

1. **分层起草**:L1 引用题库既有 DOI 的文献要点 → L2 教科书级共识(标注来源,不造 DOI)
   → L3 因子模板扩展(T1 基因组档案表 × 盐度区间,槽位来自既有数据,不新造事实);
2. **自动质检**:schema 可解析、答案长度、模板签名去重(对现有库与批内双向查)、
   oracle 自评一致性(要点 vs 参考答案)。注意:该门禁约束**生成题**(L1~L3);
   专家原题(L0,52 题)不经过生成门禁,其要点数实测为 1~5 条/题(v1.0.1 复核口径)
3. **待审队列**:产出 `data/pending_review.csv`(含 review_status 列);
4. **批准合入**:`--approve-all` 自动备份原库(`questions_v0_52.csv`)后合入。

默认起草批次的题号若已占用，生成器会拒绝覆盖；扩库时可用
`python scripts/generate_questions.py --start-id 313` 重新分配连续题号，仍需经过同一待审与批准流程。

当前正式题库 CSV 实际为 12 列；`data/pending_review.csv` 为 13 列，其中第 1 列
`review_status` 是审核流水线临时字段，不属于正式题库字段。若项目接口必须固定为
13 列，应先定义缺失字段并做版本化迁移，不要直接向金标准题库追加空列。

当前正式题库为 **1142 题,四层来源**(L0 专家 52 / L1 AI 手写 28 / L2 因子模板 12 /
L3 程序化 1050),题型覆盖 T1×442 / E×223 / T7×143 / A×123 / T5×116 / T10×95,
标签新增厌氧消化。分层构成与可信度定位见 `../dataset/provenance.md`。
**注意:非 L0 题已过自动质检,领域专家终审仍建议补做**(LLM 起草的固有边界,
BixBench 论文同样依赖专家逐题审改)。

## 已知边界(v1.0.1 更新)

- T1 类题目提到"附件 .fna 基因组文件":附件分发机制已落地(`data/attachments/<qid>/**`
  与 `_shared/**`,冒烟测试覆盖),3 株真实厌氧氨氧化菌参考基因组
  (Brocadia sinica MAG_7 / Kuenenia stuttgartiensis HKUEN01 / Scalindua sp.AMX11,
  来自 NCBI GCA 公开档案)随包发布于 `data/attachments/_shared/genomes/`;
  但 T1 题面中的 P1~P8 占位档案名与真实 NCBI 基因组的映射**尚未建立**,作答仍按
  题面所述走"仅提供属级分类学注释"分支,映射建立前不得宣称已做基因组实证考核
- 客观题型校验器已就位:`graders.fdp_check`(缺陷谱逐模块比对)与
  `graders.rank_check`(供体排序 NDCG+逐对一致率),配套金标准数据在 v2.0 题型接入时补齐
- LLM judge 输出已做鲁棒 JSON 解析(容忍围栏/噪声/缺字段),极端情况记为 `error` 行不中断整体
