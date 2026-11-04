> [revised 2026-10-23] ThetaVerse 更新至 0.3.0 后复验：本文档所引接口 read_biom / read_kegg_hits / core_metrics / ThetaData 在 0.3.0 下全部可用（实测），接入点不变；唯一变化是基因预测入口经适配层直连 pyrodigal（thetaverse.external 0.3.0 断裂，见复验报告）。原 10-20 版本内容以下全文保留。

# C：用户输入后的数据分析 Agent 流程（设计文档）

> 口径对齐（20261020 会议）：群落筛选及后续生理分析统一定义为**"设计"**；
> 基因组功能分析结果**输出报告给小江师兄作为约束条件输入**；
> 相容性溶质与环境约束**入 RAG 知识库**（不嵌公式）；16S/MAG 管线已封装（本轮只接入）。

## 一、流程总览

```
用户输入（自动判别）
   │  analyze_input.py --input <文件或菌名> --type auto
   ▼
┌────────────── 路由层 detect_type() ──────────────┐
│ .qza/.biom            → 16s 场景                  │
│ .fna/.fasta/.fa(.gz)  → mag 场景                  │
│ 其他文本（菌名）       → taxon 场景                │
└──────────────┬───────────────────────────────────┘
               ▼
┌─ 16s ────────────────────────────────────────────┐
│ QIIME2 artifacts → thetaverse read_biom          │
│ → ThetaData → core_metrics（α/β/PCoA）           │
│ 输出：alpha_diversity.tsv / PCoA_*.tsv / stats   │
│ [上游 dada2 等在 QIIME2 框架（Linux/conda）]      │
└──────────────────────────────────────────────────┘
┌─ mag ────────────────────────────────────────────┐
│ FASTA → PyrodigalBridge 基因预测 → 蛋白 FAA      │
│ → KO 注释（生产：工作站 blastp vs KEGG；          │
│   本机：参考蛋白组精确匹配/受阻标注）             │
│ → hits(8列契约) → read_kegg_hits → ThetaData     │
│ → 氮循环过程谱 + core_metrics                     │
│ 输出：stats_A1.json / 过程谱 / alpha / FAA        │
└──────────────────────────────────────────────────┘
┌─ taxon ──────────────────────────────────────────┐
│ 菌名 → NCBI esearch→esummary→FTP 下载（SHA256）  │
│ → 自动转 mag 场景（进程内链式调用）               │
│ 输出：provenance_A3.json + mag 全部产物           │
└──────────────────────────────────────────────────┘
               ▼
结构化结果（运行摘要.json，schema 见下）
               ▼
┌─ 交付小江（约束条件输入）────────────────────────┐
│ 基因组功能分析报告：基因组统计 + KO 命中 +        │
│ 24 类氮循环过程谱 + 相容性溶质关联（经验库查询）  │
└──────────────────────────────────────────────────┘
               ▼
┌─ Oxpecker 接入（证据消费）────────────────────────┐
│ run_case(payload) 的 InputSpec.files 注入分析产物 │
│ （FileRef 指向 运行摘要.json 与报告文件），       │
│ 由 intake→planner→research 链路作为可追溯证据；   │
│ 约束知识（相容性溶质/环境）走 Oxpecker rag/       │
│ service.py（知识库检索，不进公式）。              │
└──────────────────────────────────────────────────┘
```

## 二、运行摘要.json schema（每场景统一）

```json
{
  "scenario": "mag | 16s | taxon",
  "input": "用户原始输入",
  "pipeline": "封装管线标识（交付_剩余任务_20261020/scripts/...）",
  "outputs_dir": "产物目录",
  "stats": "统计文件路径",
  "elapsed_seconds": 0.0,
  "exit": "ok | blocked",
  "note": "受阻/口径说明（如有）",
  "provenance": "溯源文件路径（taxon 场景）"
}
```

## 三、给小江的基因组功能分析报告 schema（约束条件输入）

| 字段 | 来源 | 用途 |
|---|---|---|
| mag_id / 基因组统计 | stats_A1.json.gene_calling | 基本面（contigs/大小/GC/基因数/编码密度） |
| KO 命中谱 | hits 表 → ko_per_mag | 氮代谢约束的基因存在性 |
| 氮循环过程谱（24 类） | 氮循环过程谱_每MAG.tsv | 按过程筛选群落（约束条件①氮循环） |
| 相容性溶质合成/转运潜力 | 经验库 DB 查询（genome_id 关联） | 约束条件②相容性溶质 |
| 环境条件匹配度 | 经验库 env_conditions（盐度/pH/温度，缺失=NULL） | 约束条件③环境 |
| 受阻/缺失标注 | stats + 报告内 [受阻]/[缺失] | 审计与补数依据 |

## 四、Oxpecker 接入点（已核对其代码）

- 入口：`oxpecker.api.run_case(payload, use_llm, run_root)` → `agent.workflow.run`；
  payload 按 `domain/contracts.py` 的 `CaseSpec/InputSpec/FileRef` 构建。
- 注入方式：分析完成后把 `运行摘要.json` + 功能分析报告路径作为 `InputSpec.files` 的
  `FileRef` 传入，Oxpecker 的 IntakeAgent→Planner→Research 链将其作为**可追溯证据**消费；
  `domain/input_adapters.py` 为适配层，无需改动其核心。
- 知识检索：相容性溶质/环境约束走 `src/oxpecker/rag/service.py`（知识库已含
  `环境工程专利` 子库与 `env_increment` 增量），遵循会议"入知识库不嵌公式"的口径。

## 五、演示记录（全部真跑，2026-10-20）

| 场景 | 输入 | 耗时 | 结果 |
|---|---|---|---|
| mag | mock_genome.fna（模拟基因组） | 4.5s | 基因预测+受阻口径+摘要 ✓ |
| 16s | QIIME2 官方 artifacts 目录 | 2.4s | 34×770 落表+多样性+PCoA ✓ |
| taxon | "Candidatus Scalindua brodae" | 20.0s | NCBI 下载(SHA256)→mag 链 ✓ |

复现：`python scripts\analyze_input.py --input <输入> [--type auto]`；
三场景日志：`scripts\日志_B_场景*.txt`；摘要：`B_三场景接入\运行演示\<场景>\运行摘要.json`。
