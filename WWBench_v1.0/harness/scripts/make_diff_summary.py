# -*- coding: utf-8 -*-
"""A2: 生成 v1.0.0 → v1.0.1 全量 diff 摘要 docs/v1.0.1_diff_summary.md。

方法学:v1.0.0 无 git 基线,原 MANIFEST(1228 条)已被就地刷新覆盖,故采用
"整改操作台账(会话记录)重构 + 当前树逐文件枚举核对"双重方法;每一条
新增/修改/重生成判断均有独立证据(修复报告 CSV、日志、哈希清单)。
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness"

# ---- 证据 1:引文修复报告 → 被重写的 capsule 清单 ----
repaired_qids = []
with (HARNESS / "outputs" / "reference_repair_report.csv").open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if int(row["refs_fixed"]) > 0:
            repaired_qids.append(row["question_id"])

# ---- 证据 2:当前树逐目录文件计数 ----
def count_dir(p: Path, pattern="**/*") -> int:
    return sum(1 for x in p.rglob(pattern.split("/")[-1]) if x.is_file()) if p.exists() else 0

tree = {
    "harness/wwbench": count_dir(HARNESS / "wwbench"),
    "harness/scripts": count_dir(HARNESS / "scripts"),
    "harness/configs": count_dir(HARNESS / "configs"),
    "harness/tests": count_dir(HARNESS / "tests"),
    "harness/data(新增)": count_dir(HARNESS / "data"),
    "harness/outputs(v1.0未随包)": count_dir(HARNESS / "outputs"),
    "dataset/capsules": count_dir(ROOT / "dataset" / "capsules"),
    "dataset(顶层)": count_dir(ROOT / "dataset") - count_dir(ROOT / "dataset" / "capsules"),
    "results": count_dir(ROOT / "results"),
    "logs(新增)": count_dir(ROOT / "logs"),
    "docs(新增)": count_dir(ROOT / "docs"),
}

# ---- 证据 3:results 重生成核对(对比 v1.0 报告中的 2284 → 现 5710) ----
import json
n_runs = {}
for run in ["oracle_calibration", "oracle_degraded50", "mock_smoke"]:
    s = json.loads((ROOT / "results" / run / "summary.json").read_text(encoding="utf-8"))
    n_runs[run] = s["overall"]["n_runs"]

# ---- 证据 4:capline——manifest 条目数 ----
manifest_n = len((ROOT / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines())

added = {
    "harness/data/questions.csv": "P1-4 修复:题库随包(harness 寻址布局)",
    "harness/data/pending_review.csv": "P1-4 修复:审批门禁 fixture(build 时自动生成)",
    "harness/data/attachments/_shared/genomes/*.fna ×3": "P0-2b:3 株真实 anammox 参考基因组(NCBI GCA)",
    "harness/scripts/repair_references.py": "P1-8:Crossref 引文回填管线",
    "harness/scripts/refresh_manifest.py": "发布后就地清单重算工具",
    "logs/smoke_cleanroom_20260927.log": "A1 干净室冒烟日志",
    "docs/v1.0.1_diff_summary.md": "A2 本文档",
    "RELEASE_NOTES_v1.0.1.md": "A3 发布说明",
    "harness/scripts/run_real_smoke.py": "B 阶段准备:5 题真实模型冒烟(参数化读 $WWBENCH_API_KEY)",
    "harness/scripts/run_real_full.py": "B 阶段准备:52 题金标准全量",
    "harness/scripts/bootstrap_ci.py": "C 阶段准备:与 degraded 档 delta 的 bootstrap 95% CI",
    "harness/outputs/logs_v1.1/*(4 件)": "整改期运行日志(冒烟/校准/链路边界)",
}
modified = {
    "harness/wwbench/graders.py": "P1-7 evidence 引证锚点法 + NEW-1 IDCG 修复 + fdp_check/rank_check 新增",
    "harness/wwbench/report.py": "NEW-2 空评分表守卫",
    "harness/scripts/run_bench.py": "NEW-2 汇总打印判空守卫",
    "harness/scripts/build_release.py": "P1-4 根因修复 + 文档模板口径同步",
    "harness/tests/test_smoke.py": "+3 测试用例;+计数尾行(A1)",
    "harness/configs/{run_oracle,run_oracle_degraded,run_mock}.yaml": "P1-9 replicates 2→5(3 件)",
    "harness/README.md": "P1-5 口径全量对齐(92→1142 等 7 处)",
    "README.md": "已知限制 + 版本记录(v1.0.1)",
    "dataset/provenance.md": "P1-6 要点数口径 + capsule 已知限制",
    "CITATION.cff": "版本 1.0.0→1.0.1",
    "MANIFEST.sha256": "就地刷新(1228→1299→本轮终态)",
}
regenerated = {
    "results/{3 档}/(report|summary|question_level|grades|plots)": "P1-9/P1-7 重跑后同步(实测 n_runs=5710)",
    "results/comparison_report.md + comparison.png": "compare_runs.py 再生",
    f"dataset/capsules/{','.join(repaired_qids)}.zip 等 {len(repaired_qids)} 件": "P1-8 引文回填写回",
}
deleted = "(无)"

lines = [
    "# v1.0.0 → v1.0.1 全量 diff 摘要",
    "",
    "| 项 | 值 |",
    "|---|---|",
    f"| 基线 | v1.0.0(MANIFEST 1228 条,2026-09-24) |",
    f"| 当前 | v1.0.1(MANIFEST {manifest_n} 条,2026-09-27) |",
    f"| 新增文件 | {len(added)} 类(见下,含 1 个新目录 logs/、1 个新目录 docs/、3 个新目录 harness/data/、harness/outputs/) |",
    f"| 修改文件 | {len(modified)} 类 |",
    f"| 重生成文件 | results 全量 + {len(repaired_qids)} 个 capsule(内容更新,哈希变化) |",
    f"| 删除文件 | {deleted} |",
    "",
    "## 按目录聚合(当前树实测)",
    "",
    "| 目录 | 文件数 |",
    "|---|---|",
    *[f"| {k}/ | {v} |" for k, v in tree.items()],
    "",
    "## 新增明细",
    "",
    *[f"- `{k}` — {v}" for k, v in added.items()],
    "",
    "## 修改明细",
    "",
    *[f"- `{k}` — {v}" for k, v in modified.items()],
    "",
    "## 重生成明细(内容更新,非结构变化)",
    "",
    *[f"- `{k}` — {v}" for k, v in regenerated.items()],
    "",
    "## 校准数据重生成核对",
    "",
    "| run | v1.0.0 n_runs | v1.0.1 n_runs |",
    "|---|---|---|",
    f"| oracle_calibration | 2284 | {n_runs['oracle_calibration']} |",
    f"| oracle_degraded50 | 2284 | {n_runs['oracle_degraded50']} |",
    f"| mock_smoke | 2284 | {n_runs['mock_smoke']} |",
    "",
    "## 方法学声明",
    "",
    "v1.0.0 发布形态无 git 基线,原 1228 条 MANIFEST 已被 v1.0.1 就地刷新覆盖,",
    "无法做逐哈希机检 diff;本文档采用整改操作台账重构 + 当前树枚举核对双重方法,",
    "新增/修改条目均对应整改台账(WWB-REM-20260927-01)中的具体动作,重生成条目",
    "以 reference_repair_report.csv 与 summary.json 的实测字段为证据。若需哈希级",
    "机检 diff,可用 `build_release.py` 重建 v1.0.0 标签产物后比对(需临时回退",
    "harness/data 同步块,不建议;此处如实声明方法学边界)。",
]
out = ROOT / "docs" / "v1.0.1_diff_summary.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"[ok] {out}({len(lines)} 行)")
print("repaired capsules:", len(repaired_qids), repaired_qids[:5], "...")
print("manifest:", manifest_n)
