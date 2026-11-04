# -*- coding: utf-8 -*-
"""
单遍流式提取脚本（任务1 Nitrogen + 任务2 CompSul 转运）：
  一次扫描两个大 TSV，按 KO 字典分别写出：
    1Nitrogen/氮循环KO命中行_env_ench合并.tsv
    2CompSul/相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv
字节级处理（不做编解码），输出行 = 输入行原文 + 追加列，保证零篡改。
可重复运行（覆盖重跑）。
"""
import json
import re
import time
from collections import Counter
from pathlib import Path

import openpyxl

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parents[1]          # task/
OUT_DIR = SCRIPT_DIR.parent               # 交付目录

NIT_XLSX = TASK_DIR / "Nitrogen_3files" / "氮循环Knumber_process.xlsx"
CS_XLSX = TASK_DIR / "2CompSul" / "Comp_Sul transDB.xlsx"
TSVS = [
    (TASK_DIR / "Nitrogen_3files" / "KEGG_des_env_kegg_e-5_num1_similarity30.tsv", "env"),
    (TASK_DIR / "Nitrogen_3files" / "KEGG_des_ench_kegg_e-5_num1_similarity30.tsv", "ench"),
]
NIT_OUT = OUT_DIR / "1Nitrogen" / "氮循环KO命中行_env_ench合并.tsv"
CS_OUT = OUT_DIR / "2CompSul" / "相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv"
STATS_OUT = SCRIPT_DIR / "stats_extraction.json"
DICT_COPY_DIR = OUT_DIR / "字典_原始输入"

KO_RE = re.compile(rb"\bK\d{5}\b")
JOIN = " // "

HEAD13 = ["query_id", "subject_id", "pct_identity", "alignment_length", "mismatch",
          "gap_open", "query_start", "query_end", "subject_start", "subject_end",
          "evalue", "bit_score", "subject_description"]
NIT_HEADER = (HEAD13 + ["source_file", "matched_KO", "nit_cycle_process"])
CS_HEADER = (HEAD13 + ["source_file", "matched_KO",
                       "comp_sul_gene_name", "comp_sul_function",
                       "comp_sul_transport_system"])


def sanitize(s: str) -> str:
    return s.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def load_dicts():
    wb = openpyxl.load_workbook(NIT_XLSX, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    nit_rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # 表头 ko|gene|N-cycle process
        ko = sanitize(str(row[0]))
        gene = sanitize(str(row[1])) if len(row) > 1 and row[1] is not None else ""
        proc = sanitize(str(row[2])) if len(row) > 2 and row[2] is not None else ""
        if ko:
            nit_rows.append((ko, gene, proc))
    wb.close()

    wb = openpyxl.load_workbook(CS_XLSX, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    cs_rows = []  # (ko, gene, function, system)
    for row in ws.iter_rows(values_only=True):
        ko = sanitize(str(row[0])) if row[0] is not None else ""
        if not ko:
            continue
        vals = []
        for j in (1, 2, 3):  # transDB 第2、3、4列
            v = str(row[j]) if len(row) > j and row[j] is not None else ""
            vals.append(sanitize(v))
        cs_rows.append((ko, *vals))
    wb.close()

    nit_set = {k.encode("ascii") for k, *_ in nit_rows}
    # 重复 KO 的过程标注按列去重后用 " // " 连接（当前字典无重复，防御性处理）
    nit_proc = {}
    for ko, _gene, proc in nit_rows:
        key = ko.encode("ascii")
        if key in nit_proc:
            old = nit_proc[key]
            if proc and proc not in old.split(JOIN):
                nit_proc[key] = (old + JOIN + proc) if old else proc
        else:
            nit_proc[key] = proc
    # 重复 KO 的注释按列去重后用 " // " 连接（如 K10111 同属两个转运系统）
    cs_map = {}
    for ko, gene, func, system in cs_rows:
        key = ko.encode("ascii")
        if key in cs_map:
            old = cs_map[key]
            cs_map[key] = tuple(
                (o + JOIN + n) if n and n not in o.split(JOIN) else o
                for o, n in zip(old, (gene, func, system)))
        else:
            cs_map[key] = (gene, func, system)
    cs_set = set(cs_map)

    meta = {
        "nit_dict_rows": len(nit_rows),
        "nit_dict_unique_ko": len(nit_set),
        "nit_dict_duplicates": [k for k, c in Counter(k for k, *_ in nit_rows).items() if c > 1],
        "nit_dict_source": NIT_XLSX.name,
        "cs_dict_rows": len(cs_rows),
        "cs_dict_unique_ko": len(cs_set),
        "cs_dict_duplicates": [k for k, c in Counter(k for k, *_ in cs_rows).items() if c > 1],
        "dict_overlap_nit_vs_cs": sorted({k for k, *_ in nit_rows} & {k for k, *_ in cs_rows}),
    }
    return nit_set, nit_proc, cs_map, cs_set, meta


def main():
    t0 = time.time()
    nit_set, nit_proc, cs_map, cs_set, meta = load_dicts()
    print(f"[{time.time()-t0:6.1f}s] 字典加载: {meta}", flush=True)

    NIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    CS_OUT.parent.mkdir(parents=True, exist_ok=True)
    DICT_COPY_DIR.mkdir(parents=True, exist_ok=True)

    stats = {"meta": meta, "files": {}}
    with open(NIT_OUT, "wb") as fnit, open(CS_OUT, "wb") as fcs:
        fnit.write("\t".join(NIT_HEADER).encode("utf-8") + b"\n")
        fcs.write("\t".join(CS_HEADER).encode("utf-8") + b"\n")

        for path, src in TSVS:
            src_b = src.encode("ascii")
            cnt = {"total": 0, "nit_lines": 0, "cs_lines": 0, "both_lines": 0,
                   "malformed": 0}
            nit_ko_cnt, cs_ko_cnt = Counter(), Counter()
            tf = time.time()
            with open(path, "rb", buffering=0) as fin:
                rem = b""
                read = fin.read
                while True:
                    chunk = read(1 << 24)          # 16 MiB
                    if not chunk:
                        break
                    lines = (rem + chunk).split(b"\n")
                    rem = lines.pop()
                    for raw in lines:
                        cnt["total"] += 1
                        fields = raw.split(b"\t", 12)
                        if len(fields) < 13:
                            cnt["malformed"] += 1
                            continue
                        kos = KO_RE.findall(fields[12])
                        if not kos:
                            continue
                        nit_hits, cs_hits = [], []
                        for k in kos:
                            if k in nit_set and k not in nit_hits:
                                nit_hits.append(k)
                            if k in cs_set and k not in cs_hits:
                                cs_hits.append(k)
                        if nit_hits:
                            fnit.write(raw + b"\t" + src_b + b"\t"
                                       + b",".join(nit_hits) + b"\t"
                                       + nit_proc[nit_hits[0]].encode("utf-8") + b"\n")
                            cnt["nit_lines"] += 1
                            nit_ko_cnt.update(nit_hits)
                            if cs_hits:
                                cnt["both_lines"] += 1
                        if cs_hits:
                            ann = cs_map[cs_hits[0]]
                            fcs.write(raw + b"\t" + src_b + b"\t"
                                      + b",".join(cs_hits) + b"\t"
                                      + ann[0].encode("utf-8") + b"\t"
                                      + ann[1].encode("utf-8") + b"\t"
                                      + ann[2].encode("utf-8") + b"\n")
                            cnt["cs_lines"] += 1
                            cs_ko_cnt.update(cs_hits)
                    crossed = cnt["total"] // 5_000_000 != (cnt["total"] - len(lines)) // 5_000_000
                    if crossed:
                        print(f"[{time.time()-tf:6.1f}s] {src}: {cnt['total']:,} 行, "
                              f"nit={cnt['nit_lines']:,}, cs={cnt['cs_lines']:,}", flush=True)
                if rem.strip():
                    print(f"WARN({src}): 文件末尾有无换行残留 {rem[:60]!r}", flush=True)
            cnt["nit_ko_counts"] = {k.decode(): v for k, v in nit_ko_cnt.items()}
            cnt["cs_ko_counts"] = {k.decode(): v for k, v in cs_ko_cnt.items()}
            cnt["elapsed_s"] = round(time.time() - tf, 1)
            stats["files"][src] = cnt
            print(f"[{time.time()-t0:6.1f}s] {src} 完成: total={cnt['total']:,} "
                  f"nit={cnt['nit_lines']:,} cs={cnt['cs_lines']:,} "
                  f"malformed={cnt['malformed']}", flush=True)

    nit_hit, cs_hit = set(), set()
    for f in stats["files"].values():
        nit_hit |= set(f["nit_ko_counts"])
        cs_hit |= set(f["cs_ko_counts"])
    stats["nit_never_matched"] = sorted({k.decode() for k in nit_set} - nit_hit)
    stats["cs_never_matched"] = sorted({k.decode() for k in cs_set} - cs_hit)
    stats["elapsed_total_s"] = round(time.time() - t0, 1)
    STATS_OUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"DONE 总耗时 {stats['elapsed_total_s']}s, stats -> {STATS_OUT}", flush=True)


if __name__ == "__main__":
    main()
