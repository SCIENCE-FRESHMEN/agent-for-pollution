# -*- coding: utf-8 -*-
"""
[revised 2026-10-23] ThetaVerse 0.3.0 复验版：输入 artifacts 沿用 10-20 交付，输出重定向到本交付夹；逻辑零改动。
A2 链路：用户输入 16S → qiime2 分析（Windows 本机可跑部分，全真实数据）。

边界（如实声明，均有本地证据）：
  * QIIME 2 框架仅 Linux/macOS conda 发行；`pip install qiime2` 实测 "No matching
    distribution"（2026-10-20）。thetaverse read_qza 需要官方 qiime2 包做视图读取，
    故「qza 直接落表」在本机 [受阻] —— 受阻证据与工作站命令见
    上游命令_工作站执行.md。
  * 本脚本采用等价真实链路：qza 实为 zip 归档（QIIME 2 官方格式），解出其中
    QIIME 2 生成的真实数据载荷（feature-table.biom / taxonomy.tsv / tree.nwk /
    metadata.yaml 含 UUID 与语义类型），经 thetaverse read_biom / read_qza_taxonomy /
    read_newick 落表 → ThetaVerse 下游分析（rarefaction → α/β 多样性 → PCoA）。
    artifact 真伪与 provenance 记录在 stats_A2.json（UUID/SHA-256）。

用法：python run_A2_16S_qiime2.py
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(r"C:\Users\25416\Desktop\agent for pollution")
sys.path.insert(0, str(REPO / "ThetaVerse" / "src"))
ART = REPO / "task" / "交付_剩余任务_20261020" / "A_用户输入分析" / "A2_16S_qiime2" / "artifacts"
PAYLOAD = ART.parent / "qza解包数据载荷"
OUTDIR = Path(__file__).resolve().parent.parent / "B_三场景接入" / "运行演示" / "16s" / "thetaverse分析输出_revised"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


QZA_MEMBERS = {"table.qza": None, "taxonomy.qza": "taxonomy.tsv", "rooted-tree.qza": "tree.nwk"}


def unzip_payloads(stats: dict) -> Path:
    import pandas as pd

    PAYLOAD.mkdir(exist_ok=True)
    for qza, _ in QZA_MEMBERS.items():
        with zipfile.ZipFile(ART / qza) as z:
            names = z.namelist()
            meta_name = next(n for n in names if n.endswith("metadata.yaml"))
            meta = z.read(meta_name).decode("utf-8", "replace")
            uuid = meta.split("uuid:")[1].split("\n")[0].strip()
            stype = meta.split("type:")[1].split("\n")[0].strip("'\"\n ")
            data_files = [n for n in names if ("/data/" in n or n.startswith("data/"))
                          and not n.endswith("/")]
            stats["artifacts"][qza] = {"uuid": uuid, "semantic_type": stype,
                                       "data_files": data_files}
            for n in data_files:
                target = PAYLOAD / n.split("/data/")[-1]
                target.write_bytes(z.read(n))
            log(f"{qza}: uuid={uuid[:13]}.. type={stype} -> {len(data_files)} data files")

    # SHA-256 of each artifact（provenance 证据）
    for qza in QZA_MEMBERS:
        b = (ART / qza).read_bytes()
        stats["artifacts"][qza]["sha256"] = hashlib.sha256(b).hexdigest()
        stats["artifacts"][qza]["bytes"] = len(b)
    return PAYLOAD


def main() -> None:
    import pandas as pd
    from thetaverse import io as tio
    from thetaverse.core import ThetaData
    from thetaverse import tl as ttl

    stats: dict = {"artifacts": {}}
    payload = unzip_payloads(stats)

    # 特征表（QIIME 2 生成的 BIOM）—— read_biom 直接返回 ThetaData
    biom_path = payload / "feature-table.biom"
    tdata = tio.read_biom(biom_path)
    log(f"read_biom -> ThetaData {tdata.shape}")

    # 物种注释（QIIME 2 taxonomy.tsv）
    tax_path = payload / "taxonomy.tsv"
    tax = pd.read_csv(tax_path, sep="\t")
    id_col = tax.columns[0]
    tax = tax.set_index(id_col)
    tax.columns = [f"taxonomy_{c}" for c in tax.columns]
    common = [f for f in tdata.var_names if f in set(tax.index)]
    var = tax.loc[common]
    tdata = ThetaData(pd.DataFrame(tdata.X.toarray() if hasattr(tdata.X, "toarray") else tdata.X,
                                   index=tdata.obs_names, columns=tdata.var_names),
                      obs=tdata.obs.copy(), var=var, assay_type="taxonomy",
                      name="A2_16S_moving_pictures")
    log(f"taxonomy attached: {tdata.shape}, features with taxonomy={len(common)}")

    # 构树文件
    nwk_path = payload / "tree.nwk"
    try:
        tree = tio.read_newick(nwk_path)
        log(f"tree loaded: {type(tree).__name__}")
    except Exception as e:
        log(f"tree load failed (不影响主分析): {e}")

    # 下游分析：rarefaction → α/β 多样性 → PCoA
    OUTDIR.mkdir(parents=True, exist_ok=True)
    core = ttl.core_metrics(tdata, alpha_metrics=["shannon", "observed", "pielou"],
                            beta_metrics=["braycurtis", "jaccard"], seed=7)
    alpha_cols = [c for c in core.obs.columns if c.startswith("core_metrics_alpha")]
    core.obs[alpha_cols].to_csv(OUTDIR / "alpha_diversity.tsv", sep="\t", encoding="utf-8-sig")
    stats["alpha_columns"] = alpha_cols
    stats["thetadata_shape"] = list(tdata.shape)
    stats["provenance_note"] = "qza 内数据载荷为 QIIME 2 官方教程产物原样解包；UUID/SHA-256 见 artifacts"
    log(f"core_metrics done, alpha cols: {alpha_cols}")
    bdiv = [k for k in core.uns.keys()] if hasattr(core.uns, "keys") else []
    stats["uns_keys"] = bdiv
    ordm = list(core.obsm.keys()) if hasattr(core.obsm, "keys") else []
    stats["obsm_keys"] = ordm
    for k in ordm:
        try:
            import numpy as np
            np.savetxt(OUTDIR / f"PCoA_{k}.tsv", core.obsm[k], delimiter="\t",
                       header="\t".join([f"PC{i+1}" for i in range(core.obsm[k].shape[1])]))
        except Exception as e:
            log(f"save {k} failed: {e}")
    log(f"uns={bdiv} obsm={ordm}")

    (OUTDIR / "stats_A2.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log("A2 DONE")


if __name__ == "__main__":
    main()
