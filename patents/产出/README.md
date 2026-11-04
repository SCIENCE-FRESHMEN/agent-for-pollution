# 相容性溶质（compatible solute）专利知识库 · 交付说明（README）

**交付日期**：2026-10-02
**任务来源**：项目任务表 ran 分工——「总结专利内容，造 RAG」
**数据底座**：`patents/pdf/` 内 410 份专利 PDF（检索源 Google Patents，精确短语 `"compatible solute"`，检索日 2026-09-14，著录台账含 SHA256 与 PDF 直链）

---

## 一、一分钟速览

| 项目 | 结果 |
|---|---|
| 专利合规校验 | 410 份全文核对 → **227 份纳入** / 111 份扫描件无法校验 / 72 份剔除（含 13 份词组同形异义） |
| 系统性综述 | 1 份（六章，Nature 综述体例，全部结论锚定专利原文） |
| RAG 知识库 | **8103 个自包含切片**（227 专利全文窗口 7941 + 表格切片 162），三级信息标记（权利要求/实施例/背景技术） |
| 配方数据库 | **1934 条**结构化记录（溶质-场景-浓度/配比-量化效果四元组，含原文锚点），覆盖 193 份专利 |
| GraphRAG 图谱 | **424 节点 / 1009 边**（Patent-Applicant-Solute-IPC 四类节点，6 种关系） |
| 检索工具 | 跨语言查询重写器（中/英/日/德/法/西六语布尔检索式）+ 检索提示词模板 |

**建议审阅顺序**：本 README → ①《专利系统性综述》→ ②《合规校验与知识库质量自检报告》→ ③ 抽查 `RAG知识库_可读版.md` 任一专利条目与原文 PDF 对照 → ④ `formulation_database.csv` / 图谱 CSV 按需查阅。

---

## 二、目录结构与文件清单

```
patents/
├── pdf/                          410 份专利 PDF 原文（源数据，SHA256 已登记）
├── txt/                          pypdf 提取的全文文本（300 份有文本层）
├── analysis/                     校验与统计中间产物
│   ├── compliance.csv            410 份逐件校验判定（公开号/命中数/判定/依据）
│   ├── review_table.md           227 份纳入专利总表（国别/年/申请人/标题/校验依据）
│   ├── grounding_records.json    每份专利的溯源记录（短语上下文摘录×8、溶质/主题标签）
│   ├── excluded_and_unverifiable.csv   剔除+无法校验名单（含原因）
│   └── extract_manifest.csv      PDF 提取台账（页数/字符量/错误）
│
└── 产出/                         ★ 交付物目录（本 README 所在）
    ├── README.md                 ← 本文件
    ├── 专利系统性综述_compatible_solute_20261002.md     任务1成果：六章系统性综述
    ├── 合规校验与知识库质量自检报告.md                   校验方法、13 份同形异义清单、局限
    ├── 代码与运行日志_知识库升级四任务_20261002.md       四个升级任务的完整代码+日志
    ├── formulation_database.csv  配方数据库（1934 条 × 12 字段）
    ├── graph_nodes.csv           图谱节点（424）
    ├── graph_edges.csv           图谱边（1009，含 evidence 列）
    ├── cross_lingual_rewriter.py 跨语言查询重写器（可 import 的类）
    ├── RAG检索提示词.md           检索系统提示词模板 + 查询构造表 + few-shot
    ├── RAG知识库/
    │   ├── chunks.jsonl                 7941 个文本切片（机器可读主库）
    │   ├── chunks_with_tables.jsonl     8103 行（主库 + 162 表格切片，推荐用这份）
    │   ├── theme_digest_chunks.jsonl    8 类主题索引切片
    │   ├── metadata_index.csv           227 份专利 × 15 字段元数据
    │   └── RAG知识库_可读版.md           人类可读版（按主题分组，逐件条目+原文摘录）
    └── scripts/                  本轮升级代码（task1–task4、校验、运行日志、断点文件）
```

**首轮建库管线代码**（与产出同源，可复现全流程）位于 `patents/` 根目录：
`extract_all.py`（PDF→TXT）→ `compliance_check.py`（多语言全文合规校验）→ `adjudicate.py` / `finalize_corpus.py`（人工裁定与语料固化）→ `export_review_data.py`（总表/统计）→ `build_rag.py`（双维度切片）→ `gen_readable.py`（可读版）→ `verify_kb.py`（完整性校验）；审计脚本 `debug_excluded.py`、`inspect_suspects.py`、`verify_edge_cases.py`、`final_check.py`、`audit_passes.py` 记录了对每一份剔除专利的人工复核过程。

---

## 三、方法摘要（详见自检报告）

1. **合规口径**：落实 20260909 原始检索规则（`compatible solute` 两单词缺一不可），并落实为**专利原文全文核对**；中文原文核对固定术语「相容性溶质」，日文/德文/法文/西班牙文原文分别核对 `相溶性溶質 / kompatible Solute / solutés compatibles / solutos compatibles`。仅字面命中但语义无关的 13 份（电化学电解质、油田示踪液、3D 打印包埋材料等）已作为「同形异义」单独剔除并留痕。
2. **切片策略**：专利个体（1500 字符滑动窗口+首页著录切片）与科学主题（8 类索引）双维度；每条切片携带 15 字段元数据（专利号/日期/申请人/IPC/主题/溶质标签/SHA256/字符偏移），并按权利要求书、实施例、背景技术做**三级信息标记**，防止把背景技术转述的他人数据误当本专利效果。
3. **反幻觉约束**：知识库内 `text` 字段为 PDF 提取文本的逐字窗口；综述中一切跨专利概括均显式标注「基于专利文本的归纳」；原文信息不足处标注【原文信息不足，无法确认】。

---

## 四、复现指南

环境：Windows + Python 3（依赖 `pypdf`、`pdfplumber`、`openpyxl`、`pandas`，均已装入 `.rc_venv`）。

```bat
cd /d "C:\Users\25416\Desktop\agent for pollution"
.rc_venv\Scripts\python.exe patents\extract_all.py            rem ① PDF→TXT（约 3 分钟）
.rc_venv\Scripts\python.exe patents\compliance_check.py       rem ② 全文合规校验
.rc_venv\Scripts\python.exe patents\adjudicate.py             rem ③ 人工裁定固化
.rc_venv\Scripts\python.exe patents\export_review_data.py     rem ④ 总表与统计
.rc_venv\Scripts\python.exe patents\build_rag.py              rem ⑤ 构建切片库
.rc_venv\Scripts\python.exe patents\gen_readable.py           rem ⑥ 可读版
.rc_venv\Scripts\python.exe patents\verify_kb.py              rem ⑦ 完整性校验
rem —— 升级四任务（代码与日志：patents\产出\scripts\）——
.rc_venv\Scripts\python.exe patents\产出\scripts\task1_formulation.py
.rc_venv\Scripts\python.exe patents\产出\scripts\task2_tables.py
.rc_venv\Scripts\python.exe patents\产出\scripts\task3_graph.py
.rc_venv\Scripts\python.exe patents\产出\cross_lingual_rewriter.py
```

---

## 五、使用边界（审阅与引用时请注意）

1. **111 份扫描件未入库**：多为 1990s–2010s 早期 WO/CA/CN/HK 件，无文本层且本机无 OCR；本库对 2019 年前的覆盖存在文字层偏差。名单见 `analysis/excluded_and_unverifiable.csv`。
2. **纳入 ≠ 法律有效**：所有专利的法律状态未经官方核验；本交付物为技术与情报用途，不构成法律意见。
3. **同族未归并**：Allergan（HK/US/NZ）、Merck（CN/US/JP/ES）、bitop（多实体名）等家族成员为独立条目，统计时请按申请人+标题去重。
4. **配方数据库当前为规则抽取版**：`extraction_method=rule_based_v1`；配置 `OPENAI_API_KEY` 后重跑 `task1_formulation.py` 可得 LLM 抽取版（代码通道已内置）。每条记录附 `evidence_snippet` 原文锚点，引用前请对照原文。
5. **「未检出」≠「不存在」**：综述第 5 节的空白分析仅针对本 227 件语料，不构成对全球专利态势的完备判断。

---

## 六、关键结论摘要（供快速引用，出处见综述 §4）

- **废水方向**（与本项目最相关，14 件主分类）：CN118956681B（60 g/L 盐度脱氮效率 95.87%，胞内四氢嘧啶 188.96 mg/g）；CN117285158A（全程自养脱氮海藻糖 0.1–1.6 mM/L）；CN116332375A（复配渗透保护剂 0.2–0.4 wt%）；CN115651870A（甜菜碱恢复铁抑制 anammox）；CN111717982A（加压 0.1–0.5 MPa 耦合投加）。
- **专利空白**：「高盐 anammox 投加产相容性溶质功能菌做生物强化」在本语料中未检出；「处理-生产耦合」（同步脱氮联产四氢嘧啶）2024–2025 年刚出现 3 件，尚无专利族。
- **制造-应用格局**：德企 bitop/Merck 与葡萄牙 IBET 系构成第一代应用版图（1998–2015）；中国 2019 年后爆发集中于制造端（华熙生物 13 件居首）与化妆品配方端。
