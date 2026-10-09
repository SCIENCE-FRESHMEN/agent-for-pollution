# -*- coding: utf-8 -*-
"""盘点 downloads/ 并生成 下载报告.md（按期刊统计 + 失败清单）"""
import csv, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import out_utf8, DL, LOGS, sn, now
out_utf8()

def main():
    DL.mkdir(parents=True, exist_ok=True)
    per_journal, total = {}, 0
    for p in DL.rglob("*.pdf"):
        if p.stat().st_size < 20000:
            continue
        total += 1
        j = p.parent.name
        per_journal[j] = per_journal.get(j, 0) + 1

    fails = []
    flog = LOGS / "sweeper_log.csv"
    if flog.exists():
        for r in csv.DictReader(open(flog, encoding="utf-8-sig", newline="")):
            st = r.get("状态") or r.get("状态", "")
            if not str(st).startswith("downloaded"):
                fails.append((r.get("DOI"), r.get("期刊"), st))

    lines = [f"# 文献下载报告", "",
             f"- 生成时间：{now()}",
             f"- 已下载 PDF 总数：**{total} 篇**（存放于 downloads/，按期刊分文件夹）", ""]
    if per_journal:
        lines += ["## 按期刊统计", "", "| 期刊 | 篇数 |", "|---|---|"]
        for j, c in sorted(per_journal.items(), key=lambda x: -x[1]):
            lines.append(f"| {j} | {c} |")
        lines.append("")
    if fails:
        lines += ["## 未成功清单（状态见括号）", ""]
        for doi, j, st in fails:
            lines.append(f"- {doi}（{j}）— {st}")
        lines.append("")
    lines += ["## 状态说明", "",
              "- `downloaded`：成功",
              "- `blocked:*`：出版社页面无下载入口——通常是本校未订阅该期刊（永久不可得，除非换有订阅的机构）",
              "- `failed_no_pdf:*`：疑似被出版社限速，重跑本工具会自动重试",
              "- `failed_other:*`：网络/页面异常，重跑会自动重试", ""]
    out = ROOT_IF() / "下载报告.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] 报告已生成: {out}")
    print(f"[report] 磁盘 PDF 共 {total} 篇")

def ROOT_IF():
    return Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    main()
