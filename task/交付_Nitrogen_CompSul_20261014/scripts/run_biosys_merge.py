# -*- coding: utf-8 -*-
"""
任务2b：相容性溶质合成结果合并。
自动发现 2CompSul 下 *env*.xlsx / *ench*.xlsx（含合成结果的文件），
各自取主数据表（表名以 MAG_CompSul 开头；否则取第一个表），
合并为一个 xlsx：合并结果 + 各来源原始表 + 附加映射表（如 Entry_Mapping）。
2CompSul 文件夹内容更新后直接重跑本脚本即可。
"""
import json
import time
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR.parent
TASK_DIR = SCRIPT_DIR.parents[1]
COMP_DIR = TASK_DIR / "2CompSul"
MERGED_OUT = OUT_DIR / "2CompSul" / "相容性溶质合成_env_ench合并.xlsx"
STATS_OUT = SCRIPT_DIR / "stats_biosys.json"

SOURCES = {"env": "CompSul_Biosys_*env*.xlsx", "ench": "CompSul_Biosys_*ench*.xlsx"}
MAIN_PREFIX = "MAG_CompSul"   # 主数据表名前缀


def find_workbook(pattern):
    hits = sorted(COMP_DIR.glob(pattern))
    hits = [h for h in hits if not h.name.startswith("~$")]
    if not hits:
        return None, []
    return hits[0], hits


def main():
    t0 = time.time()
    stats = {"sources": {}, "output": str(MERGED_OUT.name)}
    merged_parts = []
    extra_sheets = []  # (sheet_name, DataFrame)

    for src, pattern in SOURCES.items():
        wb_path, all_hits = find_workbook(pattern)
        if wb_path is None:
            print(f"WARN: 未找到 {src} 的合成结果文件（模式 {pattern}），跳过")
            stats["sources"][src] = {"found": False}
            continue
        xls = pd.ExcelFile(wb_path, engine="openpyxl")
        main_sheet = next((s for s in xls.sheet_names if s.startswith(MAIN_PREFIX)),
                          xls.sheet_names[0])
        df = pd.read_excel(xls, sheet_name=main_sheet, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how="all")
        df["source_file"] = f"{wb_path.name} [{main_sheet}]"
        merged_parts.append(df)
        print(f"{src}: {wb_path.name} 表[{main_sheet}] {len(df):,} 行, 列={list(df.columns)}")

        # 其余表（如 Entry_Mapping）原样附带，避免信息丢失
        for s in xls.sheet_names:
            if s == main_sheet:
                continue
            extra = pd.read_excel(xls, sheet_name=s, dtype=str)
            extra_sheets.append((f"{src}_{s}", extra))
            print(f"  附带表 {src}_{s}: {len(extra):,} 行")
        xls.close()

        stats["sources"][src] = {
            "found": True, "file": wb_path.name, "sheet": main_sheet,
            "rows": int(len(df)),
            "unique_MAGs": int(df.iloc[:, 0].nunique()),
            "unique_solutes": int(df[df.columns[-2]].nunique())
            if len(df.columns) >= 2 else None,
        }

    if not merged_parts:
        print("ERROR: 未合并任何数据，退出")
        sys_exit = 1
        raise SystemExit(1)

    merged = pd.concat(merged_parts, ignore_index=True)
    # 列序：原列 + source_file 放最后
    base_cols = [c for c in merged.columns if c != "source_file"]
    merged = merged[base_cols + ["source_file"]]

    with pd.ExcelWriter(MERGED_OUT, engine="openpyxl") as w:
        merged.to_excel(w, sheet_name="合并结果", index=False)
        for name, extra in extra_sheets:
            extra.to_excel(w, sheet_name=name[:31], index=False)

    stats["merged_rows"] = int(len(merged))
    stats["expected_rows"] = int(sum(s.get("rows", 0) for s in stats["sources"].values()
                                     if s.get("found")))
    stats["match"] = stats["merged_rows"] == stats["expected_rows"]
    env_mags = set()
    MERGED_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATS_OUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE 合并 {stats['merged_rows']:,} 行 (期望 {stats['expected_rows']:,}), "
          f"match={stats['match']}, 耗时 {time.time()-t0:.1f}s -> {MERGED_OUT}")


if __name__ == "__main__":
    main()
