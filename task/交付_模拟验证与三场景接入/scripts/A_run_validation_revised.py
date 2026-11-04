# -*- coding: utf-8 -*-
"""A 复验（0.3.0）：同一 mock 基因组与真值，基因预测经适配层，输出指标并与 10-20 版对照。"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE.parent / "A_模拟验证"
OUT.mkdir(parents=True, exist_ok=True)
OLD = Path(r"C:\Users\25416\Desktop\agent for pollution\task\交付_模拟验证与三场景接入_20261020\A_模拟验证")

# 复用 10-20 构造的 mock 基因组/真值/参考库（构造过程不依赖 thetaverse，seed=42 同一套真值）
import shutil
for f in ["mock_genome.fna", "ground_truth.json", "ref_proteome.tsv"]:
    src = OLD / f
    if not (OUT / f).exists():
        shutil.copy2(src, OUT / f)
        print(f"[copy] {f}")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    from gene_caller_adapter import call_genes

    gt = json.loads((OUT / "ground_truth.json").read_text(encoding="utf-8"))
    truth = {g["gene_id"]: g for g in gt["genes"]}

    genes_by_contig, n_pred, caller = call_genes(str(OUT / "mock_genome.fna"), meta=True)
    log(f"{caller} predicted {n_pred}")

    pred, faa = [], []
    for contig_id, genes in genes_by_contig.items():
        for gi, gene in enumerate(genes, 1):
            pid = f"{contig_id}_{gi}"
            prot = str(gene.translate()).rstrip("*")
            pred.append({"pid": pid, "start": int(gene.begin), "end": int(gene.end), "protein": prot})
            faa.append(f">{pid}\n{prot}\n")
    (OUT / "mock_pyrodigal.faa").write_text("".join(faa), encoding="utf-8")

    refs = {}
    for line in (OUT / "ref_proteome.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 4:
            refs[parts[3]] = {"acc": parts[0]}
    ann = {}
    for p in pred:
        hit = refs.get(p["protein"])
        if hit:
            ann[p["pid"]] = hit

    tol = 9
    matched = {}
    for p in pred:
        for gid, g in truth.items():
            if abs(p["start"] - g["start"]) <= tol and abs(p["end"] - g["end"]) <= tol:
                matched[gid] = p["pid"]
                break
    missed = [{"gene_id": gid, "start": g["start"], "end": g["end"],
               "nearby": [p["pid"] for p in pred if abs(p["start"] - g["start"]) <= 80]}
              for gid, g in truth.items() if gid not in matched]

    acc_by_gid = {g["source_acc"]: gid for gid, g in truth.items()}
    correct = wrong = 0
    for p in pred:
        hit = ann.get(p["pid"])
        if not hit:
            continue
        gid = acc_by_gid.get(hit["acc"])
        if gid and abs(p["start"] - truth[gid]["start"]) <= tol:
            correct += 1
        else:
            wrong += 1

    metrics = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "thetaverse_version": "0.3.0（工作树）",
        "gene_caller": caller,
        "predicted": len(pred),
        "V1": {"matched": len(matched), "recall": round(len(matched) / len(truth), 4),
               "precision": round(len(matched) / max(len(pred), 1), 4), "missed": missed},
        "V2": {"ref_db": len(refs), "exact_matched": len(ann), "correct": correct,
               "wrong": wrong, "precision": round(correct / max(len(ann), 1), 4)},
        "V3": "状态不变：KO 真值源三路受阻与本版本无关（UniProt xref 停摆/KOfam 传输瓶颈/KEGG REST 400）",
    }
    (OUT / "validation_metrics_030.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    old = json.loads((OLD / "validation_metrics.json").read_text(encoding="utf-8"))
    cmp_rows = [
        ("预测基因数", old["V2_protein_layer"]["predicted_total"], len(pred)),
        ("V1 召回", old["V1_gene_layer"]["gene_recall"], metrics["V1"]["recall"]),
        ("V1 精确率", old["V1_gene_layer"]["gene_precision"], metrics["V1"]["precision"]),
        ("V2 精确匹配", old["V2_protein_layer"]["exact_matched"], metrics["V2"]["exact_matched"]),
        ("V2 正确", old["V2_protein_layer"]["correct_source"], metrics["V2"]["correct"]),
        ("V2 误配", old["V2_protein_layer"]["wrong_source"], metrics["V2"]["wrong"]),
    ]
    print("\n新旧对照（0.2.0 10-20 vs 0.3.0 今日）:")
    for k, o, n in cmp_rows:
        flag = "" if o == n else "   <-- 变化"
        print(f"  {k:<14} {o} -> {n}{flag}")
    print("\nmetrics -> validation_metrics_030.json")


if __name__ == "__main__":
    main()
