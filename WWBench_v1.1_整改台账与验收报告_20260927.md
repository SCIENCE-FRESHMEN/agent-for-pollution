# WWBench v1.0 → v1.0.1 整改台账与验收报告

| 项 | 内容 |
|---|---|
| 文档编号 | WWB-REM-20260927-01（配套《Bench测评复盘报告_WWBench_v1.0_20260927.md》） |
| 整改范围 | 测评报告 §6 全部 14 条问题的分类整改 + 整改中新发现缺陷的闭环 |
| 版本产物 | WWBench v1.0.1（CITATION.cff 已升版，date-released 2026-09-27） |
| 核验方式 | 每条整改附最小复现步骤与验收数据；终态以 19/19 冒烟日志 + 重跑校准 summary.json + MANIFEST 1299 条哈希为准 |

---

## 一、整改总览（按问题四分类）

| 分类 | 编号 | 状态 |
|---|---|---|
| 打包发布问题 | P1-4 | ✅ 已闭环（根因修复 + 全量复验） |
| 文档口径问题 | P1-5 / P1-6 / P1-9 | ✅ 已闭环（三份文档 + 三份配置全量对齐实测） |
| 代码逻辑问题 | P1-7 evidence 维 | ✅ 已闭环（根因修复，全量 5710×3 重跑验证） |
| 代码逻辑问题（新发现） | NEW-1 rank_check IDCG 公式缺陷、NEW-2 空评分表报告崩溃 | ✅ 发现即修复，测试锁定 |
| 内容资源缺失问题 | P0-1 真实模型成绩 | 🟡 链路 100% 就绪，唯一剩余=合法 API Key（外部依赖） |
| 内容资源缺失问题 | P0-2 能力错位 | 🟡 校验器与附件机制已落地；金标准 FDP 数据与 P1~P8 映射归入 v2.0 |
| 内容资源缺失问题 | P0-3 文献库、P2-11 悬空引用 | ⏳ 外部依赖（SSO / 项目组归档），本阶段无变化 |
| 设计取舍（维持声明） | P2-12 题域偏科、P2-13 独立口径进 results、P2-10 作者占位、P2-14 工作区卫生 | 📋 v1.1/v2.0 排期（见 §五） |

---

## 二、逐条整改明细（问题 → 根因 → 动作 → 验收数据）

### P1-4 发布包开箱即坏 【打包发布】【已闭环】

- **根因**：`build_release.py` 从开发布局打包时把题库复制到顶层 `dataset/`，但 harness 冒烟测试与 runner 按 `harness/data/` 寻址；`pending_review.csv` fixture 未随包。
- **动作**：`build()` 新增 harness/data 同步块（题库 + 由题库首行自动生成的审批门禁 fixture + attachments 目录整体打包）；修正版随 CITATION 1.0.1 发布。
- **验收**：`cd harness && python tests/test_smoke.py` → **19/19 通过**（含新增 3 项），日志落盘 `harness/outputs/logs_v1.1/smoke_final_19of19.log`；重建 zip：`python scripts/build_release.py --out <路径>.zip`（打包即自含，清单自动再生）。

### P1-5 文档版本漂移 【文档口径】【已闭环】

- **动作**：harness/README.md 全量修正——"92 题/418 要点"→"1142 题/4644 要点"（实测）；难度"63/25/4"→"637/441/64"；"全量 92 题"→"全量 1142 题"；"T1 的 30 题…15 基因组档案"→"442 题…8 基因组档案"；`PPT_THEME_ALIGNMENT_AUDIT.md` 引用改为"暂未随包归档，v1.1 收口补充"。
- **验收**：README 数字与 `summary.json.dataset_stats` 逐项一致（冒烟测试输出即为交叉证据）。

### P1-6 要点数口径不符 【文档口径】【已闭环】

- **动作**：`dataset/provenance.md` 与 build 模板同步改为："生成门禁约束 L1~L3 生成题；L0 专家原题不经过该门禁，实测要点 1~5 条/题（均值 4.07，总计 4644）"——解释了矛盾来源而非掩盖。
- **验收**：provenance.md 新表述 ↔ 逐行统计（min=1/max=5/mean=4.07）完全一致。

### P1-9 复跑口径不一致 【文档口径】【已闭环，数据同步升级】

- **动作**：不止改文档——把三档校准配置 `replicates: 2 → 5`，**全量重跑**，使随包基线数据本身满足 README"5 次复跑"口径。
- **验收**：`outputs/{oracle_calibration,oracle_degraded50,mock_smoke}/summary.json` 的 `n_runs` 均为 **5710**（=1142×5）；对比表由 `compare_runs.py` 再生。

### P1-7 evidence 维系统性失效 【代码逻辑】【已闭环】

- **根因**：`HeuristicGrader` 用覆盖率×系数映射六维，evidence 系数 1.2：oracle 覆盖率 0.9842×1.2=1.18→四舍五入恒为 1 分→归一化恒 0.5。非"闭卷无依据"的语义问题，是映射系数缺陷。
- **动作**：重写 `_evidence_dim`——以参考答案中的引证锚点（DOI / 期刊+年份如 "ES&T 2022" / et al. / 书名号）为集合，按作答命中比例打分（≥0.6→2 分，≥0.25→1 分，否则 0）；参考答案无锚点时退化为与准确性同权的覆盖率映射（2.0），不再产生常数。
- **验收（全量 5710×3 重跑前后对比）**：

| evidence 维归一分 | v1.0 | v1.0.1 | 判定 |
|---|---|---|---|
| oracle_calibration | 0.5（恒定） | **1.0** | 满分档恢复满分 |
| oracle_degraded50 | 0.4229 | **0.4965** | 与 accuracy（0.4956）同水平，语义合理 |
| mock_smoke | 0.0 | **0.0749** | 与其他维同量级 |
| 冒烟断言 | 无 | 满分=2 / 空答=0 强制断言 | 回归锁定 |

- **连带效应**：oracle 综合均分 0.9423 → **0.9840**（dim_norm 0.9005→0.9838），六维不再有失真项。

### NEW-1 rank_check IDCG 公式缺陷 【代码逻辑】【已闭环】

- **现象**：完美排序的 NDCG 返回 0.6955 而非 1.0。
- **根因**：IDCG 计算漏乘排位增益因子 `1/(i+1)`。
- **动作**：修正公式；冒烟测试断言完美排序 NDCG=1.0。
- **验收**：`[ok] fdp/rank 客观校验`（冒烟第 14 项）。

### NEW-2 空评分表报告崩溃 【代码逻辑】【已闭环】

- **现象**：全部作答出错时（如 API key 失效），`write_report` 与 `run_bench.py` 直接 `KeyError: 'overall'` 崩溃——真实模型小批量试跑极易踩中。
- **动作**：两层守卫（report.py 早返回最小报告 + summary.json 写入诊断 note；run_bench.py 汇总打印判空），主链路退出码 0。
- **验收**：占位 Key 实跑 1 题 → `[report](空结果守卫:无有效评分行)`，全程无 traceback（日志 `p0_1_chain_boundary_test.log`）。

### P0-1 真实模型成绩体系 【内容资源】【链路就绪，待密钥】

- **已交付**：
  1. 空结果崩溃缺陷修复（NEW-2）；
  2. **全链路边界实测**：`GLM_API_KEY=<占位>` 下实跑 `run_openai.yaml --limit 1 --replicates 1`——配置加载 ✓ → 题库加载 ✓ → Provider 构建 ✓ → HTTP 到 bigmodel 端点 ✓ → 重试 3 次（按配置）✓ → 401 错误（"令牌已过期或验证不正确"）落盘 responses.csv ✓ → 优雅退出 ✓。**整条链路只差一把合法密钥**。
- **Runbook（密钥就绪后逐条执行）**：
  ```bash
  cd WWBench_v1.0/harness
  # ① 小批量试跑（GLM 为 solver，GPT-4o 为 judge——异厂商防自评偏置）
  export GLM_API_KEY=sk-真实key
  python scripts/run_bench.py --config configs/run_openai.yaml --limit 5
  # ② 52 题金标准全量（filters.tag 留空、--limit 不加即为全量；断点续跑可中断重续）
  python scripts/run_bench.py --config configs/run_openai.yaml
  # ③ 换模型重复（改 yaml 的 model/base_url/api_key_env 三行即可）
  # ④ 排行榜
  python scripts/compare_runs.py
  ```
- **验收标准**：`outputs/` 出现非 oracle/mock 的 run；`comparison_report.md` 出现真实模型行；judge 与 solver 分属不同厂商；每 run 附 `judge_audit/`。

### P0-2 Bench 与系统能力错位 【内容资源】【阶段闭环，数据入 v2.0】

- **已交付（代码与机制层）**：
  1. `graders.fdp_check`：基因组功能缺陷谱客观校验（present/partial/missing 逐模块比对，JSON 解析失败记 0 分不静默给分）——支持中英文状态词；
  2. `graders.rank_check`：供体菌排序校验（NDCG@k + 逐对一致率 + hit@1）；
  3. 附件分发机制实证：`data/attachments/_shared/**` 与 `<qid>/**` 均进入每题工作区（冒烟第 15 项断言）；
  4. **3 株真实厌氧氨氧化菌基因组随包发布**（`harness/data/attachments/_shared/genomes/`，来自 NCBI GCA 公开档案：Brocadia sinica MAG_7 / Kuenenia stuttgartiensis HKUEN01 / Scalindua sp.AMX11）。
- **v2.0 待办（诚实边界，不虚报完成）**：40 个 T1 占位档案（P1~P8）与真实 NCBI 基因组的映射、金标准缺陷谱的生产（需在装有钱 Prodigal/annotation 管线或 ThetaVerse transport 库的机器上跑注释）、A/B/D 新题型的题面与入库（走 `generate_questions.py` 待审流程）、LV-Sim 题型（依赖系统侧模拟模块落地）。

### P1-8 引文截断 【内容资源】【试点闭环，全量入 v2.0】

- **动作**：新增 `scripts/repair_references.py`（Crossref 公开元数据回填 DOI 条目完整标题，带缓存/礼貌限速/dry-run/修复报告 CSV）。
- **验收（52 题金标准试点）**：DOI 条目 36 条中 **35 条成功回填**（1 条网络失败可重跑），12 个 capsule 重写；q-061 实测回填后标题完整（如 "Glutamate Enhances Osmoadaptation of Anammox Bacteria under High Salinity: Genomic Analysis and Experimental Evidence"）。非 DOI 内部编号条目（L0xxx）标记 `[待补全:非DOI条目]` 保持原样。
- **产物**：`outputs/reference_repair_report.csv`（52 行逐题台账）、`outputs/crossref_title_cache.json`。
- **已知瑕疵（如实披露）**：Crossref 偶尔返回含 XML 标记的标题（如 `<i>Brocadia</i>`），v1.1 批量跑时在脚本中加一步去标记即可。

### P2 项处置

- **P2-10**：CITATION 升至 1.0.1 并加 notes；真实作者名单需项目组提供，不代填；
- **P2-12**：维持"子基准"声明（harness README 范围声明保留）；
- **P2-13**：`audit_dataset.py` 已有，独立题面口径字段进 results 归入 v2.0 报告层；
- **P2-14**：`dir/`、`mkdir/` 空文件夹与 `.env` 属工作区资产，建议项目组自行清理与脱敏（未授权不代删）。

---

## 三、v1.0 → v1.0.1 前后对比总表

| 指标 | v1.0（测评时） | v1.0.1（整改后） |
|---|---|---|
| 冒烟测试 | 开箱失败→补 2 文件后 16/16 | **开箱 19/19**（新增 fdp/rank、附件分发、evidence 区分度 3 项断言） |
| oracle_calibration | mean 0.9423，dim_norm 0.9005，evidence 0.5，n_runs 2284 | **mean 0.9840，dim_norm 0.9838，evidence 1.0，n_runs 5710** |
| oracle_degraded50 | mean 0.5251，accuracy 0.0342 | mean 0.5312，accuracy 0.0350 |
| mock_smoke | mean 0.0534 | mean 0.0596 |
| evidence 维区分度 | 全队列恒 0.5 | 三档 1.0 / 0.4965 / 0.0749 |
| 复跑口径 | 校准 2 次 vs 文档"5 次" | **数据与文档统一为 5 次** |
| 发布包 harness/data | 缺失（开箱即坏） | 题库+fixture+附件随包 |
| .fna 附件 | 0 | 3 株真实基因组（12.6 MB） |
| 引文回填 | 无管线 | 脚本 + 金标准试点 35/36 |
| 客观题型校验器 | 无 | fdp_check + rank_check（带回归测试） |
| 空结果健壮性 | KeyError 崩溃 | 优雅守卫（实测验证） |
| MANIFEST | 1228 条（与产物脱节） | **1299 条**（含全部整改产物，就地重算） |
| CITATION | v1.0.0 / 2026-09-24 | v1.0.1 / 2026-09-27 + notes |

**复验入口（任何人任何机器）**：
```bash
cd WWBench_v1.0/harness
python tests/test_smoke.py                                  # 期望: 全部冒烟测试通过 ✔（19 项 [ok]）
python scripts/refresh_manifest.py                           # 期望: 1299 条且抽查一致
python scripts/repair_references.py --dry-run --qids q-061   # 期望: doi=3 fixed=3（需外网）
```

---

## 四、遗留风险与依赖（诚实声明）

1. **P0-1 唯一剩余依赖 = 合法 API Key**（GLM 用于 solver、OpenAI 用于 judge）。链路已验证到 401 边界，密钥注入后预计 1 小时内可出 52 题首跑成绩（5 复跑 × 52 题 ≈ 260 次 solver + 260 次 judge 调用）。
2. **P0-3 文献库**：仍卡出版商 SSO 机构登录（用户操作，约 2 分钟），就绪后 `start_full_run.cmd` 无人值守；开卷消融与回顾性预测题依赖此项。
3. **P0-2 金标准数据**：缺陷谱金标准需注释工具链（本机无 Prodigal/BLAST 环境），建议装好 ThetaVerse `[pyeco]` 环境后一键生成；在此之前不得宣称 T1 题已做基因组实证考核（README 已如实声明）。
4. **哈希口径说明**：当前 MANIFEST 覆盖工作目录全部产物（含 harness/outputs 运行痕迹）；正式分发 zip 由 `build_release.py` 从 staging 重新生成清单（不含 outputs/），两者口径不同属预期。

## 五、版本排期与量化验收（v1.1 → v2.0）

| 里程碑 | 时限 | 量化验收标准 |
|---|---|---|
| **v1.1 收口发布版** | 1~2 周 | ① 真实模型 ≥3 个（国际/国产/开源各≥1）完成 52 题金标准 5 复跑，comparison_report 含真实行；② judge-solver 异厂商 + judge_audit kappa 报告产出；③ `build_release.py` 一键产出 zip，解压冒烟 19/19；④ 文献库下载量 >0 并启动开卷消融（`context_mode: with_refs`）；⑤ P2-11 两份悬空文档归档 |
| **v2.0 能力完整版** | 1~2 月 | ① 五站题型入库：A 缺陷谱（客观判分 ≥40 题，fdp_check）、B 溶质映射、C 工程计算、D 供体排序（rank_check）、E 全场景报告；② P1~P8×5 属基因组映射建立，金标准缺陷谱覆盖 40 档案；③ 回顾性预测题 30~50 道（真实文献结局判卷）；④ 五级消融阶梯（裸 LLM→+RAG→+工具→+ThetaVerse→完整系统）出对比图；⑤ 全量 1142 capsule 引文修复 + 独立题面口径进 results；⑥ 诚实性指标（拒答奖励/幻觉扣分）上线 |
