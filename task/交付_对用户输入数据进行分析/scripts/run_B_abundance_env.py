# -*- coding: utf-8 -*-
"""
B 项主脚本：盐湖所有基因组的丰度和环境条件信息整理。

输入（全部为本地已有、上一交付已核验的文件）：
  1. task/Nitrogen_3files 的两份 KEGG 比对源数据的命中行交付版：
     - 1Nitrogen/氮循环KO命中行_env_ench合并.tsv        （552,808 行）
     - 2CompSul/相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv（1,184,624 行）
  2. task/2CompSul/CompSul_Biosys_MAG_env.xlsx   表 MAG_CompSul_TPM（env 合成结果）
  3. task/2CompSul/CompSul_Biosys_faa_ench.xlsx  表 MAG_CompSul（ench 合成结果）

输出（写入本交付夹 B_丰度与环境条件/）：
  1_基因组清单与注释丰度统计.tsv   每基因组一行：来源、样品类型、研究前缀、
                                   氮循环/转运/合成的命中行数与去重基因数
  2_环境条件信息框架.tsv           每基因组一行：本地可溯源字段 + 显式[缺失]字段
  （汇总统计写 stats_B.json 供 QA 与 README 引用）

口径（重要）：
  * 「丰度」：本地数据不含任何数值型丰度（TPM/覆盖度）列 —— env 合成表表名虽为
    MAG_CompSul_TPM 但仅 3 个文本列；BLAST 命中表亦不含丰度。本表输出的是
    *注释层面的基因命中统计*（命中行数、去重 KO 数、去重基因数），并显式标注
    数值丰度 [缺失]，待上游（工作站6 /media/HD2/QXJ/ran/）提供 CoverM/TPM 表。
  * 「环境条件」：本地仅有 env/ench 两类样品类型标记与基因组名中可解析的研究
    前缀/年份 token；盐度/pH/温度/地理等逐基因组元数据本地无任何文件，全部
    显式标注 [缺失]，不做任何推断填充。
"""
import io
import json
import re
import sys
import collections
from pathlib import Path

import openpyxl

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WS_ROOT = Path(r"C:\Users\25416\Desktop\agent for pollution")
PREV = WS_ROOT / "task" / "交付_Nitrogen_CompSul_20261014"
OUT = WS_ROOT / "task" / "交付_剩余任务_20261020" / "B_丰度与环境条件"
OUT.mkdir(parents=True, exist_ok=True)

NITRO_TSV = PREV / "1Nitrogen" / "氮循环KO命中行_env_ench合并.tsv"
TRANS_TSV = PREV / "2CompSul" / "相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv"
ENV_XLSX = WS_ROOT / "task" / "2CompSul" / "CompSul_Biosys_MAG_env.xlsx"
ENCH_XLSX = WS_ROOT / "task" / "2CompSul" / "CompSul_Biosys_faa_ench.xlsx"

EXPECTED_ROWS = {"nitrogen": 552_808, "transport": 1_184_624}

BIN_RE = re.compile(r"^(.*_bin\d+)_\d+(?:_\d+)?$")
TAIL_RE = re.compile(r"^(.+)_(\d+)_(\d+)$")
YEAR_RE = re.compile(r"(?:^|_)(19\d{2}|20\d{2})(?:_|$)")

MISSING = "[缺失]_本地无此数据_需上游提供"


def parse_genome(qid: str) -> tuple[str, str]:
    """query_id -> (genome_id, rule)。bin 型截断到 _bin<N>；否则去掉尾部两个数字段。"""
    m = BIN_RE.match(qid)
    if m:
        return m.group(1), "bin"
    m = TAIL_RE.match(qid)
    if m:
        return m.group(1), "tail2"
    return qid, "asis"


class Genome:
    __slots__ = ("sources", "nit_rows", "nit_ko", "nit_proc", "tr_rows", "tr_ko",
                 "tr_sys", "synth_env", "synth_ench", "gene_env", "sol_env",
                 "gene_ench", "sol_ench", "rule")

    def __init__(self):
        self.sources = set()
        self.nit_rows = 0; self.nit_ko = set(); self.nit_proc = set()
        self.tr_rows = 0; self.tr_ko = set(); self.tr_sys = set()
        self.synth_env = 0; self.synth_ench = 0
        self.gene_env = set(); self.sol_env = set()
        self.gene_ench = set(); self.sol_ench = set()
        self.rule = ""


def scan_tsv(path: Path, kind: str, genomes: dict, stats: dict) -> None:
    rows = 0
    rule_counter = collections.Counter()
    notin_vocab_samples = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        idx_src = header.index("source_file")
        idx_ko = header.index("matched_KO")
        idx_extra = header.index("nit_cycle_process") if kind == "nitrogen" else header.index("comp_sul_transport_system")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= idx_extra:
                stats.setdefault("malformed_rows", []).append(line[:80])
                continue
            rows += 1
            g, rule = parse_genome(parts[0])
            rule_counter[rule] += 1
            rec = genomes.setdefault(g, Genome())
            rec.rule = rec.rule or rule
            src = parts[idx_src]
            rec.sources.add(src)
            kos = [k for k in parts[idx_ko].split(",") if k]
            if kind == "nitrogen":
                rec.nit_rows += 1
                rec.nit_ko.update(kos)
                if parts[idx_extra]:
                    rec.nit_proc.add(parts[idx_extra])
            else:
                rec.tr_rows += 1
                rec.tr_ko.update(kos)
                if parts[idx_extra]:
                    rec.tr_sys.add(parts[idx_extra])
    key = "nitrogen" if kind == "nitrogen" else "transport"
    stats[key] = {"rows": rows, "expected_rows": EXPECTED_ROWS[key],
                  "rows_match_expected": rows == EXPECTED_ROWS[key],
                  "distinct_genomes": sum(1 for r in genomes.values()
                                          if (r.nit_rows if kind == "nitrogen" else r.tr_rows)),
                  "parse_rules": dict(rule_counter)}
    print(f"[scan] {key}: rows={rows} genomes={stats[key]['distinct_genomes']} rules={dict(rule_counter)}")


def scan_xlsx(path: Path, sheet: str, source: str, genomes: dict, stats: dict) -> None:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[sheet]
    n = 0
    mags = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        g = str(row[0]).strip()
        gene = str(row[1]).strip() if row[1] else ""
        solute = str(row[2]).strip() if row[2] else ""
        rec = genomes.setdefault(g, Genome())
        mags.add(g)
        rec.sources.add(source)
        if source == "env":
            rec.synth_env += 1
            if gene: rec.gene_env.add(gene)
            if solute: rec.sol_env.add(solute)
        else:
            rec.synth_ench += 1
            if gene: rec.gene_ench.add(gene)
            if solute: rec.sol_ench.add(solute)
        n += 1
    wb.close()
    stats[f"synth_{source}"] = {"rows": n, "sheet": sheet, "distinct_MAGs": len(mags)}
    print(f"[scan] synth_{source}: rows={n} MAGs={len(mags)}")


def study_prefix(genome: str) -> tuple[str, str]:
    m = YEAR_RE.search(genome)
    if m:
        prefix = genome[: m.start()].strip("_")
        return (prefix or MISSING), m.group(1)
    if "_bin" in genome:
        return genome.split("_bin")[0], ""
    return genome, ""


def main() -> None:
    stats = {"inputs": {}, "malformed_rows_count": 0}
    genomes: dict[str, Genome] = {}

    for p in (NITRO_TSV, TRANS_TSV, ENV_XLSX, ENCH_XLSX):
        stats["inputs"][p.name] = p.stat().st_size

    scan_tsv(NITRO_TSV, "nitrogen", genomes, stats)
    scan_tsv(TRANS_TSV, "transport", genomes, stats)
    scan_xlsx(ENV_XLSX, "MAG_CompSul_TPM", "env", genomes, stats)
    scan_xlsx(ENCH_XLSX, "MAG_CompSul", "ench", genomes, stats)

    # ---- 输出表1：基因组清单与注释丰度统计 ----
    t1 = OUT / "1_基因组清单与注释丰度统计.tsv"
    cols1 = ["genome_id", "source_file", "样品类型", "研究前缀_自基因组名解析", "年份token_自基因组名解析",
             "氮循环_命中行数", "氮循环_去重KO数", "氮循环_过程类别数",
             "转运_命中行数", "转运_去重KO数", "转运_去重转运系统数",
             "合成_env_记录数", "合成_env_去重基因数", "合成_env_去重溶质数",
             "合成_ench_记录数", "合成_ench_去重基因数", "合成_ench_去重溶质数",
             "数值丰度TPM或覆盖度"]
    with open(t1, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("\t".join(cols1) + "\n")
        for g in sorted(genomes):
            r = genomes[g]
            pre, year = study_prefix(g)
            sample = "环境样品基因组(env)" if r.sources == {"env"} else (
                "富集培养基因组(ench)" if r.sources == {"ench"} else "env+ench")
            fh.write("\t".join(map(str, [
                g, "+".join(sorted(r.sources)), sample, pre, year,
                r.nit_rows, len(r.nit_ko), len(r.nit_proc),
                r.tr_rows, len(r.tr_ko), len(r.tr_sys),
                r.synth_env, len(r.gene_env), len(r.sol_env),
                r.synth_ench, len(r.gene_ench), len(r.sol_ench),
                MISSING])) + "\n")
    stats["out_table1"] = {"path": t1.name, "rows": len(genomes), "columns": cols1}

    # ---- 输出表2：环境条件信息框架 ----
    t2 = OUT / "2_环境条件信息框架.tsv"
    env_cols = ["genome_id", "source_file", "样品类型", "研究前缀_自基因组名解析", "年份token_自基因组名解析",
                "盐度", "pH", "温度", "地理位置", "采样时间", "培养条件", "缺失说明"]
    with open(t2, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("\t".join(env_cols) + "\n")
        for g in sorted(genomes):
            r = genomes[g]
            pre, year = study_prefix(g)
            sample = "环境样品基因组(env)" if r.sources == {"env"} else (
                "富集培养基因组(ench)" if r.sources == {"ench"} else "env+ench")
            fh.write("\t".join([
                g, "+".join(sorted(r.sources)), sample, pre, year,
                MISSING, MISSING, MISSING, MISSING, MISSING, MISSING,
                "本地仅有样品类型（env=环境样品基因组/ench=富集培养基因组）与基因组名token；"
                "逐基因组盐度/pH/温度等环境元数据在工作站6源目录，本地无文件，未做推断"]) + "\n")
    stats["out_table2"] = {"path": t2.name, "rows": len(genomes), "columns": env_cols}

    stats["totals"] = {
        "distinct_genomes_union": len(genomes),
        "genomes_env_only": sum(1 for r in genomes.values() if r.sources == {"env"}),
        "genomes_ench_only": sum(1 for r in genomes.values() if r.sources == {"ench"}),
        "genomes_in_both": sum(1 for r in genomes.values() if len(r.sources) == 2),
        "with_nitrogen_hits": sum(1 for r in genomes.values() if r.nit_rows),
        "with_transport_hits": sum(1 for r in genomes.values() if r.tr_rows),
        "with_synth_env": sum(1 for r in genomes.values() if r.synth_env),
        "with_synth_ench": sum(1 for r in genomes.values() if r.synth_ench),
        "sum_nit_rows_check": sum(r.nit_rows for r in genomes.values()),
        "sum_tr_rows_check": sum(r.tr_rows for r in genomes.values()),
        "sum_synth_env_check": sum(r.synth_env for r in genomes.values()),
        "sum_synth_ench_check": sum(r.synth_ench for r in genomes.values()),
    }
    stats["malformed_rows_count"] = len(stats.pop("malformed_rows", []))

    sp = OUT.parent / "scripts" / "stats_B.json"
    sp.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats["totals"], ensure_ascii=False, indent=2))
    print(f"[done] {t1}\n[done] {t2}\n[done] {sp}")


if __name__ == "__main__":
    main()
