# 文献 PDF 批量下载任务 —— 移交执行书（执行模型：Hy4 preview）

> 本文件是把 `literature_downloader` 工具包的下载任务完整移交给你（WorkBuddy 智能体，
> 使用 Hy4 preview 模型）的执行依据。所有下载清单、规则、参数以
> `literature_downloader/lists/` 下 Excel 为准，本文件是解析结果 + 硬性规则。

## 1. 任务目标

按 Excel 清单顺序，把 **2790 篇剩余文献** 的 DOI 逐条打开出版社页面，下载合法授权的
PDF 落盘；全程写日志，失败条目如实记录，不得静默跳过。

## 2. 数据源（已解析，以此为准）

| 文件 | 内容 | 条数 |
|---|---|---|
| `lists/剩余待下载_汇总.xlsx` | 剩余待下载总清单（本次执行的唯一清单） | 2790 |
| `lists/待下载_第1份.xlsx` / `第2份` / `第3份` | 三人分片（各 930，合计 2790） | 2790 |
| `lists/文献下载总览.xlsx` | 全量总览 3834 篇：已下载 1044、未下载 2744、失败 46 | 参考 |
| `lists/待下载文献清单_源.xlsx` | 源清单（DOI/标题/期刊/出版商/摘要） | 3721 |
| `remaining_workbuddy.csv` | **本次待下队列**（从剩余汇总严格重建，顺序一致） | 2790 |

队列状态构成：未下载 2744、失败-无PDF 25、失败-无权限 14、失败-其他 7。

## 3. 执行环境与脚本（真实浏览器，禁止伪造）

工具包脚本（与本任务书同目录树的 `literature_downloader/`）：

1. `make_queue.py`：xlsx → remaining.csv（已代做，直接用 `remaining_workbuddy.csv`）
2. `chrome_serve.py`：启动**已登录机构订阅的真实 Chrome**（CDP 9222，常驻后台）
3. `downloader_v4.py`：连接 CDP，逐条按 DOI 下载（断点续跑、失败熔断）
   ```bash
   python downloader_v4.py --queue remaining_workbuddy.csv --limit 9999 --pause-min 5 --pause-max 10
   ```
4. `supervisor.py`：看门狗（保活、分块、冷却、补跑 3 轮），可替代 3 长跑

路径经环境变量配置（模板见 `config.example.env`），**不得写死个人路径**：
`LIT_ROOT / LIT_OUT / LIT_DIR / LIT_LOG / CHROME_BIN / CHROME_PROFILE / CDP_PORT / QUEUE_PATH / WORKSPACE / PY_BIN`。

## 4. 硬性规则（来自 PROMPT.md，逐条遵守）

1. 只下载清单内文献，只下有合法权限的内容。
2. **禁止**盗版站点、Sci-Hub、破解来源；禁止绕过登录/付费墙/DRM/IP 限制；不自动输密码。
3. 必须用真实 Chrome + CDP（`chrome_serve.py`）；**不要用 Selenium/Playwright 伪造浏览器**，
   不要用 Playwright persistent context。
4. 单线程，每篇间隔 5–10 秒，不并发。
5. 不改浏览器指纹、不伪装 UA、不用代理池、不打码。
6. 不可点击：购买、订阅、免费试用、加信用卡、分享、关注、广告下载。
7. 可点击：Accept cookies / 关广告 / PDF / Download PDF / Full Text / View PDF。
8. 断点续跑：开跑先扫磁盘已有 PDF（文件名规则：DOI 中 `/`→`_`、全小写、加 `.pdf`），
   已存在写 `skipped_exists` 跳过。
9. 日志 `LIT_LOG` **追加写，不覆盖**，字段：
   `序号, DOI, 标题, 出版商, 状态, 文件名, 错误原因, 时间, 备注`。

## 5. 状态定义与失败处理

| 状态 | 含义 | 处理 |
|---|---|---|
| `downloaded` | 已下到 LIT_OUT | 继续 |
| `skipped_exists` | 磁盘已有 | 跳过 |
| `blocked` | 无 PDF 入口/无权限 | **永久失败**，记日志继续，不熔断 |
| `failed_no_pdf` | 有入口下不来 = 疑似限流 | **触发熔断**，停车冷却 |
| `failed_other` | 其他异常 | 记日志继续 |

- 单篇失败：记录原因+截图，继续下一篇，不卡住。
- 连续失败：跳过并记录，最后汇总。
- 仅浏览器崩溃、下载目录不可写、Excel/队列无法读取时，**立刻停止并报错，不静默跳过**。
- 收尾：重跑盘点（`make_queue.py --rescan`），输出总览对比（已下载上升/剩余下降）。

## 6. 顺序与完整性要求

- **严格按 `remaining_workbuddy.csv` 行序执行**（与 `剩余待下载_汇总.xlsx` 序号一致），
  不删减、不重排、不改写任何条目。
- 执行结束必须输出：成功 N / 跳过 N / 失败 N（含逐条失败清单）。
