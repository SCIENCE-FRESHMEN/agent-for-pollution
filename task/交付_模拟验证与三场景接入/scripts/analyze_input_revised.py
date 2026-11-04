# -*- coding: utf-8 -*-
"""
B：用户输入统一入口（三场景自动路由）。

  python analyze_input.py --input <路径或物种名> [--type auto|16s|mag|taxon] [--outdir DIR]

路由规则（--type auto 时按输入自动判别）：
  *.qza / *.biom / 目录含 *.qza        -> 16s   （封装管线：A2，thetaverse read_biom 下游）
  *.fna / *.fasta / *.fna.gz           -> mag   （封装管线：A1，基因预测→注释→下游）
  其他文本（物种名，如 "Candidatus Scalindua brodae"） -> taxon（NCBI 查找下载 → 转 mag）

封装管线零改动：经 importlib 同进程加载（本环境嵌套 CreateProcess 被沙箱禁止）。
每场景产出 <outdir>/<场景>\运行摘要.json + 管线原生输出，供 Agent 流程（C）结构化消费。
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path


class _Unclosable(io.RawIOBase):
    """不可关闭、不缓冲的字节流：管线模块反复重包 sys.stdout/stderr 也不会互相关闭。"""

    def __init__(self, fd: int):
        self.fd = fd

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:
        os.write(self.fd, b)
        return len(b)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass  # 故意不关


sys.stdout = io.TextIOWrapper(_Unclosable(1), encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(_Unclosable(2), encoding="utf-8", errors="replace")
REPO = Path(r"C:\Users\25416\Desktop\agent for pollution")
PREV_SCRIPTS = Path(__file__).resolve().parent  # revised：使用本交付夹的 revised 管线


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def detect_type(inp: str) -> str:
    low = inp.lower()
    if low.endswith((".qza", ".biom")) or Path(inp).is_dir():
        return "16s"
    if low.endswith((".fna", ".fasta", ".fa", ".fna.gz", ".fasta.gz")):
        return "mag"
    return "taxon"


def run_mag(inp: str, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    fasta = Path(inp)
    if not fasta.exists():
        raise FileNotFoundError(fasta)
    sys.argv = ["run_A1_mag_thetaverse_revised.py", "--fasta", str(fasta), "--workdir", str(outdir / "A1管线输出")]
    mod = load_module(PREV_SCRIPTS / "run_A1_mag_thetaverse_revised.py", "run_a1_mod")
    mod.run()
    return {"scenario": "mag", "input": str(fasta), "pipeline": "A1 (交付_剩余任务_20261020/scripts/run_A1_mag_thetaverse.py)",
            "outputs_dir": str(outdir / "A1管线输出"),
            "stats": str(outdir / "A1管线输出" / "stats_A1.json"),
            "note": "KO 注释生产口径=工作站 blastp（命令见 A1 上游文档）；本机受阻状态见 stats_A1.json 的 steps.blocked_note"}


def run_16s(inp: str, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    mod = load_module(PREV_SCRIPTS / "run_A2_16S_revised.py", "run_a2_mod")
    mod.main()
    return {"scenario": "16s", "input": str(inp), "pipeline": "A2 (交付_剩余任务_20261020/scripts/run_A2_16S_qiime2.py)",
            "outputs_dir": str(outdir / "thetaverse分析输出_revised"),
            "stats": str(outdir / "thetaverse分析输出_revised" / "stats_A2.json"),
            "note": "qza 上游去噪在 QIIME 2 框架（Linux/conda），本机读表+下游已验证"}


def run_taxon(inp: str, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    sys.argv = ["run_A3_ncbi_mag_revised.py", "--species", inp, "--analyze",
                "--workdir", str(outdir / "NCBI下载")]
    mod = load_module(PREV_SCRIPTS / "run_A3_ncbi_mag_revised.py", "run_a3_mod")
    mod.main()
    return {"scenario": "taxon", "input": inp, "pipeline": "A3→A1 (交付_剩余任务_20261020/scripts/run_A3_ncbi_mag.py)",
            "outputs_dir": str(outdir / "NCBI下载"),
            "provenance": str(outdir / "NCBI下载" / "provenance_A3.json"),
            "note": "NCBI 下载全链真实执行；下载后自动转 mag 场景"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="文件路径（.fna/.qza/.biom）或物种名")
    ap.add_argument("--type", choices=["auto", "16s", "mag", "taxon"], default="auto")
    ap.add_argument("--outdir", default=str(Path(__file__).resolve().parent.parent / "B_三场景接入" / "运行演示"))
    args = ap.parse_args()

    sc = args.type if args.type != "auto" else detect_type(args.input)
    log(f"input={args.input!r} -> scenario={sc}")
    outdir = Path(args.outdir) / sc
    t0 = time.time()
    runner = {"mag": run_mag, "16s": run_16s, "taxon": run_taxon}[sc]
    summary = runner(args.input, outdir)
    summary["elapsed_seconds"] = round(time.time() - t0, 1)
    summary["exit"] = "ok"
    sp = outdir / "运行摘要.json"
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"summary -> {sp}")
    log(f"ENTRY DONE ({sc}, {summary['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()
