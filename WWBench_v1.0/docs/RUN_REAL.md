# 真实模型首跑操作手册(B 阶段,拿到 API Key 后执行)

> 密钥只经环境变量注入,不写入任何文件/日志/配置;两把 Key 建议不同厂商(judge 与 solver 异源,防自评偏置)。

## 0) 准备(一次性)

```bash
cd WWBench_v1.0/harness
python tests/test_smoke.py        # 确认末行 19/19 smoke checks passed
```

## 1) B1 五题冒烟(全部闸门自动判定,退出码 0=通过)

```bash
# Windows cmd
set WWBENCH_API_KEY=你的GLM/DeepSeek/Qwen密钥
set WWBENCH_JUDGE_KEY=你的OpenAI密钥
python scripts/run_real_smoke.py
```

| 环境变量 | 缺省 | 说明 |
|---|---|---|
| `WWBENCH_API_KEY` | 必填 | solver 用的 OpenAI 兼容密钥 |
| `WWBENCH_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | solver 端点 |
| `WWBENCH_MODEL` | `glm-4.7` | solver 模型名 |
| `WWBENCH_JUDGE_KEY` | (缺省用 heuristic judge,显式警告) | judge 密钥 |
| `WWBENCH_JUDGE_BASE_URL` / `WWBENCH_JUDGE_MODEL` | OpenAI 官方 / `gpt-4o` | judge 端点与模型 |

五闸门:(a) 无 401/限流/未捕获异常;(b) grades.csv 列集与 oracle 档同构;
(c) 空结果守卫未触发;(d) 六维 ∈[0,2] 且 evidence 非退化常量(若全为 1.0 立即停);
(e) fdp/rank 校验器调用无异常。**任一 FAIL 不得进入 B2。**

题号说明:任务书要求的 q-001~q-005 不存在(题号自 q-061 起),实际取文件顺序
前 5 题(q-061, q-104, q-105, q-113, q-118),已在脚本头部如实声明。

## 2) B2 金标准全量(52 题 × 5 复跑 = 260 solver + 260 judge 调用)

```bash
python scripts/run_real_full.py                      # 全量;断点续跑可中断重执行
python scripts/run_real_full.py --limit 10           # (可选)先 10 题再放全量
```

产出 `outputs/real_<model>_<日期>/`:`grades.csv`、`responses.csv`、
`per_question_aggregate.csv`(每题均分/跨复跑标准差)、`summary_real.json`
(两层聚合六维)、`evidence_hist.png`、`calibration_gate.json`。

**B3 熔断闸门(脚本自动执行)**:
- overall > 0.9840(oracle)→ `STOP_ABOVE_ORACLE`,先查训练泄漏,不许发版;
- overall < 0.4965(degraded)→ `STOP_BELOW_DEGRADED`,抽样 5 题人工读作答;
- 区间内 → `PASS_TO_PHASE_C`,退出码 0。

## 3) C1 对比与置信区间(自动化)

```bash
python scripts/bootstrap_ci.py --real outputs/real_<model>_<日期>/per_question_aggregate.csv --baseline ../results/oracle_degraded50/question_level.csv --out outputs/real_<model>_<日期>/bootstrap_delta_vs_degraded.json
python scripts/compare_runs.py    # real 档自动进入排行榜(基于 outputs/ 目录)
```

## 4) C2 决策

把 `calibration_gate.json` 的 verdict 交给发布工程师,按 RELEASE_NOTES §四冻结
规则产出 `docs/RELEASE_DECISION_v1.0.1.md`(发版 / 不发版二选一,禁止中间态)。

## 预算提示

B2 全量 ≈ 260 次 solver 调用(每题题面约 300~500 token ×5 复跑)+ 260 次 judge
调用(题面+要点+作答,单次约 1.5~2.5K token)。GLM-4.7 与 GPT-4o 各约
0.5~1M token 量级;先跑 `--limit 10` 核算单价再放全量。
