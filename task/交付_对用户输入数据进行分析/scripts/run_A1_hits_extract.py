# -*- coding: utf-8 -*-
"""
A1 下游演示输入制备：从上一交付的真实盐湖 KEGG 命中行中，选代表基因组，
转写为 thetaverse read_kegg_hits 的 8 列契约文件。

选基因组规则（写入 manifest）：按 B 交付表1 的 氮循环_命中行数 排序，
env/ench 各取前 6，保证跨研究前缀多样性（每个 study 前缀最多 2 个）。

8 列契约（thetaverse io.schemas.KEGG_HIT_COLUMNS / read_kegg_hits 源码）：
  col0=qseqid  col2=pident  col4=qcovhsp  col5=evalue  col7=ko（单列单值）
源行 13+3 列：c2=pct_identity c10=evalue c13=source_file c14=matched_KO。
qcovhsp 源数据无对应列，置空（read_kegg_hits to_numeric coerce 为 NaN，如实缺失）。
"""
import io
import json
import re
import sys
import collections
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:\Users\25416\Desktop\agent for pollution")
DELIV = REPO / "task" / "交付_剩余任务_20261020"
B_T1 = DELIV / "B_丰度与环境条件" / "1_基因组清单与注释丰度统计.tsv"
PREV = REPO / "task" / "交付_Nitrogen_CompSul_20261014"
TSVS = {"nitrogen": PREV / "1Nitrogen" / "氮循环KO命中行_env_ench合并.tsv",
        "transport": PREV / "2CompSul" / "相容性溶质转运KO命中行_含transDB注释_env_ench合并.tsv"}
OUT = DELIV / "A_用户输入分析" / "A1_MAG_thetaverse" / "下游演示_盐湖真实命中"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    import pandas as pd
    t1 = pd.read_csv(B_T1, sep="\t", encoding="utf-8-sig", dtype=str)
    t1["n"] = t1["氮循环_命中行数"].astype(int)
    selected: list[str] = []
    manifest = []
    study_count: dict[str, int] = {}
    for src in ("env", "ench"):
        k = 0
        sub = t1[(t1["source_file"] == src) & (t1["n"] > 0)].sort_values("n", ascending=False)
        for _, row in sub.iterrows():
            g = row["genome_id"]
            study = g.split("_bin")[0]
            if study_count.get(study, 0) >= 2:
                continue
            selected.append(g)
            study_count[study] = study_count.get(study, 0) + 1
            manifest.append({"genome_id": g, "source": src, "study_prefix": study,
                             "氮循环_命中行数": int(row["n"])})
            k += 1
            if k >= 6:
                break
    print("selected genomes:", [m["genome_id"] for m in manifest])

    sel_set = set(selected)
    bin_re = re.compile(r"^(.*_bin\d+)_\d+(?:_\d+)?$")
    tail_re = re.compile(r"^(.+)_(\d+)_(\d+)$")

    def parse(q: str) -> str:
        m = bin_re.match(q)
        if m:
            return m.group(1)
        m = tail_re.match(q)
        if m:
            return m.group(1)
        return q

    hits_path = OUT / "hits_8col_盐湖真实命中.tsv"
    n_rows = 0
    per_genome = collections.Counter()
    with open(hits_path, "w", encoding="utf-8", newline="") as fo:
        for label, path in TSVS.items():
            with open(path, encoding="utf-8", errors="replace") as fh:
                header = fh.readline().rstrip("\n").split("\t")
                i_q, i_pid, i_qs, i_qe, i_ev, i_ko = 0, 2, 6, 7, 10, 14
                for line in fh:
                    parts = line.rstrip("\n").split("\t")
                    g = parse(parts[i_q])
                    if g not in sel_set:
                        continue
                    for ko in [k for k in parts[i_ko].split(",") if k]:
                        fo.write("\t".join([f"{g}|{parts[i_q]}", "-", parts[i_pid], "-",
                                            "", parts[i_ev], "-", ko]) + "\n")
                        n_rows += 1
                        per_genome[g] += 1
    (OUT / "manifest_入选基因组.json").write_text(
        json.dumps({"selected": manifest, "rows_written": n_rows,
                    "rows_per_genome": dict(per_genome),
                    "contract": "8col: qseqid,-,pident,-,qcovhsp(缺),evalue,-,ko；源=上一交付氮循环+转运命中行"}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"rows written: {n_rows} -> {hits_path}")


if __name__ == "__main__":
    main()
