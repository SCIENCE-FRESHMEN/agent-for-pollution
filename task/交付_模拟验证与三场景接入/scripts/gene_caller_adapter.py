# -*- coding: utf-8 -*-
"""
revised 版基因预测适配层（2026-10-23）。

背景：ThetaVerse 更新至 0.3.0 后，thetaverse.external 包导入断裂——
external/_runner.py 等 5 个文件引用 core.exceptions.ExecutableNotFoundError，
该异常在 0.3.0 的 core.exceptions 中已不存在（上游重构 core 未同步 external）。
证据：ImportError 复现 + findstr 全源检索（见复验报告）。

适配策略：优先 thetaverse.external.PyrodigalBridge（0.2.0 行为）；ImportError 时退回
pyrodigal 直连（参数与 PyrodigalBridge.find_genes 完全一致：meta、closed=False、
min_gene=90、translation_table 默认 11），并如实返回调用方描述供 provenance 记录。
"""
import io
import sys
from pathlib import Path

_THETA_SRC = Path(r"C:\Users\25416\Desktop\agent for pollution\ThetaVerse\src")
if str(_THETA_SRC) not in sys.path:
    sys.path.insert(0, str(_THETA_SRC))

_state = {"checked": False, "bridge": None}


def _read_fasta(path):
    recs, name, seq = [], None, []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith(">"):
                if name is not None:
                    recs.append((name, "".join(seq)))
                name, seq = line[1:].split()[0], []
            elif line:
                seq.append(line)
    if name is not None:
        recs.append((name, "".join(seq)))
    return recs


def call_genes(fasta_path: str, meta: bool = True):
    """返回 (genes_by_contig, n_genes, caller_desc)。

    genes_by_contig: {contig_id: pyrodigal Genes 对象}，元素含 begin/end/translate()。
    """
    if not _state["checked"]:
        _state["checked"] = True
        try:
            from thetaverse.external import PyrodigalBridge  # noqa: F401
            _state["bridge"] = PyrodigalBridge()
            print("[adapter] thetaverse.external.PyrodigalBridge 可用")
        except Exception as e:
            _state["bridge"] = None
            print(f"[adapter] thetaverse.external 不可用（{type(e).__name__}: {str(e)[:120]}），退回 pyrodigal 直连")

    bridge = _state["bridge"]
    if bridge is not None:
        res = bridge.find_genes(fasta_path, meta=meta)
        return res.meta["genes_by_contig"], int(res.n_records), \
            f"thetaverse.external.PyrodigalBridge (pyrodigal {bridge.version()}, 进程内)"

    import pyrodigal
    finder = pyrodigal.GeneFinder(meta=meta, closed=False, min_gene=90)
    genes_by_contig = {}
    n_total = 0
    for contig_id, seq in _read_fasta(fasta_path):
        genes = finder.find_genes(seq)
        genes_by_contig[contig_id] = genes
        n_total += len(genes)
    return genes_by_contig, n_total, \
        f"pyrodigal {pyrodigal.__version__} 直连（0.3.0 external 断裂适配，参数与 PyrodigalBridge 一致）"
