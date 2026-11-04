---
language:
  - zh
  - en
license: mit
task_categories:
  - question-answering
tags:
  - wastewater-treatment
  - environmental-engineering
  - llm-benchmark
  - anammox
  - compatible-solutes
  - rubric-grading
size_categories:
  - 1K<n<10K
---

# WWBench: Wastewater Biological Treatment Benchmark

面向废水生物处理领域的 LLM/智能体评测基准,模式仿照
[BixBench](https://huggingface.co/datasets/futurehouse/BixBench)(FutureHouse 生信基准):
**题库(dataset)与评测框架(harness)分离,results 附基线校准数据**。

## 数据集概览

| 项 | 值 |
|---|---|
| 题目总数 | 1142 |
| 打分要点总数 | 4644 |
| 题型 | T1 总体耐盐化措施(因子设计)/ E 环境工程 / T7 培养基设计 / A 主导溶质 / T5 菌株选择 / T10 场景推理 |
| 评分模式 | rubric_6dims(六维 0-2 分 + 要点逐条命中 + 数值容差校验) |
| 验证子集 | `questions-verified-52.csv`(专家撰写金标准,对应 BixBench-Verified-50) |
| 语言 | 中文(领域术语中英混排) |

## 目录结构

```
WWBench_v1.0/
├── README.md                  # 本卡片
├── LICENSE / CITATION.cff / MANIFEST.sha256
├── dataset/                   # 对应 BixBench 的 HF 数据集部分
│   ├── questions.csv          # 主题库(12 列,见下文字段说明)
│   ├── questions-verified-52.csv
│   ├── provenance.md          # 题目来源分层(重要)
│   └── capsules/<question_id>.zip   # 每题工作区材料(内含 Data/references.txt)
├── harness/                   # 对应 BixBench 的 GitHub 评测框架
│   ├── wwbench/  scripts/  configs/  tests/
│   └── requirements.txt
└── results/                   # 离线三档校准基线(oracle / degraded / mock)
```

## questions.csv 字段(12 列)

| 列 | 说明 |
|---|---|
| question_id | 唯一题号(q-061 起) |
| 标签 / 主题 / 难度 / 题型 | 元数据,用于分层报告 |
| question | 题面(含结构化作答步骤要求) |
| ideal_keypoints(打分用) | 打分要点,以全角分号"；"分隔(条目内不含分号) |
| ideal_detail(参考) | 参考答案(judge 评分与 oracle 校准的金标准) |
| eval_mode | 评分模式,当前全部 rubric_6dims |
| categories | 多标签类别(英文逗号分隔,一题可属多组) |
| 参考文献 | 来源文献(DOI 或内部编号;教科书级来源以书名标注) |
| 细分 | 领域细分(废水生物处理) |

## 加载示例

```python
import pandas as pd
df = pd.read_csv("dataset/questions.csv", encoding="utf-8-sig")
# 或使用 harness 的解析器(自动拆分要点/抽取因子变量):
# from wwbench.dataset import load_questions
# questions = load_questions("dataset/questions.csv")
```

## 评测方式

```bash
cd harness
python tests/test_smoke.py                                    # 离线自检
python scripts/run_bench.py --config configs/run_oracle.yaml   # 校准上界
python scripts/run_bench.py --config configs/run_openai.yaml   # 真实模型(OpenAI 兼容端点)
```

指标:逐次达标率 / 多数达标率(majority-vote 口径)/ 拒答率 / 数值召回 /
六维分;分层到 标签/题型/优势菌/目标盐度/基因组档案 等轴。详见 harness/README.md。

## 题目来源与限制(请务必阅读 dataset/provenance.md)

- 52 题为领域专家撰写(金标准);
- 其余由 AI 按分层种子起草(文献要点/教科书共识/因子模板),已过自动质检,
  **未经领域专家逐题终审**;
- T1 家族为 优势菌×基因组档案×盐度区间 的因子设计,存在模板族相关性,
  汇报总体指标时建议同时给出"独立题面口径";
- 打分要点数实测为 1~5 条/题(均值 4.07);capsule 内引文部分在源数据即被截断,
  T1 题面的 .fna 档案名与真实基因组映射未建立——详见 dataset/provenance.md
  "已知限制"(v1.0.1)。

## 版本

- **v1.0.1(2026-09-27)**:修复发布包 harness/data 缺失导致的开箱即坏
  (冒烟测试 19/19 通过);evidence 维判分修复(原全队列恒 0.5 无区分度);
  三档校准基线按 5 次复跑重跑;文档口径对齐实测数据。
- v1.0.0(2026-09-24):首次发布。

## 引用

见 CITATION.cff。
