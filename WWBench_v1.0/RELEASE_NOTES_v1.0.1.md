# WWBench v1.0.1 发布说明(Release Candidate)

发布日期:2026-09-27 ｜ 状态:RC 冻结(A 阶段完成,待 B 阶段真实模型成绩) ｜ 许可:MIT

## 一、已闭环问题(8 条,整改前 → 整改后)

| # | 问题 | 整改前 | 整改后 |
|---|---|---|---|
| 1 | 发布包开箱即坏(P1-4) | 冒烟测试 `FileNotFoundError`,补 2 文件后才 16/16 | 根因修复(build_release.py 同步 harness/data + 自动生成 fixture),**开箱 19/19**,干净室 venv 复验通过(`logs/smoke_cleanroom_20260927.log` 末行 `19/19 smoke checks passed`) |
| 2 | evidence 维无区分度(P1-7) | 全队列恒 0.5(覆盖率×1.2 系数缺陷) | 引证锚点命中法;三档实测 **1.0 / 0.4965 / 0.0749**,冒烟含满分=2/空答=0 强制断言 |
| 3 | 复跑口径(P1-9) | 校准 2 次复跑 vs 文档宣称 5 次 | 配置改 5 并全量重跑,n_runs **2284→5710**(三档) |
| 4 | 文档口径漂移(P1-5/6) | "92 题/418 要点"、"要点 3-8"、"T1 30 题"等 7 处失实 | 全部对齐实测:**1142 题/4644 要点**,难度 637/441/64,T1 442 题;要点 1~5 条(门禁只约束生成题) |
| 5 | 客观题型校验器缺失(P0-2a) | 无 | `fdp_check`(缺陷谱逐模块比对,JSON 解析失败记 0)+ `rank_check`(NDCG@k+逐对一致率),冒烟 2 项断言锁定 |
| 6 | 基因组附件缺位(P0-2b) | capsule 无任何 .fna | 附件分发机制实证 + **3 株真实 anammox 基因组随包**(NCBI GCA 档案,12.6 MB) |
| 7 | 引文截断(P1-8) | 无修复管线,残句入 capsule | `repair_references.py`(Crossref 回填);52 题金标准试点 **36 条 DOI 回填 35 条**,12 capsule 重写,报告 CSV 落盘 |
| 8 | 空评分表崩溃(NEW-2) | 全部作答出错时 `KeyError: 'overall'` | 两层守卫,优雅落盘诊断报告;占位 Key 实跑验证退出码 0 |

连带效应:oracle 档综合均分 **0.9423 → 0.9840**(dim_norm 0.9005 → 0.9838),六维再无失真项;degraded 0.5251→0.5312、mock 0.0534→0.0596(重跑实测)。

## 二、整改中新发现并修复的 bug(2 个)

1. **rank_check IDCG 漏乘排位增益**:完美排序 NDCG 返回 0.6955 而非 1.0;修正公式后冒烟断言锁定(现返回 1.0)。
2. **报告层空结果 KeyError**(见上表 #8):由 P0-1 链路边界测试发现。

## 三、诚实挂起项(4 条,阻塞原因与解锁动作)

| 挂起项 | 阻塞原因 | 解锁动作 |
|---|---|---|
| P0-1 真实模型成绩单 | 缺合法 API Key(链路已验证至 GLM 端点 401 边界,零代码障碍) | 用户提供 `$WWBENCH_API_KEY` 后执行 `python scripts/run_real_smoke.py`(5 题)→ 通过后 `python scripts/run_real_full.py`(52 题×5 复跑) |
| P0-3 文献知识库(2790 篇 0 落地) | 出版商 SSO 机构登录未完成;全队列经 Unpaywall 证实 0% OA,无权限合法下载量为 0 | 用户在下载专用 Chrome 完成一次机构登录 → 金标准 DOI 验证 → `start_full_run.cmd` 无人值守 |
| 基因组注释工具链(T1 金标准缺陷谱) | 本机无 Prodigal/BLAST/diamond 环境;40 个 P1~P8 占位档案与真实 NCBI 基因组映射未建立 | 部署 ThetaVerse `[pyeco]` 环境跑注释生成金标准;映射建立前不宣称 T1 已做基因组实证考核 |
| CITATION 作者占位 | 真实作者名单需项目组确认,不代填 | 项目组提供名单后更新 CITATION.cff |

v2.0 题型扩展(A/B/C/D/E 五站、回顾性预测题、五级消融阶梯)按《WWBench_v1.1_整改台账与验收报告》§五排期执行,不属于本版范围。

## 四、冻结声明(A4)

自本文件落盘起,v1.0.1 的评分器/题库/校准配置**冻结**;B/C 阶段只允许新增 `results/real_*/` 与 `outputs/` 运行痕迹。若 B 阶段暴露 P0 级新 bug:回滚到本 RC 产物 → 修复 → 重走 A1 冒烟 → 重新冻结,禁止在跑数过程中热改。

## 五、最小验证入口

```bash
cd WWBench_v1.0/harness
python tests/test_smoke.py        # 期望末行: 19/19 smoke checks passed
python scripts/refresh_manifest.py
python scripts/repair_references.py --dry-run --qids q-061   # 需外网
```
