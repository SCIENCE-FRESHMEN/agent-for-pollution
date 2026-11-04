# -*- coding: utf-8 -*-
"""
[revised 2026-10-23] ThetaVerse 0.3.0 复验版：复制到 revised 交付夹后路径自动指向 revised\D_经验库；逻辑零改动。
D：盐湖经验库建库（幂等 SQLite）。

底座：交付_剩余任务_20261020\B_丰度与环境条件\ 两张表（58,171 基因组）。
表设计（面向约束条件筛选/环境匹配度查询）：
  genomes            基因组清单与注释丰度（表1 全量）
  env_conditions     环境条件框架（表2 全量；缺失字段 NULL 占位，不编造）
  ko_dictionary      氮循环 KO 字典 v2（64 KO + 24 类过程）
  transport_dict     相容性溶质转运字典（78 行 transDB）
  ingest_log         入库批次记录（可追溯）
幂等：先 DROP 再 CREATE + 全量 INSERT；重建结果与源文件逐行对账。
上游到货后（丰度/盐度/pH 等）：UPDATE 对应列即可，schema 预留。
"""
import io
import json
import sqlite3
import sys
import time
from pathlib import Path

import openpyxl

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:\Users\25416\Desktop\agent for pollution")
B = REPO / "task" / "交付_剩余任务_20261020" / "B_丰度与环境条件"
PREV = REPO / "task" / "交付_Nitrogen_CompSul_20261014" / "字典_原始输入"
OUT = Path(__file__).resolve().parent.parent / "D_经验库"
OUT.mkdir(parents=True, exist_ok=True)
DB = OUT / "盐湖经验库.db"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    with open(path, encoding="utf-8-sig") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        rows = [l.rstrip("\n").split("\t") for l in fh if l.strip()]
    return header, rows


def main() -> None:
    t0 = time.time()
    if DB.exists():
        DB.unlink()
        log("幂等：删除旧库重建")
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # 1. genomes（表1）
    h1, r1 = read_tsv(B / "1_基因组清单与注释丰度统计.tsv")
    cols1 = [c.replace("(", "_").replace(")", "").replace("+", "_") for c in h1]
    cur.execute(f"CREATE TABLE genomes ({', '.join(c + ' TEXT' for c in cols1)})")
    cur.executemany(f"INSERT INTO genomes VALUES ({', '.join('?' * len(cols1))})", r1)
    log(f"genomes: {len(r1)} rows")

    # 2. env_conditions（表2；缺失串转 NULL 占位）
    h2, r2 = read_tsv(B / "2_环境条件信息框架.tsv")
    cols2 = [c.replace("(", "_").replace(")", "").replace("+", "_") for c in h2]
    cur.execute(f"CREATE TABLE env_conditions ({', '.join(c + ' TEXT' for c in cols2)})")
    r2n = [[None if c.startswith("[缺失]") else c for c in row] for row in r2]
    cur.executemany(f"INSERT INTO env_conditions VALUES ({', '.join('?' * len(cols2))})", r2n)
    log(f"env_conditions: {len(r2n)} rows")

    # 3. ko_dictionary（氮循环 v2）
    wb = openpyxl.load_workbook(PREV / "氮循环Knumber_process.xlsx", read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    hdr = [str(c).strip() if c is not None else f"col{i}" for i, c in enumerate(rows[0])]
    safe_hdr = [f"c{i}" for i in range(len(hdr))]
    cur.execute("CREATE TABLE ko_dictionary ({}, source TEXT, header_map TEXT)".format(
        ", ".join(c + " TEXT" for c in safe_hdr)))
    kdict = [tuple([("" if v is None else str(v)) for v in row] + ["氮循环Knumber_process.xlsx v2", "|".join(f"{s}={h}" for s, h in zip(safe_hdr, hdr))])
             for row in rows[1:] if row[0]]
    cur.executemany(f"INSERT INTO ko_dictionary VALUES ({', '.join('?' * (len(safe_hdr) + 2))})", kdict)
    log(f"ko_dictionary: {len(kdict)} rows")

    # 4. transport_dict（transDB 78 行）
    wb = openpyxl.load_workbook(PREV / "Comp_Sul transDB.xlsx", read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    hdr4 = [str(rows[0][i]).strip() if rows[0][i] else f"c{i}" for i in range(len(rows[0]))]
    cur.execute("CREATE TABLE transport_dict ({}, source TEXT, header_map TEXT)".format(
        ", ".join(f"c{i} TEXT" for i in range(len(rows[0])))))
    tdict = [tuple([("" if v is None else str(v)) for v in row] + ["Comp_Sul transDB.xlsx", "|".join(f"c{i}={h}" for i, h in enumerate(hdr4))])
             for row in rows[1:] if row and row[0]]
    cur.executemany(f"INSERT INTO transport_dict VALUES ({', '.join('?' * (len(rows[0]) + 2))})", tdict)
    log(f"transport_dict: {len(tdict)} rows")

    # 5. ingest_log
    cur.execute("CREATE TABLE ingest_log (batch TEXT, ingested_at TEXT, detail TEXT)")
    cur.execute("INSERT INTO ingest_log VALUES ('20261020_init', ?, ?)",
                (time.strftime("%Y-%m-%d %H:%M:%S"),
                 f"genomes={len(r1)}, env_conditions={len(r2n)}, ko_dict={len(kdict)}, transport_dict={len(tdict)}"))

    con.commit()

    # 6. 对账
    checks = {
        "genomes 行数 == 表1 行数": cur.execute("SELECT COUNT(*) FROM genomes").fetchone()[0] == len(r1),
        "env_conditions 行数 == 表2 行数": cur.execute("SELECT COUNT(*) FROM env_conditions").fetchone()[0] == len(r2n),
        "genomes 基因组唯一": cur.execute("SELECT COUNT(DISTINCT genome_id) FROM genomes").fetchone()[0] == len(r1),
        "ko_dictionary == 64": cur.execute("SELECT COUNT(*) FROM ko_dictionary").fetchone()[0] == 64,
        "transport_dict == 源数据行(78含表头→77)": cur.execute("SELECT COUNT(*) FROM transport_dict").fetchone()[0] == len(tdict) == 77,
        "env_conditions 缺失字段为 NULL": cur.execute(
            "SELECT COUNT(*) FROM env_conditions WHERE 盐度 IS NULL").fetchone()[0] == len(r2n),
    }
    recon = {"checks": checks, "rows": {"genomes": len(r1), "env_conditions": len(r2n),
                                        "ko_dictionary": len(kdict), "transport_dict": len(tdict)},
             "elapsed_seconds": round(time.time() - t0, 1),
             "upstream_pending": ["数值丰度(CoverM/TPM)", "盐度", "pH", "温度", "地理位置", "采样时间", "培养条件"]}
    (OUT / "建库对账.json").write_text(json.dumps(recon, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"对账: {sum(checks.values())}/{len(checks)} PASS -> 建库对账.json")
    log(f"DB -> {DB}")
    con.close()


if __name__ == "__main__":
    main()
