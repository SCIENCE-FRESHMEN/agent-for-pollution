# -*- coding: utf-8 -*-
"""构建 WWBench 标准发布包(仿 BixBench 的 HF 数据集 + GitHub 框架 + results 三段式)。

产出:WWBench_v1.0.zip(含 dataset/ harness/ results/ + 数据集卡片 + 许可 + 引用 + 清单)。
用法:python scripts/build_release.py [--out ~/Desktop/WWBench_v1.0.zip]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wwbench.dataset import load_questions  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

DATASET_CARD = """---
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
| 题目总数 | {n_q} |
| 打分要点总数 | {n_kp} |
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
  汇报总体指标时建议同时给出"独立题面口径"。

## 引用

见 CITATION.cff。
"""

PROVENANCE = """# 题目来源分层(provenance)

| 层 | 题号区间 | 数量 | 生成方式 | 可信度定位 |
|---|---|---|---|---|
| L0 专家原题 | q-061~q-200 | 52 | 领域专家撰写(用户提供) | 金标准,评测口径锚点 |
| L1 AI 手写 | q-201~q-252 | 28 | 按文献要点逐题撰写,引用题库既有 DOI | 高,建议专家抽审 |
| L2 因子模板 | q-301~q-312 | 12 | 8 基因组档案 × 新盐度区间组合 | 同 T1 家族口径 |
| L3 大规模程序化 | q-313~q-1362 | 1050 | 30+ 模板 × 正交因子轴组合生成,数值按化学计量推导 | 中,用于扩容与分层统计 |

全部题目经过统一质检门禁:schema 校验、条目内无分号、逐字查重
(对金标准与批内双向)、oracle 自评一致性。打分要点数实测分布为 1~5 条/题
(均值 4.07,v1.0.1 按 1142 题逐行复核实测口径修正,原"3-8"表述系生成器
配置注释,与发布数据不符)。模板族相关性由 audit_dataset.py 如实
报告(独立题面数与簇规模),不在发布数据中隐藏。

## capsules 约定(对应 BixBench 的 data_folder)

`capsules/<question_id>.zip` 内含 `Data/references.txt`(该题参考文献线索)。
已知限制(v1.0.1 披露):①引文取自题库"参考文献"列,部分条目在源数据导入时
即被截断为 ~45 字符(如 "L0430 Glycine Betaine and Ectoine Are the Majo"),
修复管线见 harness/scripts/repair_references.py;②部分 T1 题面声称的
`*.fna` 基因组附件为因子设计占位名,P1~P8 与真实 NCBI 基因组的映射尚未建立,
真实参考基因组现发布于 `harness/data/attachments/_shared/genomes/`(3 株),
经智能体模式的 `_shared` 分发机制进入每题工作区。
"""

CITATION = """cff-version: 1.2.0
message: "If you use WWBench, please cite."
title: WWBench: Wastewater Biological Treatment Benchmark for LLMs
authors:
  - family-names: WWBench
    given-names: Contributors
version: 1.0.1
date-released: "2026-09-27"
license: MIT
notes: "v1.0.1 发布包修复:harness/data 随包同步(开箱冒烟 19/19 通过);evidence 维判分修复;口径对齐实测数据。"
"""

REQUIREMENTS = """pandas>=2.0
PyYAML>=6.0
openai>=1.30
matplotlib>=3.7
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _rmtree(path: Path) -> None:
    """删除目录,自动解除继承自备份链的只读位。"""
    import os
    import stat

    def _force_rm(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onerror=_force_rm)


def build(staging: Path) -> None:
    if staging.exists():
        _rmtree(staging)
    (staging / "dataset" / "capsules").mkdir(parents=True)
    (staging / "harness").mkdir(parents=True)
    (staging / "results").mkdir(parents=True)

    questions = load_questions(ROOT / "data" / "questions.csv")

    # ---- dataset ----
    shutil.copy(ROOT / "data" / "questions.csv", staging / "dataset" / "questions.csv")
    shutil.copy(ROOT / "data" / "questions_v0_52.csv",
                staging / "dataset" / "questions-verified-52.csv")
    (staging / "dataset" / "provenance.md").write_text(PROVENANCE, encoding="utf-8")

    for q in questions:  # 每题一个 capsule zip(内含 Data/ 目录,仿 BixBench 约定)
        zp = staging / "dataset" / "capsules" / f"{q.question_id}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Data/references.txt", "\n\n".join(q.references) or "(无参考文献)")

    # ---- harness(排除缓存) ----
    for sub in ["wwbench", "scripts", "configs", "tests"]:
        dst = staging / "harness" / sub
        shutil.copytree(ROOT / sub, dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_patch*"))
    shutil.copy(ROOT / "README.md", staging / "harness" / "README.md")
    (staging / "harness" / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")

    # ---- harness/data(v1.0.1 修复 P1-4 打包缺陷) ----
    # v1.0 的发布包把题库只放在顶层 dataset/,而 harness 的冒烟测试与 runner 均按
    # harness/data/ 寻址,导致开箱即坏。现随包同步:题库、审批门禁 fixture、附件。
    import pandas as pd  # noqa: E402  — 依赖 wwbench.dataset,环境必然可用

    harness_data = staging / "harness" / "data"
    harness_data.mkdir(parents=True)
    shutil.copy(ROOT / "data" / "questions.csv", harness_data / "questions.csv")
    fixture = pd.read_csv(ROOT / "data" / "questions.csv", encoding="utf-8-sig", nrows=1)
    fixture.to_csv(harness_data / "pending_review.csv", index=False, encoding="utf-8-sig")
    attachments_src = ROOT / "data" / "attachments"
    if attachments_src.exists():
        shutil.copytree(attachments_src, harness_data / "attachments",
                        ignore=shutil.ignore_patterns("__pycache__"))

    # ---- results(裁掉 responses.csv 与工作区/轨迹,保留报告与评分) ----
    for run in ["oracle_calibration", "oracle_degraded50", "mock_smoke"]:
        src = ROOT / "outputs" / run
        dst = staging / "results" / run
        if not src.exists():
            continue
        dst.mkdir(parents=True)
        for name in ["report.md", "summary.json", "question_level.csv", "grades.csv"]:
            if (src / name).exists():
                shutil.copy(src / name, dst / name)
        if (src / "plots").exists():
            shutil.copytree(src / "plots", dst / "plots")
    for name in ["comparison_report.md", "comparison.png"]:
        if (ROOT / "outputs" / name).exists():
            shutil.copy(ROOT / "outputs" / name, staging / "results" / name)

    # ---- 卡片 / 许可 / 引用 ----
    (staging / "README.md").write_text(
        DATASET_CARD.format(n_q=len(questions), n_kp=sum(q.num_keypoints for q in questions)),
        encoding="utf-8",
    )
    (staging / "CITATION.cff").write_text(CITATION, encoding="utf-8")
    (staging / "LICENSE").write_text(
        "MIT License\n\nCopyright (c) 2026 WWBench Contributors\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the \"Software\"), to deal\n"
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in\n"
        "all copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND.\n",
        encoding="utf-8",
    )

    # ---- MANIFEST ----
    lines = []
    for f in sorted(p for p in staging.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256"):
        lines.append(f"{sha256(f)}  {f.relative_to(staging).as_posix()}")
    (staging / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home() / "Desktop" / "WWBench_v1.0.zip"))
    args = ap.parse_args()
    out = Path(args.out)

    staging = ROOT / "_release_staging" / "WWBench_v1.0"
    build(staging)

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    # 统一使用正斜杠路径,避免 Windows 反斜杠 zip 的跨平台解压问题
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(p for p in staging.rglob("*") if p.is_file()):
            zf.write(f, f"WWBench_v1.0/{f.relative_to(staging).as_posix()}")

    n = len(zipfile.ZipFile(out).namelist())
    print(f"[release] {out} ({out.stat().st_size // 1024} KB, {n} 个文件)")
    _rmtree(ROOT / "_release_staging")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
