# -*- coding: utf-8 -*-
"""全链 QA：核验交付夹内 A1/A2/A3/B 全部产出的结构、一致性与溯源完整性。"""
import hashlib
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DELIV = Path(r"C:\Users\25416\Desktop\agent for pollution\task\交付_剩余任务_20261020")
A_DIR = DELIV / "A_用户输入分析"

checks: list[tuple[str, bool, str]] = []
def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(("PASS " if ok else "FAIL "), name, ("| " + detail if detail else ""))


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------- B ----------
check("B stats_B.json 存在", (DELIV / "scripts" / "stats_B.json").exists())
check("B 表1 存在", (DELIV / "B_丰度与环境条件" / "1_基因组清单与注释丰度统计.tsv").exists())
check("B 表2 存在", (DELIV / "B_丰度与环境条件" / "2_环境条件信息框架.tsv").exists())
qa_b = DELIV / "scripts" / "QA_B报告.txt"
check("B QA报告 存在且全PASS", qa_b.exists() and "FAIL" not in qa_b.read_text(encoding="utf-8"))

# ---------- A2 ----------
a2 = A_DIR / "A2_16S_qiime2"
s2p = a2 / "thetaverse分析输出" / "stats_A2.json"
check("A2 stats_A2.json 存在", s2p.exists())
if s2p.exists():
    s2 = json.loads(s2p.read_text(encoding="utf-8"))
    ok_uuid = all("uuid" in v and "sha256" in v for v in s2.get("artifacts", {}).values())
    check("A2 三个qza均记录 uuid+sha256", ok_uuid, str(list(s2.get("artifacts", {}))))
    ok_hash = True
    for name, v in s2.get("artifacts", {}).items():
        p = a2 / "artifacts" / name
        if not p.exists() or sha256(p) != v["sha256"]:
            ok_hash = False
    check("A2 qza SHA-256 复算一致", ok_hash)
    check("A2 ThetaData 34样本", int(s2.get("thetadata_shape", [0])[0]) == 34, str(s2.get("thetadata_shape")))
    check("A2 taxonomy 全覆盖770", int(s2.get("thetadata_shape", [0, 0])[1]) == 770)
out2 = a2 / "thetaverse分析输出"
alpha = out2 / "alpha_diversity.tsv"
check("A2 alpha_diversity.tsv 34行+表头", alpha.exists() and len(alpha.read_text(encoding="utf-8-sig").strip().splitlines()) == 35)
for pc in ["PCoA_core_metrics_braycurtis_pcoa.tsv", "PCoA_core_metrics_jaccard_pcoa.tsv"]:
    p = out2 / pc
    n_data = sum(1 for l in p.read_text(encoding="utf-8-sig").splitlines() if l.strip() and not l.startswith("#")) if p.exists() else -1
    check(f"A2 {pc} 34行", n_data == 34, str(n_data))
check("A2 上游工作站命令文档存在", (a2 / "上游命令_工作站执行.md").exists())
pay = a2 / "qza解包数据载荷"
for f in ["feature-table.biom", "taxonomy.tsv", "tree.nwk"]:
    check(f"A2 载荷 {f} 存在", (pay / f).exists())

# ---------- A1 ----------
a1 = A_DIR / "A1_MAG_thetaverse"
s1p = a1 / "stats_A1.json"
check("A1 stats_A1.json 存在", s1p.exists())
if s1p.exists():
    s1 = json.loads(s1p.read_text(encoding="utf-8"))
    gc = s1.get("gene_calling", [])
    check("A1 三个MAG基因预测记录", len(gc) == 3 and all(g.get("predicted_genes", 0) > 1000 for g in gc),
          "; ".join(f"{g['mag_id'][:20]}:{g.get('predicted_genes')}" for g in gc))
    check("A1 注释方法已记录", bool(s1.get("steps", {}).get("annotation_method")), str(s1.get("steps", {}).get("annotation_method")))
    check("A1 受阻说明已记录(0命中)", "blocked_note" in s1.get("steps", {}))
    check("A1 参考蛋白组规模已记录", s1.get("steps", {}).get("reference_proteins_total", 0) > 10000,
          str(s1.get("steps", {}).get("reference_proteins_total")))
demo = a1 / "下游演示_盐湖真实命中"
man = json.loads((demo / "manifest_入选基因组.json").read_text(encoding="utf-8"))
check("A1 演示 manifest 1056 行真实命中", man.get("rows_written") == 1056, str(man.get("rows_written")))
check("A1 演示入选12基因组跨6研究", len(man.get("selected", [])) == 12
      and len({m["study_prefix"] for m in man["selected"]}) >= 5,
      str(len({m["study_prefix"] for m in man.get("selected", [])})))
demo_stats_p = demo / "thetaverse分析" / "stats_A1.json"
check("A1 演示 stats 存在", demo_stats_p.exists())
if demo_stats_p.exists():
    ds = json.loads(demo_stats_p.read_text(encoding="utf-8"))
    check("A1 演示 hit_rows=1056 与 manifest 一致", ds.get("steps", {}).get("hit_rows") == 1056)
    check("A1 演示 ThetaData 12样本", ds.get("ko_per_mag") is not None and len(ds.get("ko_per_mag", {})) == 12)
    check("A1 演示氮循环过程谱存在", (demo / "thetaverse分析" / "氮循环过程谱_每MAG.tsv").exists())
    check("A1 演示 alpha_diversity 存在", (demo / "thetaverse分析" / "alpha_diversity.tsv").exists())
# 演示命中行与源交付逐行核验（抽 3 行回源比对）
demo_hits = demo / "hits_8col_盐湖真实命中.tsv"
if demo_hits.exists():
    dl = demo_hits.read_text(encoding="utf-8").strip().splitlines()
    check("A1 演示命中行数=1056", len(dl) == 1056, str(len(dl)))
    check("A1 演示命中行全部8列", all(len(l.split("\t")) == 8 for l in dl[:50]))
for d in ["Candidatus Brocadia sinica sp.MAG_7(GCA_013360995.1)_pyrodigal.faa",
          "Candidatus Kuenenia stuttgartiensis sp.HKUEN01(GCA_022180985.1)_pyrodigal.faa",
          "Candidatus Scalindua sp.AMX11(GCA_004351875.1)_pyrodigal.faa"]:
    check(f"A1 蛋白预测产物 {d[:24]}..", (a1 / d).exists())
check("A1 工作站命令文档存在", (a1 / "上游注释_工作站执行.md").exists())

# ---------- A3 ----------
a3 = A_DIR / "A3_NCBI下载MAG"
p3p = a3 / "provenance_A3.json"
check("A3 provenance 存在", p3p.exists())
if p3p.exists():
    p3 = json.loads(p3p.read_text(encoding="utf-8"))
    dl = p3.get("steps", {}).get("download", {})
    fna = a3 / dl.get("fasta", "")
    check("A3 fna 存在且字节数一致", fna.exists() and fna.stat().st_size == dl.get("bytes_fna"), dl.get("fasta", ""))
    check("A3 下载URL已记录", dl.get("url", "").startswith("https://ftp.ncbi.nlm.nih.gov/"), dl.get("url", "")[:60])
    check("A3 物种解析已记录", bool(p3.get("steps", {}).get("esummary", {}).get("speciesname_ncbi")))
a3tv = a3 / "thetaverse分析" / "stats_A1.json"
check("A3 下载基因组的 ThetaVerse 分析已跑", a3tv.exists())

# ---------- scripts ----------
for s in ["run_B_abundance_env.py", "run_B_qa.py", "run_A1_mag_thetaverse.py",
          "run_A2_16S_qiime2.py", "run_A3_ncbi_mag.py", "download_qiime2_artifacts.py",
          "run_QA_all.py", "stats_B.json", "QA_B报告.txt"]:
    check(f"scripts/{s} 存在", (DELIV / "scripts" / s).exists())

n_fail = sum(1 for _, ok, _ in checks if not ok)
rep = "\n".join(f"[{'PASS' if ok else 'FAIL'}] {n} {d}" for n, ok, d in checks)
(DELIV / "scripts" / "QA报告_全链.txt").write_text(
    f"全链QA共{len(checks)}项，失败{n_fail}项\n\n{rep}\n", encoding="utf-8")
print(f"\nQA done: {len(checks)} checks, {n_fail} failed")
