# -*- coding: utf-8 -*-
"""一次性生成 revised 版管线脚本：基于 10-20 交付脚本做最小补丁（external 断裂适配 + 输出重定向）。"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OLD = Path(r"C:\Users\25416\Desktop\agent for pollution\task\交付_剩余任务_20261020\scripts")
NEW = Path(__file__).resolve().parent
OLD_A2 = OLD / "run_A2_16S_qiime2.py"

NEW_GENE_CALL = '''def gene_call(fasta: Path, workdir: Path) -> dict:
    from gene_caller_adapter import call_genes

    prefix = workdir / (fasta.stem + "_pyrodigal")
    faa = Path(str(prefix) + ".faa")
    genes_by_contig, n_records, caller_desc = call_genes(str(fasta), meta=True)
    lines = []
    n_written = 0
    for contig_id, genes in genes_by_contig.items():
        for gi, gene in enumerate(genes, 1):
            lines.append(f">{contig_id}_{gi}\\n{str(gene.translate()).rstrip('*')}\\n")
            n_written += 1
    faa.write_text("".join(lines), encoding="utf-8")
    log(f"{caller_desc} genes={n_written} -> {faa.name}")

    contigs = read_fasta(fasta)
    genome_len = sum(len(s) for _, s in contigs)
    gc = sum(s.count("G") + s.count("C") + s.count("g") + s.count("c") for _, s in contigs)
    proteins = read_fasta(faa)
    gene_len = sum(len(s) for _, s in proteins) * 3
    return {
        "fasta": fasta.name,
        "mag_id": fasta.stem,
        "contigs": len(contigs),
        "genome_bp": genome_len,
        "gc_percent": round(100 * gc / max(genome_len, 1), 2),
        "predicted_genes": len(proteins),
        "gene_bp": gene_len,
        "coding_density_percent": round(100 * gene_len / max(genome_len, 1), 2),
        "proteins_faa": str(faa),
        "pyrodigal_version": caller_desc,
        "gene_caller": caller_desc,
    }
'''

# ---- 1. run_A1_revised ----
src = (OLD / "run_A1_mag_thetaverse.py").read_text(encoding="utf-8")
start = src.index("def gene_call(")
end = src.index("def peptide_search(")
patched = src[:start] + NEW_GENE_CALL + "\n\n" + src[end:]
anchor = 'REPO = Path(r"C:\\Users\\25416\\Desktop\\agent for pollution")\nsys.path.insert(0, str(REPO / "ThetaVerse" / "src"))'
patched = patched.replace(anchor, anchor + '\nsys.path.insert(0, str(Path(__file__).resolve().parent))  # revised: adapter 同目录')
(NEW / "run_A1_mag_thetaverse_revised.py").write_text(patched, encoding="utf-8")
print("written run_A1_mag_thetaverse_revised.py")

# ---- 2. run_A2_revised（输出重定向到 revised）----
a2 = OLD_A2.read_text(encoding="utf-8")
a2 = a2.replace(
    'OUTDIR = ART.parent / "thetaverse分析输出"',
    'OUTDIR = Path(__file__).resolve().parent.parent / "B_三场景接入" / "运行演示" / "16s" / "thetaverse分析输出_revised"')
a2 = a2.replace('"""',
                '"""\n[revised 2026-10-23] ThetaVerse 0.3.0 复验版：输入 artifacts 沿用 10-20 交付，输出重定向到本交付夹；逻辑零改动。', 1)
(NEW / "run_A2_16S_revised.py").write_text(a2, encoding="utf-8")
print("written run_A2_16S_revised.py")

# ---- 3. run_A3_revised（指向 revised A1；workdir 默认 revised）----
a3 = (OLD / "run_A3_ncbi_mag.py").read_text(encoding="utf-8")
a3 = a3.replace('run_A1_mag_thetaverse.py', 'run_A1_mag_thetaverse_revised.py')
a3 = a3.replace('run_A1_mag_thetaverse', 'run_A1_mag_thetaverse_revised')
(NEW / "run_A3_ncbi_mag_revised.py").write_text(a3, encoding="utf-8")
print("written run_A3_ncbi_mag_revised.py")

# ---- 4. analyze_input_revised ----
ENT_SRC = Path(r"C:\Users\25416\Desktop\agent for pollution\task\交付_模拟验证与三场景接入_20261020\scripts\analyze_input.py")
ent = ENT_SRC.read_text(encoding="utf-8")
ent = ent.replace('PREV_SCRIPTS = REPO / "task" / "交付_剩余任务_20261020" / "scripts"',
                  'PREV_SCRIPTS = Path(__file__).resolve().parent  # revised：使用本交付夹的 revised 管线')
ent = ent.replace('"run_A1_mag_thetaverse.py"', '"run_A1_mag_thetaverse_revised.py"')
ent = ent.replace('"run_A2_16S_qiime2.py"', '"run_A2_16S_revised.py"')
ent = ent.replace('"run_A3_ncbi_mag.py"', '"run_A3_ncbi_mag_revised.py"')
ent = ent.replace('def run_16s(inp: str, outdir: Path) -> dict:',
                  'def run_16s(inp: str, outdir: Path) -> dict:')
# 16s outputs 摘要指向 revised 输出
ent = ent.replace('"outputs_dir": str(REPO / "task" / "交付_剩余任务_20261020" / "A_用户输入分析" / "A2_16S_qiime2" / "thetaverse分析输出"),',
                  '"outputs_dir": str(outdir / "thetaverse分析输出_revised"),')
ent = ent.replace('"stats": str(REPO / "task" / "交付_剩余任务_20261020" / "A_用户输入分析" / "A2_16S_qiime2" / "thetaverse分析输出" / "stats_A2.json"),',
                  '"stats": str(outdir / "thetaverse分析输出_revised" / "stats_A2.json"),')
(NEW / "analyze_input_revised.py").write_text(ent, encoding="utf-8")
print("written analyze_input_revised.py")
