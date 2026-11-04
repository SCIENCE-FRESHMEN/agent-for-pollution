# 交付说明：氮循环 + 相容性溶质（合成/转运）数据库整理

对应 20261013 任务表 PPT「2.数据分析部分 ② 数据库整理」前两项：

1. **盐湖所有基因组的氮循环注释信息** —— 从工作站 6 `/media/HD2/QXJ/ran/1Nitrogen` 的两份 KEGG 比对结果中，按《氮循环Ko号.xlsx》摘出氮循环 KO 的行；
2. **盐湖所有基因组的相容性溶质合成和转运信息** —— 转运：按《Comp_Sul transDB.xlsx》摘行并回填 transDB 第 2/3/4 列注释；合成：两个结果表合并为一个文档。

生成日期：2026-10-14。

## 一、交付内容

| 文件 | 内容 | 行数 |
|---|---|---|
| `1Nitrogen/氮循环KO命中行_env_ench合并.tsv` | 两个大 TSV 中命中氮循环 64 个 KO 的行，env + ench 合一 | 552,808 |
| `2CompSul/相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv` | 命中 transDB 77 个转运 KO 的行，行尾追加 transDB 第 2/3/4 列 | 1,184,624 |
| `2CompSul/相容性溶质合成_env_ench合并.xlsx` | 两个合成结果表纵向合并 | 112,475 |
| `字典_原始输入/` | 两个 KO 字典原件备份（保证本夹自洽可溯源） | — |
| `scripts/` | 全部生成脚本 + 统计 JSON + 运行日志 + QA 报告（可复跑） | — |
| `QA报告.txt`（在 scripts/ 下） | 全部校验结果 | — |

## 二、输入与来源

- 氮循环源文件（工作站 `1Nitrogen` 目录，本机已解压于 `task/Nitrogen_3files/`）：
  - `KEGG_des_env_kegg_e-5_num1_similarity30.tsv`：76,343,624 行（15.4 GB）
  - `KEGG_des_ench_kegg_e-5_num1_similarity30.tsv`：14,301,884 行（2.8 GB）
  - 均为无表头 13 列 BLAST tabular 格式：query_id、subject_id、pct_identity、alignment_length、mismatch、gap_open、query_start、query_end、subject_start、subject_end、evalue、bit_score、subject_description。
- 字典（**当前生效 v2**）：`氮循环Knumber_process.xlsx`（2026-10-15 更新，64 个 KO，新增第 3 列 "N-cycle process" 氮循环过程标注）。v1 为 `氮循环Ko号.xlsx`（2026-10-13，72 个 KO），两版均存于 `字典_原始输入/` 备查。
  - v2 相对 v1 删除 8 个 KO，全部为碳酸酐酶（K01672、K01673、K01674、K01743、K18245、K18246、K28955、K28956），无新增；氮循环输出相应由 596,760 行收敛为 552,808 行（逐源精确核验：env 506,681→467,950、ench 90,079→84,858）。
- 转运字典：`Comp_Sul transDB.xlsx`（78 行、77 个唯 KO）。
- 合成结果：`CompSul_Biosys_MAG_env.xlsx`（表 MAG_CompSul_TPM，79,000 行）、`CompSul_Biosys_faa_ench.xlsx`（表 MAG_CompSul，33,475 行；另含 Entry_Mapping 表 80 行，已一并附在合并 xlsx 中）。
  - 注：任务书写的 `CompSul_Biosys_MAG_ench.xlsx` 在实际文件夹中为 `CompSul_Biosys_faa_ench.xlsx`，已按实际文件处理。
- env / ench 两个源沿用工作站原始命名（env = 环境样品基因组、ench = 富集培养物，如需精确含义请与上游确认）；输出 `source_file` 列标记每行来自哪一源。

## 三、输出格式

- **氮循环 TSV**（16 列）= 原 13 列（内容与源文件逐字节一致）+ `source_file`（env/ench）+ `matched_KO`（该行命中的 KO，多个用英文逗号分隔）+ `nit_cycle_process`（来自字典 v2 第 3 列的过程标注；一行命中多个 KO 时取**首个** KO 的过程）。
- **转运 TSV**（18 列）= 原 13 列 + `source_file` + `matched_KO` + transDB 第 2/3/4 列（`comp_sul_gene_name`、`comp_sul_function`、`comp_sul_transport_system`，逐字照抄，制表符已替换为空格）。一行命中多个 KO 时注释取**首个** KO。
- 两个 TSV 首行为表头（源文件本身无表头，此处为便于下游使用而加；如需与源文件同构可删除首行）。
- 合并 xlsx：`合并结果` 表（原 3 列 + `source_file` 标注来源文件与表名）+ `ench_Entry_Mapping` 表。

## 四、方法与关键口径

- KO 匹配：对第 13 列 subject_description 用正则 `\bK\d{5}\b` 提取全部 KO（兼容一条记录多个 KO 的情况），与字典精确匹配；输出行 = 源行原文 + 追加列，**不做任何删改**。
- transDB 中 K10111 出现两行（分属 Sorbitol/Mannitol polyol 与 trehalose/maltose 两个系统），输出中该 KO 的三列注释按列去重后用 ` // ` 连接。
- transDB 第 5–8 列基本为空，仅 K05565、K05568 第 8 列有「关键」标记；按任务要求只并入第 2/3/4 列，该标记未包含在输出中（特此说明，避免信息静默丢失）。
- 氮循环字典与转运字典无交集，不存在同一行同时进两个文件的情况。
- 多 KO 命中行：氮循环 218 行、转运 9,304 行（此类行 matched_KO 为逗号分隔，转运注释与氮过程标注仅对应首个 KO）。
- 氮循环字典 v2 共 64 个 KO，**55 个有命中**，9 个在两源数据中零命中：K00264、K01948、K10534、K15877、K17877、K22896、K22898、K28504、K28761（多为真菌/完整基因组的特异基因，如 amoA、真菌 CYP55、vanadium nitrogenase 亚基等，在盐湖 MAG 最佳命中中未出现，属正常生物学缺失而非漏配；已做源文件字节级复核，见 `scripts/零命中KO复核.txt`）。转运字典 77 个 KO 全部有命中。

## 五、质量核验（详见 scripts/QA报告.txt）

1. 行数三方核验：扫描计数 = 输出回读计数 = 全量重扫计数（env 76,343,624 行 / ench 14,301,884 行，无畸形行）。
2. **全量字节级复核**：以同一逻辑重扫 18.2 GB 源文件生成临时副本，与交付输出逐字节比对完全一致（氮循环 123,873,450 B、转运 379,245,393 B）。
3. 字典符合性：输出每行 matched_KO 均属对应字典；转运行的追加注释与 transDB 查表 100% 一致；氮循环行的描述列均包含其 matched_KO。
4. 抽样溯源：从输出各源抽样，回源文件流式检索，原始 13 列逐字节存在。
5. 源文件处理前后大小不变（只读扫描）。
6. 合成合并 xlsx：合并行数 112,475 = 两源之和；精确重复行 0；两源 MAG（不区分大小写）零重叠；空单元格 0。
7. **独立复现执行**：2026-10-14 按 prompt 从零重跑全链路（提取→合并→QA→零命中复核），全部数字与首次运行逐项一致，两份 TSV 字节级复现（日志见 `scripts/运行日志_首次全量扫描.txt` 与 `scripts/运行日志_复现扫描20261014.txt`）。
8. **字典 v2 重做（2026-10-15）**：换用 64 KO 新字典后重跑提取→QA→零命中复核，QA 再次全绿 PASS；转运输出与源行数完全不变（字节一致），氮循环新旧版本差异逐源精确核验（见上文字典条目）。本次运行日志：`scripts/运行日志_新字典64KO_20261015.txt`；v1（72 KO）统计存档：`scripts/stats_extraction_v1_72KO.json`。

## 六、复跑方式（2CompSul 更新后）

```powershell
# 相容性溶质合成（2CompSul 文件夹内容更新后，仅需重跑这一步，约 20 秒）
python "交付_Nitrogen_CompSul_20261014\scripts\run_biosys_merge.py"

# 如字典或大 TSV 也变了，重跑全量提取（约 6 分钟，需 18 GB 源文件在位）+ QA
python "交付_Nitrogen_CompSul_20261014\scripts\run_extraction.py"
python "交付_Nitrogen_CompSul_20261014\scripts\run_qa.py"
```

依赖：Python 3.10+，`openpyxl`、`pandas`（仅合并 xlsx 用到 pandas）。

## 七、注意事项

- 转运输出中同源基因的蛋白同源比对来自 e-5 / similarity 30 筛选后的 KEGG 最佳命中，列为原始比对值，未做二次过滤；下游约束建模时如需阈值（如 identity ≥ 某值）请自行筛选。
- `相容性溶质合成` 的合并为纵向拼接，未去重（两源 MAG 编号体系不同，无重叠行）。
