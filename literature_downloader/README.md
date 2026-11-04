# 文献 PDF 自动下载工具包（literature_downloader）

把"非 OA 文献核验清单"里的 DOI 自动下成 PDF 的一套脚本。核心思路：
用**已登录机构订阅的真实 Chrome**（通过 CDP 远程控制）访问出版社页面，
按 DOI 抓取 PDF 落到本地；断点续跑、失败熔断、看门狗自动保活与补跑。

---

## 1. 文件清单与职责

| 文件 | 作用 |
|---|---|
| `split_three_v3.py` | **汇总+拆分**：扫描磁盘真实 PDF（含 PII 命名文件的内部 DOI 反查），对照核验清单，产出 `文献下载总览.xlsx` / `剩余待下载_汇总.xlsx` / `待下载_第1~3份.xlsx` |
| `make_queue.py` | **桥接**：把某个拆分 xlsx 转成下载器要的 `remaining.csv`（列：DOI,Title,Publisher） |
| `chrome_serve.py` | **启动器**：拉起真实 Chrome（指定已登录 profile + 开放 CDP 9222 端口），常驻后台 |
| `downloader_v4.py` | **下载器**：连接 CDP，逐条按 DOI 打开出版社页面、找 PDF 入口、触发下载、写日志；断点续跑、失败熔断 |
| `supervisor.py` | **看门狗（全自动）**：保活 Chrome、分块调用下载器、被封自动冷却降速、主队列跑完后自动补跑失败项最多 3 轮 |
| `requirements.txt` | Python 依赖 |
| `config.example.env` | 所有路径/端口的环境变量模板 |

> 说明：`split_three_v3.py` 只做"盘点+拆分"，**不下载**；下载由 `downloader_v4.py`/`supervisor.py` 完成。

---

## 2. 前置条件（每台机器都要有）

1. **Python 3.10+**，并安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. **已安装 Google Chrome**（系统版，不是 Playwright 自带 chromium）。
3. **已登录机构订阅的 Chrome profile**（即 `CHROME_PROFILE` 指向的目录），
   里面 Chrome 已登录学校/机构的图书馆代理，能正常打开 ScienceDirect / Springer /
   Wiley / ACS 的全文。没有这个，绝大多数 PDF 会判定为"无权限(blocked)"。
4. 把核验清单 xlsx 放到已知路径（`HEN_XLSX`）。

---

## 3. 路径配置（换机器只需改环境变量）

所有脚本路径都读环境变量，缺省为本机默认值。把 `config.example.env`
复制成 `.env` 改好，运行前注入即可，**不用改代码**：

```bash
# Windows cmd
set LIT_ROOT=D:\YourProject
set CHROME_PROFILE=D:\YourProject\browser_profile_authorized
set HEN_XLSX=D:\path\to\non_oa_literature_links_核验.xlsx
# 然后运行脚本...

# bash
export LIT_ROOT=/data/YourProject
export CHROME_PROFILE=/data/YourProject/browser_profile_authorized
export HEN_XLSX=/data/path/to/non_oa_literature_links_核验.xlsx
```

---

## 4. 用法 A：手动分人下载（推荐给"三人分三份"场景）

适合把 3 份表分别交给 3 个人/3 台机器各下各的。

**(a) 先盘点+拆分一次（只需一个人做）：**
```bash
python split_three_v3.py
```
得到 `output/` 下：总览、剩余汇总、第1~3份 xlsx。

**(b) 每个人对自己那份表生成队列并下载：**
```bash
# 第1个人
python make_queue.py --input 待下载_第1份.xlsx --output remaining_1.csv
python chrome_serve.py                      # 先开 Chrome（另一个终端常驻）
python downloader_v4.py --queue remaining_1.csv --limit 9999 --tag p1 --pause-min 30 --pause-max 45
```
第2、3人同理换成 `第2份`/`第3份`、`remaining_2.csv`/`remaining_3.csv`。

`downloader_v4.py` 常用参数：
- `--limit N`：本次最多下 N 篇（不填则按队列全下）
- `--pause-min/--pause-max`：每篇间隔秒（保守 30~45）
- `--rest-every N --rest-sec S`：每 N 篇长休息 S 秒
- `--max-consec-fail K`：连续 K 篇"有入口却下不来"即熔断停车（疑似被封）
- 失败/已下的 DOI 会自动跳过（读 `LIT_LOG` 与磁盘），可反复重跑同一队列。

---

## 5. 用法 B：单机全自动（supervisor.py）

一台机器想一口气跑完、被封自动冷却、失败自动补跑：

```bash
python chrome_serve.py        # 终端1：常驻 Chrome
python supervisor.py          # 终端2：看门狗（拉起下载器+保活+补跑）
```
- 看门狗分块（每块 400 篇）调用下载器，自适应档位 L0~L3（15s~170s/篇）。
- 检测到熔断 → 整体停车冷却 20 分钟；连续 3 次熔断 → 判定配额耗尽，长休 3 小时并重启浏览器换新会话。
- 主队列跑空后，自动汇总失败项做补跑（最多 3 轮）。
- 进度/日志：`logs/authorized_browser_download_v2.csv`、`logs/v4_supervisor.log`、

> supervisor 默认读取 `QUEUE_PATH`（`remaining.csv`）。先用 `make_queue.py`
> 生成它（或把 `剩余待下载_汇总.xlsx` 转成 `remaining.csv`）。

---

## 6. 状态说明（日志"状态"列）

| 状态 | 含义 |
|---|---|
| `downloaded` | 已下到 `LIT_OUT` |
| `skipped_exists` | 磁盘已有，跳过 |
| `blocked` | 页面无 PDF 入口 / 验证页 = 无权限（**永久失败**，不触发熔断） |
| `failed_no_pdf` | 有入口却下不来 = 疑似被限速（**触发熔断**） |
| `failed_other` | 其他异常 |

"无权限"与"被限速"刻意区分：前者是期刊未订阅（跳过即可），
后者是 IP 被限流（必须停车冷却，否则越顶越封）。

---

## 7. 排查

- **全部 blocked**：Chrome profile 没登录机构订阅，或 CDP 没连上（确认 9222 端口、`chrome_serve.py` 已起）。
- **触发熔断后停了**：正常，等冷却（手动 `supervisor.py` 会自动续；手动跑就等会儿再 `--limit` 重跑）。
- **某刊整刊 blocked**：日志里同刊 blocked≥3 会被下载器记为"死刊"自动跳过；
  若其实是被封假象，删 `LIT_LOG` 里对应行或换 IP 后重跑。
- **下载器找不到 PDF 入口**：个别出版社页面结构变动，可在 `downloader_v4.py`
  的 `strategy_*` 函数里补选择器。
