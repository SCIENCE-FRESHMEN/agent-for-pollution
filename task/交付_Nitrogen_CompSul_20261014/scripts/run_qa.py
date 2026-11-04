# -*- coding: utf-8 -*-
"""
QA 自检脚本：
 A. 输出文件回读校验：行数、列数、source 合法且计数与 stats 一致、matched_KO 均在字典内、
    氮循环行 subject_description 确实含 matched_KO、转运行追加 3 列与 transDB 查表一致。
 B. 全量字节级复核：同一逻辑重扫两个源文件生成临时副本，与交付输出逐字节比对。
 C. 样例行端到端溯源：从输出抽 3 行/env 源，在源文件流式扫描确认原文存在。
 D. 大小检查与压缩决策（>400MB 转 .gz）、字典文件拷贝进交付夹。
结果写入 QA报告.txt。发现任何 FAIL 均以退出码 1 结束。
"""
import filecmp
import gzip
import json
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR.parent
TASK_DIR = SCRIPT_DIR.parents[1]
NIT_OUT = OUT_DIR / "1Nitrogen" / "氮循环KO命中行_env_ench合并.tsv"
CS_OUT = OUT_DIR / "2CompSul" / "相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv"
STATS = json.loads((SCRIPT_DIR / "stats_extraction.json").read_text(encoding="utf-8"))
CS_XLSX = TASK_DIR / "2CompSul" / "Comp_Sul transDB.xlsx"
NIT_XLSX = TASK_DIR / "Nitrogen_3files" / "氮循环Knumber_process.xlsx"
DICT_DIR = OUT_DIR / "字典_原始输入"

KO_RE = re.compile(rb"\bK\d{5}\b")
NIT_KOS = set()
NIT_PROC = {}
CS_MAP = {}
report = []
fails = []


def log(msg):
    report.append(msg)
    print(msg, flush=True)


def fail(msg):
    fails.append(msg)
    log(f"FAIL: {msg}")


def load_dicts_for_qa():
    import openpyxl
    JOIN = " // "
    wb = openpyxl.load_workbook(NIT_XLSX, read_only=True, data_only=True)
    for i, row in enumerate(wb.worksheets[0].iter_rows(values_only=True)):
        if i == 0:
            continue
        if row[0]:
            ko = str(row[0]).strip().encode("ascii")
            NIT_KOS.add(ko)
            proc = (str(row[2]).replace("\t", " ").strip()
                    if len(row) > 2 and row[2] is not None else "")
            if ko in NIT_PROC:
                old = NIT_PROC[ko]
                if proc and proc not in old.split(JOIN):
                    NIT_PROC[ko] = (old + JOIN + proc) if old else proc
            else:
                NIT_PROC[ko] = proc
    wb.close()
    wb = openpyxl.load_workbook(CS_XLSX, read_only=True, data_only=True)
    JOIN = " // "
    for row in wb.worksheets[0].iter_rows(values_only=True):
        if row[0] is None:
            continue
        ko = str(row[0]).strip().encode("ascii")
        vals = tuple(str(row[j]).replace("\t", " ").strip() if len(row) > j and row[j] is not None else ""
                     for j in (1, 2, 3))
        if ko in CS_MAP:
            CS_MAP[ko] = tuple((o + JOIN + n) if n and n not in o.split(JOIN) else o
                               for o, n in zip(CS_MAP[ko], vals))
        else:
            CS_MAP[ko] = vals
    wb.close()


def validate_output(path, expected_total, per_source, kos_all, n_cols, task):
    """回读输出并校验结构、计数、字典符合性、（转运）注释正确性。"""
    src_cnt = Counter()
    ko_cnt = Counter()
    multi_ko_rows = 0
    bad_cols = bad_src = bad_ko = bad_ann = bad_desc = 0
    header = None
    with open(path, "rb") as f:
        header = f.readline().rstrip(b"\n").split(b"\t")
        if len(header) != n_cols:
            fail(f"{task}: 表头列数 {len(header)} != {n_cols}")
        for ln, raw in enumerate(f, 2):  # 从第2行起为数据
            fields = raw.rstrip(b"\n").split(b"\t")
            if len(fields) != n_cols:
                bad_cols += 1
                if bad_cols <= 3:
                    log(f"  {task} 行{ln} 列数={len(fields)}")
                continue
            src_cnt[fields[13]] += 1
            kos = fields[14].split(b",")
            if len(kos) > 1:
                multi_ko_rows += 1
            for k in kos:
                if k not in kos_all:
                    bad_ko += 1
                ko_cnt[k] += 1
            if task == "Nitrogen":
                if not all(k in fields[12] for k in kos):
                    bad_desc += 1
                if fields[15] != NIT_PROC[kos[0]].encode("utf-8"):
                    bad_ann += 1
                    if bad_ann <= 2:
                        log(f"  {task} 行{ln} 过程列不一致: {fields[15]!r}")
            else:  # CompSul：追加3列必须与 transDB 查表一致（多KO行取首KO）
                ann = CS_MAP[kos[0]]
                got = tuple(x.decode("utf-8") for x in fields[15:18])
                if got != ann:
                    bad_ann += 1
                    if bad_ann <= 2:
                        log(f"  {task} 行{ln} 注释不一致: {got} != {ann}")
    log(f"[{task}] 数据行={sum(src_cnt.values()):,} 期望={expected_total:,} "
        f"列数异常={bad_cols} source异常={bad_src} KO不在字典={bad_ko} "
        f"描述缺KO={bad_desc} 注释不一致={bad_ann} 多KO命中行={multi_ko_rows:,}")
    log(f"[{task}] source 计数: " + ", ".join(f"{k.decode()}={v:,}" for k, v in sorted(src_cnt.items())))
    if bad_cols or bad_ko or bad_desc or bad_ann:
        fail(f"{task} 结构/符合性校验未通过")
    if sum(src_cnt.values()) != expected_total:
        fail(f"{task} 行数不符: {sum(src_cnt.values()):,} != {expected_total:,}")
    for src_b, cnt in per_source.items():
        if src_cnt[src_b.encode()] != cnt:
            fail(f"{task} source={src_b} 计数 {src_cnt[src_b.encode()]:,} != {cnt:,}")
    # 多 KO 命中行统计（转运注释仅取首 KO，需向用户披露）
    log(f"[{task}] 命中KO种类数: {len(ko_cnt):,}")


def rerun_bytecompare():
    """同一逻辑重扫源文件 -> 临时文件 -> 与交付输出逐字节比对；同时复核源文件总行数。"""
    sys.path.insert(0, str(SCRIPT_DIR))
    from run_extraction import KO_RE  # noqa
    total_lines = {}
    for out_path, is_nit in [(NIT_OUT, True), (CS_OUT, False)]:
        count_this_pass = out_path is NIT_OUT  # 行数只在第一遍统计，避免两遍相加成 2 倍
        tmp = out_path.with_suffix(".qa_tmp.tsv")
        t0 = time.time()
        with open(out_path, "rb") as fref, open(tmp, "wb") as ftmp:
            ftmp.write(fref.readline())  # 表头照抄
            for path, src in [("KEGG_des_env_kegg_e-5_num1_similarity30.tsv", "env"),
                              ("KEGG_des_ench_kegg_e-5_num1_similarity30.tsv", "ench")]:
                src_b = src.encode("ascii")
                if count_this_pass:
                    total_lines[src] = {"total": 0, "malformed": 0}
                with open(TASK_DIR / "Nitrogen_3files" / path, "rb", buffering=0) as fin:
                    rem = b""
                    read = fin.read
                    while True:
                        chunk = read(1 << 24)
                        if not chunk:
                            break
                        lines = (rem + chunk).split(b"\n")
                        rem = lines.pop()
                        tl = total_lines.get(src) if count_this_pass else None
                        if tl is not None:
                            tl["total"] += len(lines)
                        for raw in lines:
                            fields = raw.split(b"\t", 12)
                            if len(fields) < 13:
                                if tl is not None:
                                    tl["malformed"] += 1
                                continue
                            kos = KO_RE.findall(fields[12])
                            hits = [k for k in kos
                                    if (k in NIT_KOS if is_nit else k in CS_MAP)]
                            if not hits:
                                continue
                            dedup = list(dict.fromkeys(hits))
                            if is_nit:
                                ftmp.write(raw + b"\t" + src_b + b"\t" + b",".join(dedup) + b"\t"
                                           + NIT_PROC[dedup[0]].encode("utf-8") + b"\n")
                            else:
                                ann = CS_MAP[dedup[0]]
                                ftmp.write(raw + b"\t" + src_b + b"\t" + b",".join(dedup) + b"\t"
                                           + ann[0].encode("utf-8") + b"\t"
                                           + ann[1].encode("utf-8") + b"\t"
                                           + ann[2].encode("utf-8") + b"\n")
        same = filecmp.cmp(out_path, tmp, shallow=False)
        sz_a, sz_b = out_path.stat().st_size, tmp.stat().st_size
        log(f"[复核] {out_path.name}: 字节级比对 {'一致' if same else '不一致'} "
            f"(交付 {sz_a:,}B vs 重扫 {sz_b:,}B, {time.time()-t0:.0f}s)")
        if not same:
            fail(f"{out_path.name} 全量重扫不一致")
        tmp.unlink()
    for src, tl in total_lines.items():
        exp = STATS["files"][src]
        log(f"[复核] {src} 总行数: 重扫 {tl['total']:,} vs 记录 {exp['total']:,}, "
            f"malformed 重扫 {tl['malformed']:,} vs 记录 {exp['malformed']:,}")
        if tl["total"] != exp["total"] or tl["malformed"] != exp["malformed"]:
            fail(f"{src} 总行数/malformed 与记录不符")


def spot_provenance(n_per_src=3):
    """从输出每源抽 n 行，回源文件流式查找原 13 列内容是否逐字节存在。"""
    import itertools
    samples = {"env": [], "ench": []}
    for out_path in (NIT_OUT, CS_OUT):
        with open(out_path, "rb") as f:
            f.readline()
            total = sum(1 for _ in f)
        step = max(1, total // 3000)
        with open(out_path, "rb") as f:
            f.readline()
            for i, raw in enumerate(f):
                if i % step:
                    continue
                src = raw.split(b"\t")[13]
                orig = raw.split(b"\t", 13)[0:13]
                if len(samples[src.decode()]) < n_per_src:
                    key = b"\t".join(orig)
                    samples[src.decode()].append((key, out_path.name))
    for src, items in samples.items():
        fname = ("KEGG_des_env_kegg_e-5_num1_similarity30.tsv" if src == "env"
                 else "KEGG_des_ench_kegg_e-5_num1_similarity30.tsv")
        remaining = {k for k, _ in items}
        with open(TASK_DIR / "Nitrogen_3files" / fname, "rb", buffering=0) as fin:
            rem = b""
            while remaining and (chunk := fin.read(1 << 24)):
                lines = (rem + chunk).split(b"\n")
                rem = lines.pop()
                for raw in lines:
                    if raw in remaining:
                        remaining.discard(raw)
        log(f"[溯源] {src}: 抽样 {len(items)} 行, 源文件中找到 {len(items)-len(remaining)} 行")
        if remaining:
            fail(f"{src} 有 {len(remaining)} 个抽样行未能在源文件中找到")


def compress_and_finalize():
    for p in (NIT_OUT, CS_OUT):
        sz = p.stat().st_size
        log(f"[大小] {p.name}: {sz/2**20:.1f} MiB")
        if sz > 400 * 2**20:
            gz = p.with_suffix(".tsv.gz")
            with open(p, "rb") as fin, gzip.open(gz, "wb", compresslevel=6) as fout:
                shutil.copyfileobj(fin, fout, length=1 << 22)
            log(f"[压缩] {p.name} -> {gz.name}: {gz.stat().st_size/2**20:.1f} MiB, 明细文件保留原 tsv")
        DICT_DIR.mkdir(exist_ok=True)
    shutil.copy2(NIT_XLSX, DICT_DIR / NIT_XLSX.name)
    shutil.copy2(CS_XLSX, DICT_DIR / CS_XLSX.name)
    log(f"[字典] 已拷贝字典至 {DICT_DIR}")


def main():
    t0 = time.time()
    load_dicts_for_qa()
    f_env = STATS["files"]["env"]
    f_ench = STATS["files"]["ench"]
    log("=" * 70)
    log("A. 输出回读校验")
    validate_output(NIT_OUT, f_env["nit_lines"] + f_ench["nit_lines"],
                    {"env": f_env["nit_lines"], "ench": f_ench["nit_lines"]},
                    NIT_KOS, 16, "Nitrogen")
    validate_output(CS_OUT, f_env["cs_lines"] + f_ench["cs_lines"],
                    {"env": f_env["cs_lines"], "ench": f_ench["cs_lines"]},
                    set(CS_MAP), 18, "CompSul")
    log("=" * 70)
    log("C. 抽样端到端溯源")
    spot_provenance()
    log("=" * 70)
    log("B. 全量重扫字节级复核")
    rerun_bytecompare()
    log("=" * 70)
    log("D. 压缩与字典归档")
    compress_and_finalize()
    log("=" * 70)
    verdict = "PASS" if not fails else f"FAIL x{len(fails)}"
    log(f"QA 结论: {verdict}  (总耗时 {time.time()-t0:.0f}s)")
    (SCRIPT_DIR / "QA报告.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
