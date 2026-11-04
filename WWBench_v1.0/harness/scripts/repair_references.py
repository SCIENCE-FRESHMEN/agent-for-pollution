# -*- coding: utf-8 -*-
"""引文截断修复管线(v1.1 新增,对应 P1-8)。

背景:题库"参考文献"列的部分条目在源数据导入时被截断为约 45 字符
(如 "10.1021/acs.est.2c01104 Glutamate Enhances Osmoadaptation of Ana"),
capsule 的 references.txt 因此携带残缺标题。

本脚本对给定题号集合:
1. 抽取 DOI 前缀条目,经 Crossref API(api.crossref.org,仅公开元数据)回填完整标题;
2. 非 DOI 条目(内部编号 L0xxx / 教科书来源)保持原样,标记 [待补全:非DOI条目];
3. 就地重写对应 capsule 的 Data/references.txt,并输出修复报告 CSV。

用法:
  python scripts/repair_references.py --questions ../dataset/questions-verified-52.csv
  python scripts/repair_references.py --qids q-061,q-104            # 指定题号
可选:--dry-run(只输出报告不改写 capsule);--delay 秒(默认 0.3,礼貌限速)。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wwbench.dataset import load_questions  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAPSULES = ROOT.parent / "dataset" / "capsules"
CACHE_PATH = ROOT / "outputs" / "crossref_title_cache.json"
REPORT_PATH = ROOT / "outputs" / "reference_repair_report.csv"

DOI_RE = re.compile(r"^(10\.\d{4,9}/\S+)(?:\s+(.*))?$")
MAILTO = "wwbench-repair@example.org"


def split_entry(entry: str) -> tuple[str, str]:
    """把 '10.1021/xxx Some Title' 拆成 (doi, 截断标题或空串)。"""
    m = DOI_RE.match(entry.strip())
    if not m:
        return "", ""
    return m.group(1).rstrip(".,"), (m.group(2) or "").strip()


def fetch_title(doi: str, delay: float, cache: dict) -> str:
    if doi in cache:
        return cache[doi]
    url = f"https://api.crossref.org/works/{urllib.request.quote(doi)}?mailto={MAILTO}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"WWBench-repair/1.0 (mailto:{MAILTO})"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        titles = data.get("message", {}).get("title") or []
        title = titles[0].strip() if titles else ""
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError) as err:
        title = ""
        print(f"  [warn] {doi}: {err}")
    cache[doi] = title
    time.sleep(delay)
    return title


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="capsule 引文截断修复(Crossref 回填)")
    ap.add_argument("--questions", default=str(ROOT.parent / "dataset" / "questions-verified-52.csv"))
    ap.add_argument("--qids", default="", help="逗号分隔题号;缺省则用 --questions 文件全部题号")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    questions = load_questions(args.questions)
    if args.qids:
        wanted = {q.strip() for q in args.qids.split(",") if q.strip()}
        questions = [q for q in questions if q.question_id in wanted]
    print(f"[scope] {len(questions)} 题")

    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    rows, changed = [], 0
    try:
        for q in questions:
            repaired, doi_n, fixed_n, missing_n = [], 0, 0, 0
            for entry in q.references:
                doi, old_title = split_entry(entry)
                if not doi:
                    repaired.append(entry if entry.endswith("]") else f"{entry} [待补全:非DOI条目]")
                    missing_n += 1
                    continue
                doi_n += 1
                title = fetch_title(doi, args.delay, cache)
                if title:
                    repaired.append(f"{doi} {title}")
                    if title != old_title:
                        fixed_n += 1
                else:
                    repaired.append(entry)
                    missing_n += 1
            rows.append({
                "question_id": q.question_id, "refs_total": len(q.references),
                "refs_doi": doi_n, "refs_fixed": fixed_n, "refs_unresolved": missing_n,
            })
            if fixed_n and not args.dry_run:
                zp = CAPSULES / f"{q.question_id}.zip"
                with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("Data/references.txt", "\n\n".join(repaired) or "(无参考文献)")
                changed += 1
            print(f"[{q.question_id}] doi={doi_n} fixed={fixed_n} unresolved={missing_n}")
    finally:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REPORT_PATH.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["question_id", "refs_total", "refs_doi",
                                                   "refs_fixed", "refs_unresolved"])
            writer.writeheader()
            writer.writerows(rows)

    total_fixed = sum(r["refs_fixed"] for r in rows)
    total_doi = sum(r["refs_doi"] for r in rows)
    print(f"[done] 题数={len(rows)} DOI条目={total_doi} 回填标题={total_fixed} "
          f"重写capsule={changed} {'(dry-run 未写盘)' if args.dry_run else ''}")
    print(f"[report] {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
