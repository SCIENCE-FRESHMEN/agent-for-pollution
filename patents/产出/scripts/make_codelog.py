# -*- coding: utf-8 -*-
"""Assemble 代码与运行日志 markdown: embeds the four on-disk scripts + run logs."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUTD = r"C:\Users\25416\Desktop\agent for pollution\patents\产出"
SC = os.path.join(OUTD, "scripts")
dst = os.path.join(OUTD, "代码与运行日志_知识库升级四任务_20261002.md")

def read(p):
    return open(p, encoding="utf-8").read().rstrip() + "\n"

code1 = read(os.path.join(SC, "task1_formulation.py"))
code2 = read(os.path.join(SC, "task2_tables.py"))
code3 = read(os.path.join(SC, "task3_graph.py"))
code4 = read(os.path.join(OUTD, "cross_lingual_rewriter.py"))
log1 = read(os.path.join(SC, "task1_run.log"))
log2 = read(os.path.join(SC, "task2_run.log"))
log3 = read(os.path.join(SC, "task3_run.log"))
log4 = read(os.path.join(SC, "task4_run.log"))

doc = f"""# 知识库升级四任务：完整代码与运行日志

**日期**：2026-10-02　**执行环境**：Windows / Python 3 (`.rc_venv`)，依赖 `pypdf`、`pdfplumber 0.11.10`、`openpyxl`
**代码位置**：`patents/产出/scripts/`（Task 1–3 与校验脚本）；Task 4 类文件：`patents/产出/cross_lingual_rewriter.py`

---

## Task 1：参数化配方数据库抽取（Formulation DB）

**输出**：`patents/产出/formulation_database.csv`（1934 条记录 × 12 字段，覆盖 193 份专利）
**执行日志**：

```text
{log1}```

```python
{code1}```

---

## Task 2：Table-Aware 切片增强（表格感知 RAG）

**输出**：`patents/产出/RAG知识库/chunks_with_tables.jsonl`（8103 行 = 原 7941 切片 + 162 个表格切片，覆盖 62 份专利）
**执行日志**：

```text
{log2}```

```python
{code2}```

---

## Task 3：GraphRAG 基础图谱构建（节点与边）

**输出**：`patents/产出/graph_nodes.csv`（424 节点）、`patents/产出/graph_edges.csv`（1009 边）
**执行日志**：

```text
{log3}```

```python
{code3}```

---

## Task 4：跨语言 Query 重写器（Cross-Lingual Rewriter）

**输出**：类文件 `patents/产出/cross_lingual_rewriter.py`（可直接 import；`rewrite()` 返回布尔检索式列表，`rewrite_weighted()` 返回带权列表）
**测试日志**（3 个典型中文查询）：

```text
{log4}```

```python
{code4}```

---

## 复现命令

```bat
cd /d "C:\\Users\\25416\\Desktop\\agent for pollution"
.rc_venv\\Scripts\\python.exe patents\\产出\\scripts\\task1_formulation.py   > patents\\产出\\scripts\\task1_run.log 2>&1
.rc_venv\\Scripts\\python.exe patents\\产出\\scripts\\task2_tables.py       > patents\\产出\\scripts\\task2_run.log 2>&1
.rc_venv\\Scripts\\python.exe patents\\产出\\scripts\\task3_graph.py        > patents\\产出\\scripts\\task3_run.log 2>&1
.rc_venv\\Scripts\\python.exe patents\\产出\\cross_lingual_rewriter.py      > patents\\产出\\scripts\\task4_run.log 2>&1
```

## 工程备注

1. Task 1 含 LLM 通道（`response_format={{"type": "json_object"}}`）。本机未配置 `OPENAI_API_KEY`，脚本 3 次连接尝试失败后自动降级为受控词表+正则抽取；每条记录的 `extraction_method` 列标记实际路径（`llm` / `rule_based_v1`），`evidence_snippet` 列保留原文锚点。配置 key 后重跑即得 LLM 版。
2. Task 2 排除 111 份无文本层扫描件（与本知识库边界一致），支持断点续跑（`task2_progress.json`），默认 45 分钟墙钟预算（本次 664 秒即全部完成）。
3. Task 3 的 `CITES` 边来自全文交叉引用正则（库内实际命中 1 条：CN117466434A → CN111717982A）；`SAME_FAMILY` 为归一化标题代理（6 组 20 边，evidence 列标注 `normalized_title_proxy`），非官方 INPADOC 同族。
4. Task 4 词典覆盖中/英/日/德/法/西六语等价术语与 9 类溶质变体；`use_llm=True` 时叠加 LLM 同义扩展（同样需要 API key）。
"""
with open(dst, "w", encoding="utf-8") as f:
    f.write(doc)
print("written:", dst, len(doc), "chars")
