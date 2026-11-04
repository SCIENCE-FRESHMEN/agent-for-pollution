# 文献 PDF 自动下载（Computer Use / 真实浏览器）— 可移植执行 Prompt

> 本 prompt 配合 `literature_downloader/` 工具包使用。**所有路径都通过环境变量配置（见 `config.example.env`），不要写死任何人的本地路径**；换机器只改 `config.example.env` 并注入变量即可，不用改代码、不用改本 prompt。
>
> 你（执行体）具备 Computer Use 能力：可以截图、移动鼠标、点击、输入、滚动、切换标签、读文件、扫目录、写日志。全部自动完成，不要让人手点。

---

## 0. 开跑前先配置（每台机器必做）

把包里的 `config.example.env` 复制成 `.env`，按**本机**改好以下变量（示例值是某台机器的，仅作格式参考）：

```
LIT_ROOT            = 文献项目根目录（里面要有 literature/ 与 logs/）
LIT_OUT            = PDF 落盘目录（例如 literature/authorized_pdf_v2）
LIT_DIR            = literature 目录（断点续跑扫描已存在 PDF 用）
LIT_LOG            = 下载日志 CSV 路径
CHROME_BIN         = Chrome 可执行文件完整路径
CHROME_PROFILE     = 已登录机构订阅的 Chrome profile 目录（复用这个会话）
CDP_PORT / CDP_HTTP= 9222 / http://127.0.0.1:9222
HEN_XLSX           = 你的文献清单 xlsx 路径（含 DOI 列）
OUTDIR             = 汇总/拆分产物目录
QUEUE_PATH         = remaining.csv 路径（下载器读取的待下队列）
WORKSPACE          = 本工具包目录（supervisor 找 downloader_v4.py 用）
PY_BIN             = python 解释器路径
```

运行任何脚本前，先 `set`（Windows cmd）或 `export`（bash）注入这些变量。

---

## 1. 输入与规则

- **文献清单**：用户指定的 xlsx（工作表含 `DOI` 列；`标题`、`出版商` 列用于日志与分组）。直接读 DOI 列。
- **下载目录**：`LIT_OUT`。
- **文件名规则**：DOI 里的 `/` 换成 `_`，全小写，加 `.pdf`。
  例：`10.1016/j.biortech.2012.02.122` → `10.1016_j.biortech.2012.02.122.pdf`
- **日志**：`LIT_LOG`，**追加写入，不要覆盖**。建议字段：
  `序号, DOI, 标题, 出版商, 状态, 文件名, 错误原因, 时间, 备注`
- **浏览器**：复用 `CHROME_PROFILE` 这个**已登录机构权限**的真实 Chrome 会话；不碰登录流程、不自动输入密码。

---

## 2. 必须遵守（硬性）

1. 只处理用户明确列出的文献，只下载有合法权限的内容。
2. 不使用盗版站点、Sci-Hub、非官方破解来源。
3. 不绕过登录、付费墙、DRM、IP 限制；不自动输入密码；不破解。
4. 控制**真实浏览器**：截图、移动鼠标、点击、输入、滚动、切换标签。不要用 Selenium/Playwright 去伪造浏览器；**不要使用 Playwright persistent context**（那会让你无法下载 PDF）。本包 `chrome_serve.py` 启动的是系统真实 Chrome + CDP，下载器通过 CDP 连接它——这是真实会话，不是伪造浏览器。
5. 单线程，每篇间隔 5–10 秒，不并发、不批量狂点。
6. 不修改浏览器指纹、不伪装 User-Agent、不使用代理池、不打码。
7. 不点击：购买、订阅、免费试用、添加信用卡、分享、关注、广告下载。
8. 可以点击：Accept cookies / 同意隐私政策 / 关闭广告 / PDF / Download PDF / Full Text / View PDF。

---

## 3. 断点续跑（开跑第一步）

- 开跑前先扫描 `LIT_DIR`（含 `LIT_OUT`）下已有的 PDF，按上面文件名规则匹配 DOI。
- 已存在的 DOI 直接跳过，并在日志写 `skipped_exists`，不重复下载。
- 若用户清单里有一部分已在磁盘（例如"已有 113 篇"），按文件名规则匹配后同样跳过。

---

## 4. 每篇操作流程（Computer Use 控制真实浏览器）

1. 从 Excel 读下一条 DOI（序号递增）。
2. 先检查目标文件名是否已存在；存在 → 写 `skipped_exists`，处理下一条。
3. 打开 DOI 链接：`https://doi.org/<DOI>`。
4. 等待页面加载。
5. 若出现 cookie 横幅 → 点击接受/关闭（参考第 8 条允许项）。
6. 寻找 `PDF` / `Download PDF` / `Full Text` / `View PDF` 等按钮或链接。
7. 点击并等待下载完成。
8. 若 PDF 在新标签打开 → 切到新标签，用浏览器下载按钮保存。
9. 下载到 `LIT_OUT`。
10. 按规则重命名：`/`→`_`，全小写，加 `.pdf`。
11. 写日志：序号、DOI、标题、出版商、状态、文件名、错误原因、时间、备注。
12. 处理下一篇，间隔 5–10 秒。
13. 无法自动完成时的处理：若页面需要额外交互（表单、确认框、订阅页、登录页、付费页、访问限制页等），尝试完成这些交互（填表单、点确认、刷新重试）；确实拿不到 PDF 就标记 `blocked` 跳过，最后汇总。

---

## 5. 用工具包脚本（推荐：可靠且同样控制真实浏览器）

纯手点 3000+ 篇既慢又易错，优先用包里脚本——它们做的正是第 4 节那套流程，只是用 CDP 驱动**真实已登录 Chrome**（非 Playwright persistent context，能下 PDF，满足第 4 条）：

```bash
# a) 生成待下队列（从用户给的清单 xlsx 提取 DOI/标题，--rescan 会重扫磁盘剔除已下）
python make_queue.py --input "<用户的清单.xlsx>" --output remaining.csv --rescan

# b) 起真实 Chrome（另一终端常驻；复用 CHROME_PROFILE，开 CDP 9222）
python chrome_serve.py

# c) 下载（单线程、5–10s 间隔、断点续跑、失败熔断）
python downloader_v4.py --queue remaining.csv --limit 9999 --pause-min 5 --pause-max 10
```

- 下载器逐篇打开 DOI、找 PDF 入口、触发下载、按规则重命名、追加日志、跳过已存在；`blocked`=无权限（永久失败，跳过）、`failed_no_pdf`=有入口却下不来（疑似被限流，会熔断停车冷却）。
- 若执行体是纯 Computer Use 智能体，也可完全按第 4 节用截图/鼠标一步步操作真实浏览器，逻辑相同；脚本只是更稳更快的参考实现（原 `authorized_browser_download_v2.py` 的整理版即包内 `downloader_v4.py`）。
- 想单机一口气跑完+被封自动冷却+失败自动补跑：用 `python supervisor.py`（同样依赖已起的真实 Chrome）。

---

## 6. 状态 / 失败 / 收尾

- 状态建议：`downloaded` / `skipped_exists` / `blocked` / `failed_no_pdf` / `failed_other`。
- 某篇找不到 PDF 或下载失败：记录原因、截图、继续下一篇，**不要卡住**。
- 连续多篇失败：不停等，继续跳过并记录，最后统一汇总。
- 仅当浏览器崩溃、下载目录不可写、Excel 无法读取时才暂停并告知用户。
- 收尾：重跑 `split_three_v3.py`（或 `make_queue.py --rescan`）盘点，确认"已下载"上升、"剩余"下降，输出总览。
