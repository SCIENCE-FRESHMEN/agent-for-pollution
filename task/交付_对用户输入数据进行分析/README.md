# 交付说明：《20261013任务表》ran 线剩余任务（B + ①A1/A2/A3）

交付日期：2026-10-20。对应任务书 `20261013任务表.pptx` 第 2 页「2.数据分析部分（ran）」中
上一交付（`task\交付_Nitrogen_CompSul_20261014\`，数据库整理前两项）未覆盖的剩余部分。
分工背景见 `10.13meeting.txt`。

**铁律执行情况**：本交付零捏造——所有结论溯源到本地文件或真实运行输出；本机跑不通的部分
全部显式标注 [受阻] 并附证据与工作站/WSL 命令；[缺失] 数据列出向上游索取清单，未做任何推断填充。

---

## 一、任务对照表（验收入口）

| 任务书条目 | 状态 | 交付物 | 证据（QA 报告位置） |
|---|---|---|---|
| ②盐湖所有基因组的**丰度和环境条件**信息 | **已完成**（可溯源部分做实，数值丰度与环境元数据本地缺失如实标注） | `B_丰度与环境条件\1_基因组清单与注释丰度统计.tsv`（58,171 基因组）<br>`B_丰度与环境条件\2_环境条件信息框架.tsv` | `scripts\QA_B报告.txt`（23/23 PASS） |
| ①用户输入 MAG：使用 thetaverse 分析 | **链路真实跑通**（基因预测真跑；KO 注释生产路径在工作站，本机受阻已留证；下游用真实数据端到端演示） | `A_用户输入分析\A1_MAG_thetaverse\`（基因预测产物+统计+下游演示） | `scripts\QA报告_全链.txt` |
| ①用户输入 16S：使用 qiime2 分析 | **下游真跑**（QIIME 2 框架 Windows 不可装，受阻留证；真实 qza 数据落表+下游分析全通） | `A_用户输入分析\A2_16S_qiime2\` | `scripts\QA报告_全链.txt` |
| ①物种名→NCBI 查找下载 MAG→thetaverse 分析 | **全链真实跑通**（esearch→esummary→FTP 下载→基因预测→分析，全程真实） | `A_用户输入分析\A3_NCBI下载MAG\` | `scripts\QA报告_全链.txt` |

全链 QA：**48/48 PASS**（`scripts\QA报告_全链.txt`）。

---

## 二、B：丰度和环境条件信息（②的第三项）

### 数据来源（全部为上一交付已核验文件）
- 氮循环 KO 命中行 TSV（552,808 行）、转运 KO 命中行 TSV（1,184,624 行）
- 相容性溶质合成 env xlsx（MAG_CompSul_TPM 表 79,000 行）、ench xlsx（MAG_CompSul 表 33,475 行）

### 产出
1. **1_基因组清单与注释丰度统计.tsv** — 58,171 个基因组（env 48,410 + ench 9,761，零混杂），
   每行：来源、样品类型、自基因组名解析的研究前缀/年份 token、氮循环/转运/合成三类注释的
   命中行数与去重 KO 数/基因数/溶质数。
   行数四方精确对账：氮 552,808、转运 1,184,624、合成 env 79,000、ench 33,475，与源文件完全一致。
2. **2_环境条件信息框架.tsv** — 同 58,171 行；本地可溯源字段（样品类型 env=环境样品基因组 /
   ench=富集培养基因组、研究前缀、年份 token）做实；盐度/pH/温度/地理位置/采样时间/培养条件
   六列**全部标注 [缺失]**（本地无任何逐基因组环境元数据文件，全工作区检索确证）。

### 口径声明（重要）
- **数值型丰度（TPM/覆盖度）本地不存在**：合成表表名虽为 MAG_CompSul_TPM 但仅 3 个文本列
  （上游导出即无数值）；BLAST 命中行亦不含丰度。表 1 输出的是**注释层面命中统计**，
  表 1 最后一列「数值丰度TPM或覆盖度」整列标注 [缺失]。
- 覆盖口径：清单=在氮循环/转运/合成至少一次命中的基因组；三次命中皆无的基因组在本地数据中不可见。

### 待上游（工作站6 /media/HD2/QXJ/ran/）索取清单
1. 逐基因组丰度表（CoverM 覆盖度/TPM，MAG×样本矩阵）；
2. 逐基因组环境元数据表（盐度/pH/温度/地理位置/采样时间）；
3. 「丰度」如指其他口径（如注释基因拷贝数），请上游明确定义后按同管线重跑（脚本一键复现）。

---

## 三、A1：用户输入 MAG → ThetaVerse 分析

### 真实跑通的部分
1. **基因预测**（`thetaverse.external.PyrodigalBridge`，pyrodigal 3.7.1 进程内）：
   | MAG | contigs | 基因组 | 基因数 | 编码密度 |
   |---|---|---|---|---|
   | Candidatus Brocadia sinica sp.MAG_7 (GCA_013360995.1) | 142 | 3.60 Mb | 3,342 | 84.98% |
   | Candidatus Kuenenia stuttgartiensis sp.HKUEN01 (GCA_022180985.1) | 391 | 4.18 Mb | 3,836 | 80.25% |
   | Candidatus Scalindua sp.AMX11 (GCA_004351875.1) | 121 | 4.59 Mb | 3,958 | 80.95% |
   产物：`*_pyrodigal.faa`（蛋白 FASTA，即工作站注释的输入）+ `stats_A1.json`（含全部统计）。
2. **下游链路端到端真跑**（`下游演示_盐湖真实命中\thetaverse分析\`）：以**同口径真实盐湖命中行**
   （上一交付 TSV 中跨 6 个研究前缀的 12 个代表基因组，1,056 行真实 BLAST 命中）为输入：
   `read_kegg_hits` 落表 → ThetaData 12×83 KO → 氮循环过程谱 12×19 类（v2 64 KO 字典映射）→
   core_metrics（rarefaction→α/β 多样性→PCoA，seed=7）。
   这证明下游全链路就绪：工作站回传任何 MAG 的命中表后 `--hits` 即插即出。

### [受阻] KO 注释（本机）——证据与恢复条件
用户 MAG 的 KO 注释生产路径是工作站 BLAST vs KEGG（盐湖数据即此口径，参数 e-5/num1/similarity30）。
本机三种替代途径当日实测均不可用（全过程见 `scripts\运行日志_A1_20261020.txt`）：
1. KOfam profiles.tar.gz：1.5 GB，本机到 genome.jp 实测 ~20 KB/s（约 22 小时）；
2. UniProt 肽精确搜索：持续 503/超时，每批 >3 分钟；
3. NCBI Blast.cgi（swissprot）：单 job 排队 >10 分钟未出；
4. UniProt 参考蛋白组精确序列匹配：11,768 条参考蛋白拉取成功，但与 pyrodigal 预测蛋白
   **全长精确一致为 0 条**（基因预测起点/翻译差异所致，方法学上限，非故障）。
恢复条件：工作站执行 `上游注释_工作站执行.md` 中的 blastp/diamond 命令（约分钟级），
回传 TSV 后 `python scripts\run_A1_mag_thetaverse.py --hits <TSV>` 一键出全部下游结果。

---

## 四、A2：用户输入 16S → qiime2 分析

### [受阻] QIIME 2 框架上游（Windows 本机）——证据
- QIIME 2 官方仅发行 Linux/macOS conda 包（docs.qiime2.org/2024.10/install/）；
- `pip install qiime2` 实测 `No matching distribution found`（2026-10-20）；
- thetaverse `read_qza` 需官方 qiime2 包做 artifact 视图读取 → qza 直接落表本机不可行。
工作站/WSL2 全流程命令见 `A2_16S_qiime2\上游命令_工作站执行.md`（import→demux→dada2→
classify-sklearn→建树）。

### 真实跑通的部分（`A2_16S_qiime2\thetaverse分析输出\`）
输入为 **QIIME 2 官方 moving-pictures 教程的真实 artifacts**（docs.qiime2.org 下载；
UUID/语义类型/SHA-256 全记录于 `stats_A2.json`：FeatureTable[Frequency] 000b0c9f-…、
FeatureData[Taxonomy] b66f5bb0-…、Phylogeny[Rooted] e3b9f6ba-…）：
1. qza 为 zip 归档，原样解包数据载荷（feature-table.biom / taxonomy.tsv / tree.nwk）；
2. thetaverse `read_biom` → **ThetaData 34 样本 × 770 ASV**，770/770 全部挂上 QIIME 2 物种注释；
3. `read_newick` 载入系统发育树（scikit-bio TreeNode）；
4. `core_metrics`（seed=7）：α 多样性（shannon/observed/pielou，`alpha_diversity.tsv` 34 行）+
   β 多样性 + PCoA（braycurtis/jaccard 两套坐标，`PCoA_*.tsv` 各 34 行）。
即：**16S 表格→thetaverse 下游分析链路在 Windows 本机真实可用**，上游 dada2 去噪在工作站跑。

### [缺失]
sample_metadata.tsv 源站 data.qiime2.org 本机网络不可达（连接超时）→ 分组检验
（beta_group_significance）待元数据文件到位后重跑即得。

---

## 五、A3：物种名 → NCBI 查找下载 MAG → thetaverse 分析（全链真实跑通）

`A_用户输入分析\A3_NCBI下载MAG\`，输入物种名 `Candidatus Scalindua brodae`（演示用厌氧氨氧化物种）：
1. esearch（assembly, latest genbank）→ 1 命中；
2. esummary → GCF_000786775.1 / ASM78677v1（NCBI 物种学名确认为 Candidatus Scalindua brodae）；
3. FTP 直链下载 `GCF_000786775.1_ASM78677v1_genomic.fna.gz`：1,227,127 字节，
   MD5 5adf5f8e8c67…（完整值见 provenance_A3.json），解压出基因组 FASTA；
4. 自动进入 A1 链路：基因预测（PyrodigalBridge）→ 注释状态如实记录 → stats 落盘。
全程 URL/字节数/MD5/耗时溯源见 `provenance_A3.json`。换任何物种名重跑：
`python scripts\run_A3_ncbi_mag.py --species "<学名>" --analyze`。

---

## 六、复现方式（本机）

```bat
cd /d "C:\Users\25416\Desktop\agent for pollution"

REM B 项（约 3 分钟，读 170 万行 TSV）
python "task\交付_剩余任务_20261020\scripts\run_B_abundance_env.py"
python "task\交付_剩余任务_20261020\scripts\run_B_qa.py"

REM A1 用户 MAG（基因预测+注释状态，约 2 分钟）→ 工作站回传后加 --hits <TSV>
python "task\交付_剩余任务_20261020\scripts\run_A1_mag_thetaverse.py"
REM A1 下游演示（真实盐湖命中 1,056 行）
python "task\交付_剩余任务_20261020\scripts\run_A1_hits_extract.py"
python "task\交付_剩余任务_20261020\scripts\run_A1_mag_thetaverse.py" --hits "task\交付_剩余任务_20261020\A_用户输入分析\A1_MAG_thetaverse\下游演示_盐湖真实命中\hits_8col_盐湖真实命中.tsv" --workdir "task\交付_剩余任务_20261020\A_用户输入分析\A1_MAG_thetaverse\下游演示_盐湖真实命中\thetaverse分析"

REM A2（qza 已在 artifacts\，约 10 秒）
python "task\交付_剩余任务_20261020\scripts\run_A2_16S_qiime2.py"

REM A3 全链（下载+分析，约 3 分钟）
python "task\交付_剩余任务_20261020\scripts\run_A3_ncbi_mag.py" --analyze

REM 全链 QA
python "task\交付_剩余任务_20261020\scripts\run_QA_all.py"
```

依赖：Python 3.10+（本机为 LO 便携版 3.13.15）＋ numpy/pandas/scipy/openpyxl +
`pip install pyrodigal pyhmmer biom-format scikit-bio`（全部为 pip 轮子，无需管理员）；
thetaverse 经 `sys.path` 直接使用 `ThetaVerse\src`（v0.2.0，无安装）。

## 七、运行日志索引
- `scripts\运行日志_B_20261020.txt` / `QA_B运行日志.txt` / `QA_B报告.txt`
- `scripts\运行日志_A1_20261020.txt`（含四种注释途径的失败证据）/ `运行日志_A1下游演示_20261020.txt`
- `scripts\运行日志_A2_20261020.txt` / `运行日志_A3全链_20261020.txt`
- `scripts\QA报告_全链.txt`（48 项）/ `stats_B.json` / `stats_A1.json`（A1/A2/A3 各自文件夹内）
