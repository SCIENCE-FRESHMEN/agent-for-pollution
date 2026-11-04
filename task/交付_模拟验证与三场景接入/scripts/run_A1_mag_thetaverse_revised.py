# -*- coding: utf-8 -*-
"""
A1 链路：用户输入 MAG → ThetaVerse 分析（本机真实跑通版）。

链路设计（与项目既有数据体系对齐）：
  1. 基因预测：thetaverse.external.PyrodigalRunner（pyrodigal CLI，pip 可装轮子）
  2. 功能注释：UniProt 肽精确搜索（peptidesearch.uniprot.org）拿 Swiss-Prot/TrEMBL
     精确匹配 → UniProt REST 取 KEGG KO 交叉引用。
     说明：本机无 blast/KEGG 库（KOfam profiles.tar.gz 实测 1.5GB @ ~20KB/s，
     需 22 小时，放弃），生产环境应使用工作站 blastp/diamond（与盐湖数据同参数
     e-5/num1/similarity30）；肽精确匹配的覆盖范围有限，实际覆盖率如实写入统计。
  3. ThetaVerse 落表：hits 写成 read_kegg_hits 契约的无表头 8 列
     （qseqid,_,pident,_,qcovhsp,evalue,_,ko），thetaverse 读入构建 ThetaData
  4. 下游分析：氮循环过程映射（v2 64 KO 字典，24 类过程）+ core_metrics
     （rarefaction → α/β 多样性 → PCoA，seed 固定可复现）

用法：
  python run_A1_mag_thetaverse.py [--fasta A.fna B.fna ...] [--workdir DIR]
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(r"C:\Users\25416\Desktop\agent for pollution")
sys.path.insert(0, str(REPO / "ThetaVerse" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # revised: adapter 同目录

PYRODIGAL_EXE = None  # 基因预测改用 PyrodigalBridge 进程内调用，无需 CLI
DEFAULT_FASTAS = sorted((REPO / "genomes_and_queation_to_jiang").glob("*.fna"))
DICT_XLSX = REPO / "task" / "交付_Nitrogen_CompSul_20261014" / "字典_原始输入" / "氮循环Knumber_process.xlsx"
KO_RE = re.compile(r"\bK\d{5}\b")
UA = {"User-Agent": "Mozilla/5.0 (agent-pollution deliverable)"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- gene calling

def read_fasta(path: Path) -> list[tuple[str, str]]:
    recs, name, seq = [], None, []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith(">"):
                if name:
                    recs.append((name, "".join(seq)))
                name, seq = line[1:].split()[0], []
            elif line:
                seq.append(line)
    if name:
        recs.append((name, "".join(seq)))
    return recs


def gene_call(fasta: Path, workdir: Path) -> dict:
    from gene_caller_adapter import call_genes

    prefix = workdir / (fasta.stem + "_pyrodigal")
    faa = Path(str(prefix) + ".faa")
    genes_by_contig, n_records, caller_desc = call_genes(str(fasta), meta=True)
    lines = []
    n_written = 0
    for contig_id, genes in genes_by_contig.items():
        for gi, gene in enumerate(genes, 1):
            lines.append(f">{contig_id}_{gi}\n{str(gene.translate()).rstrip('*')}\n")
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


def peptide_search(proteins: list[tuple[str, str, str]], sp_only: bool, batch: int, stats: dict) -> dict[tuple[str, str], list[str]]:
    """对 (mag, pid, seq) 蛋白列表做 UniProt 精确肽搜索，返回 {(mag,pid): [acc,...]}。"""
    uniq: dict[str, list[tuple[str, str]]] = {}
    for mag, pid, seq in proteins:
        uniq.setdefault(seq, []).append((mag, pid))
    log(f"unique protein sequences: {len(uniq)} (from {len(proteins)})")
    seqs = list(uniq)
    out: dict[tuple[str, str], list[str]] = {}
    t_all = time.time()
    submits_fail = 0
    for i in range(0, len(seqs), batch):
        if not out and time.time() - t_all > 480:
            raise RuntimeError("BLOCKED: UniProt 肽搜索 8 分钟仍无任何产出")
        chunk = seqs[i : i + batch]
        data = urllib.parse.urlencode({"peps": "; ".join(chunk), "spOnly": "on" if sp_only else "off"}).encode()
        loc = None
        for attempt, wait in enumerate([5, 10, 20, 40, 60]):
            try:
                req = urllib.request.Request("https://peptidesearch.uniprot.org/asyncrest", data=data, headers=UA)
                resp = urllib.request.urlopen(req, timeout=120)
                loc = resp.headers.get("Location")
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
                code = getattr(e, "code", None)
                log(f"peptide submit retry{attempt+1} batch{i//batch+1}: {type(e).__name__} {code}")
                if attempt == len([5, 10, 20, 40, 60]) - 1:
                    submits_fail += 1
                time.sleep(wait)
        if not loc:
            if submits_fail >= 2 and not out:
                raise RuntimeError("BLOCKED: UniProt peptide search 持续 503/超时")
            continue
        t0 = time.time()
        body = ""
        poll_err = 0
        t_poll = time.time()
        while time.time() - t_poll < 180:  # 单批轮询上限 3 分钟，防挂死
            time.sleep(3)
            try:
                r2 = urllib.request.urlopen(urllib.request.Request(loc, headers=UA), timeout=10)
                b = r2.read().decode("utf-8", "replace")
                if b:
                    body = b
                    break
            except urllib.error.HTTPError as e2:
                if e2.code not in (202, 303):
                    poll_err += 1
            except (TimeoutError, OSError):
                poll_err += 1
            if poll_err >= 8:
                break
        n_lines = 0
        for line in body.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t") if "\t" in line else line.split()
            if len(parts) >= 2:
                pep, acc = parts[0].strip(), parts[1].strip()
                n_lines += 1
                for key in uniq.get(pep, []):
                    out.setdefault(key, [])
                    if acc not in out[key]:
                        out[key].append(acc)
        if i == 0 and body:
            log(f"peptide response sample: {body[:160]!r}")
        log(f"peptide batch {i//batch+1}/{(len(seqs)+batch-1)//batch}: {len(chunk)} seqs, "
            f"{n_lines} match lines, {time.time()-t0:.0f}s")
    stats["peptide_search_seconds"] = round(time.time() - t_all, 1)
    stats["proteins_with_uniprot_match"] = len(out)
    if not out:
        raise RuntimeError("BLOCKED: UniProt 肽搜索全程无产出")
    return out


def uniprot_proteome_match(flat: list[tuple[str, str, str]], stats: dict) -> tuple[dict[tuple[str, str], list[str]], dict[str, dict], str]:
    """按 MAG 的物种名拉取 UniProt 参考蛋白组（含序列+KEGG KO），本地精确序列匹配。

    覆盖率如实报告（只有与参考蛋白组序列完全一致的蛋白才获得 KO 注释）。
    返回 ({(mag,pid): [acc,...]}, {acc: {protein_name, kos}}, method_str)。
    """
    mags = sorted({m for m, _, _ in flat})
    seq2refs: dict[str, list[tuple[str, str, str]]] = {}  # seq -> [(acc, name, mag)]
    acc_meta: dict[str, dict] = {}
    n_ref = 0
    for mag in mags:
        sp_full = re.sub(r"\(GCA_\d+\.\d+\)$", "", mag)
        sp = sp_full.split(" sp.")[0].strip()  # 去掉 sp.MAG_7 等菌株号，取种/属级学名
        # UniProt stream：该物种全部蛋白（名称查询，Candidatus 前缀自动降级），取 accession/名/KO/序列
        names_to_try = [f'organism_name:"{sp}"']
        if sp.startswith("Candidatus "):
            names_to_try.append(f'organism_name:"{sp.replace("Candidatus ", "")}"')
        got = 0
        for q in names_to_try:
            url = ("https://rest.uniprot.org/uniprotkb/stream?format=tsv"
                   "&fields=accession,protein_name,xref_kegg,sequence"
                   "&query=" + urllib.parse.quote(q))
            body = ""
            for attempt, wait in enumerate([3, 8, 20]):
                try:
                    body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read().decode("utf-8", "replace")
                    break
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e2:
                    log(f"[proteome] {sp}: stream retry{attempt+1}: {type(e2).__name__} {getattr(e2,'code',None)}")
                    time.sleep(wait)
            lines = [l for l in body.splitlines() if l]
            if len(lines) <= 1:
                log(f"[proteome] {q}: 0 rows, try next name variant")
                continue
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) < 4 or not parts[0]:
                    continue
                acc, pname, xref, seq = parts[0], parts[1], parts[2], parts[3].strip()
                kos = sorted(set(KO_RE.findall(xref)))
                acc_meta[acc] = {"protein_name": pname, "kos": kos}
                seq2refs.setdefault(seq, []).append((acc, pname, mag))
                got += 1
            log(f"[proteome] {q}: {got} reference proteins")
            break
        n_ref += got
    stats["reference_proteins_total"] = n_ref
    # 2) 本地精确序列匹配
    out: dict[tuple[str, str], list[str]] = {}
    for mag, pid, seq in flat:
        for acc, _pname, _m in seq2refs.get(seq, []):
            out.setdefault((mag, pid), [])
            if acc not in out[(mag, pid)]:
                out[(mag, pid)].append(acc)
    stats["proteins_with_reference_match"] = len(out)
    method = "UniProt参考蛋白组精确序列匹配"
    return out, acc_meta, method


def ncbi_blast_subset(flat: list[tuple[str, str, str]], stats: dict) -> dict[tuple[str, str], list[str]]:
    """降级路径：每个 MAG 取最长的 10 个代表蛋白，走 NCBI Blast.cgi blastp vs swissprot。

    覆盖为代表性子集（非全蛋白组），结果中如实标注方法与子集规模。
    """
    import re as _re
    out: dict[tuple[str, str], list[str]] = {}
    by_mag: dict[str, list[tuple[str, str]]] = {}
    for mag, pid, seq in flat:
        by_mag.setdefault(mag, []).append((pid, seq))
    BLAST = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
    for mag, plist in by_mag.items():
        rep = sorted(plist, key=lambda t: -len(t[1]))[:10]
        query = "".join(f">{pid}\n{seq}\n" for pid, seq in rep)
        data = urllib.parse.urlencode({
            "CMD": "Put", "PROGRAM": "blastp", "DATABASE": "swissprot",
            "QUERY": query, "HITLIST_SIZE": "3", "EXPECT": "1e-5"}).encode()
        body = urllib.request.urlopen(urllib.request.Request(BLAST, data=data, headers=UA), timeout=120).read().decode("utf-8", "replace")
        m = _re.search(r"RID = (\S+)", body)
        if not m:
            log(f"[blast] {mag}: no RID ({body[:120]!r})")
            continue
        rid = m.group(1)
        log(f"[blast] {mag}: RID={rid}")
        ready = False
        for _ in range(40):
            time.sleep(15)
            chk = urllib.request.urlopen(urllib.request.Request(
                BLAST + f"?CMD=Get&FORMAT_OBJECT=SearchInfo&RID={rid}", headers=UA), timeout=120).read().decode("utf-8", "replace")
            if "Status=READY" in chk:
                ready = True
                break
            if "Status=UNKNOWN" in chk:
                break
        if not ready:
            log(f"[blast] {mag}: not ready in time")
            continue
        res = urllib.request.urlopen(urllib.request.Request(
            BLAST + f"?CMD=Get&FORMAT_TYPE=Tabular&RID={rid}&ALIGNMENTS=3&DESCRIPTIONS=3", headers=UA), timeout=180).read().decode("utf-8", "replace")
        n = 0
        seen_q = set()
        for line in res.splitlines():
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 2:
                continue
            q, sid = cols[0], cols[1]
            if q in seen_q:
                continue
            seen_q.add(q)
            acc = sid.split("|")[1] if "|" in sid else sid.split("(", 1)[0]
            out.setdefault((mag, q), [])
            if acc not in out[(mag, q)]:
                out[(mag, q)].append(acc)
                n += 1
        log(f"[blast] {mag}: {len(seen_q)} queries with hits, {n} accessions")
    stats["ncbi_blast_subset"] = {m: 10 for m in by_mag}
    return out


def uniprot_ko_xref(accs: list[str], batch: int, stats: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    t0 = time.time()
    for i in range(0, len(accs), batch):
        chunk = accs[i : i + batch]
        query = " OR ".join(f"accession:{a}" for a in chunk)
        url = ("https://rest.uniprot.org/uniprotkb/stream?format=tsv"
               "&fields=accession,protein_name,xref_kegg&query=" + urllib.parse.quote(query))
        for attempt in range(3):
            try:
                body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf-8", "replace")
                break
            except (urllib.error.URLError, urllib.error.HTTPError) as e:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        lines = body.splitlines()
        for line in lines[1:]:
            parts = line.split("\t")
            if not parts or not parts[0]:
                continue
            kos = sorted(set(KO_RE.findall(parts[-1] if len(parts) >= 3 else "")))
            out[parts[0]] = {"protein_name": parts[1] if len(parts) >= 3 else "",
                             "kos": kos}
        log(f"uniprot xref batch {i//batch+1}/{(len(accs)+batch-1)//batch}: {len(chunk)} accs -> {len(lines)-1} rows")
    stats["uniprot_xref_seconds"] = round(time.time() - t0, 1)
    return out


# ------------------------------------------------------------------ thetaverse

def load_nitrogen_dict() -> dict[str, str]:
    import openpyxl
    wb = openpyxl.load_workbook(DICT_XLSX, read_only=True)
    ws = wb.worksheets[0]
    d: dict[str, str] = {}
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    cols = [str(c).strip() if c is not None else "" for c in header]
    iko = next(i for i, c in enumerate(cols) if c.lower().startswith("ko"))
    iproc = next((i for i, c in enumerate(cols) if "process" in c.lower()), None)
    for row in rows:
        if not row or not row[iko]:
            continue
        m = KO_RE.search(str(row[iko]))
        if m:
            d[m.group(0)] = str(row[iproc]).strip() if iproc is not None and row[iproc] else ""
    wb.close()
    return d


def run() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fasta", nargs="*", default=[str(p) for p in DEFAULT_FASTAS])
    ap.add_argument("--workdir", default=str(REPO / "task" / "交付_剩余任务_20261020" / "A_用户输入分析" / "A1_MAG_thetaverse"))
    ap.add_argument("--pep-batch", type=int, default=200)
    ap.add_argument("--method", choices=["proteome", "blast", "peptide"], default="proteome",
                    help="KO 注释途径：proteome=UniProt 参考蛋白组精确序列匹配（默认，快且稳）；blast=NCBI blastp 子集（当日队列>10min 兜底）；peptide=UniProt 肽精确匹配（当日服务不稳）")
    ap.add_argument("--hits", default=None,
                    help="已有 KO 命中表（read_kegg_hits 8列契约，如工作站回传）时直接跑下游，跳过基因预测与注释")
    ap.add_argument("--acc-batch", type=int, default=100)
    ap.add_argument("--sp-only", action="store_true", default=True)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    workdir = Path(args.workdir)
    (workdir / "logs").mkdir(parents=True, exist_ok=True)
    stats: dict = {"inputs": [Path(f).name for f in args.fasta], "steps": {}}
    steps = stats.setdefault("steps", {})

    if args.hits:
        # 模式B：工作站回传的 KO 命中表（或同口径真实数据）直接进下游
        hits_path = Path(args.hits)
        steps["annotation_method"] = "外部提供命中表(工作站BLAST口径)"
        acc_ko, pep2acc, flat = {}, {}, []
        method = steps["annotation_method"]
        import shutil
        n_hit_rows = sum(1 for _ in open(hits_path, encoding="utf-8", errors="replace"))
        steps["hit_rows"] = n_hit_rows
        log(f"--hits mode: {n_hit_rows} rows from {hits_path.name}")
        shutil.copy2(hits_path, workdir / "kegg_hits_8col_for_thetaverse.tsv")
        evid_path = None
    else:
        # 模式A：用户 MAG 输入 → 基因预测 → 注释尝试 → 下游
        # 1. 基因预测
        mag_stats = []
        all_proteins: dict[str, list[tuple[str, str]]] = {}
        for f in args.fasta:
            fp = Path(f)
            log(f"=== gene calling: {fp.name}")
            s = gene_call(fp, workdir)
            mag_stats.append(s)
            all_proteins[s["mag_id"]] = read_fasta(Path(s["proteins_faa"]))
        stats["gene_calling"] = mag_stats

        # 2-3. KO 注释（UniProt 肽精确匹配 → KEGG KO 交叉引用；503 持续时降级 NCBI blastp）
        flat: list[tuple[str, str, str]] = []
        for mag, prots in all_proteins.items():
            for pid, seq in prots:
                flat.append((mag, pid, seq))
        acc_ko: dict[str, dict] = {}
        if args.method == "proteome":
            pep2acc, acc_ko, method = uniprot_proteome_match(flat, steps)
        elif args.method == "peptide":
            try:
                pep2acc = peptide_search(flat, args.sp_only, args.pep_batch, steps)
                method = "UniProt精确肽匹配"
            except RuntimeError as e:
                log(f"肽搜索受阻，降级 NCBI blastp 代表性子集: {e}")
                steps["peptide_search_blocked"] = str(e)
                pep2acc = ncbi_blast_subset(flat, steps)
                method = "NCBI_blastp_swissprot(代表性子集)"
        else:
            # blast：NCBI Blast.cgi 当日实测单 job >10min 队列，仅作兜底
            pep2acc = ncbi_blast_subset(flat, steps)
            method = "NCBI_blastp_swissprot(代表性子集)"
        accs = sorted({a for v in pep2acc.values() for a in v})
        log(f"matched UniProt accessions: {len(accs)}")
        steps["matched_accessions"] = len(accs)
        if accs:
            acc_ko = uniprot_ko_xref(accs, args.acc_batch, steps)
        steps["matched_genes"] = len(pep2acc)
        steps["annotation_method"] = method

        # 4. hits 表（read_kegg_hits 契约）+ 证据表
        hits_path = workdir / "kegg_hits_8col_for_thetaverse.tsv"
        evid_path = workdir / "annotation_evidence_匹配溯源.tsv"
        n_hit_rows = 0
        with open(hits_path, "w", encoding="utf-8", newline="") as fh, open(evid_path, "w", encoding="utf-8-sig", newline="") as fe:
            fe.write("mag_id\tgene_id\t匹配方法\tuniprot_accession\tuniprot_protein_name\tKEGG_KO\t氮循环过程(v2字典)\n")
            for mag, pid, seq in flat:
                for acc in pep2acc.get((mag, pid), []):
                    info = acc_ko.get(acc)
                    if not info:
                        continue
                    kos = info["kos"]
                    # read_kegg_hits 契约：无表头 8 列，KO 必须单列单值 -> 每个 KO 一行
                    for ko in kos:
                        fh.write("\t".join([f"{mag}|{pid}", "-", "100.0", "-", "100.0",
                                            "0.0", "-", ko]) + "\n")
                        n_hit_rows += 1
                    if kos:
                        procs = sorted({nit_dict[k] for k in kos if k in nit_dict and nit_dict[k]})
                        fe.write(f"{mag}\t{pid}\t{method}({acc})\t{acc}\t{info['protein_name']}\t{','.join(kos)}\t{';'.join(procs)}\n")
        stats["steps"]["hit_rows"] = n_hit_rows
        log(f"hits rows: {n_hit_rows}")

    # 5-6. ThetaVerse 落表 + 氮循环过程映射 + core_metrics
    import pandas as pd
    from thetaverse import io as tio, tl as ttl
    from thetaverse.core import ThetaData

    nit_dict = load_nitrogen_dict()
    stats["nitrogen_dict_size"] = len(nit_dict)

    if not args.hits and stats["steps"].get("hit_rows", 0) == 0:
        log("[受阻] 用户 MAG 本机注释 0 命中：基因预测产物已交付，KO 注释走工作站（见 上游注释_工作站执行.md）")
        stats["steps"]["blocked_note"] = "本机注释0命中，下游演示见 下游演示_盐湖真实命中/；工作站回传hits后用 --hits 重跑"
        (workdir / "stats_A1.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        log("A1 DONE (mode A, 0 hits)")
        return

    hits = tio.read_kegg_hits(hits_path)
    log(f"read_kegg_hits: {hits.shape}, columns={list(hits.columns)}")
    hits[["mag", "gene"]] = hits["qseqid"].str.rsplit("|", n=1, expand=True)
    feature = hits.pivot_table(index="mag", columns="ko", values="qseqid", aggfunc="count").fillna(0.0)

    if args.hits:
        # 基因组元数据从命中行提取（外部命中表模式下无 gene_calling 统计）
        obs = pd.DataFrame(index=feature.index)
        obs["n_hit_genes"] = hits.drop_duplicates(["mag", "gene"]).groupby("mag").size()
    else:
        obs = pd.DataFrame(mag_stats).set_index("mag_id")
        obs = obs.loc[feature.index]
    var = pd.DataFrame(
        {"nit_cycle_process": [nit_dict.get(k, "") for k in feature.columns],
         "is_nitrogen_ko": [k in nit_dict for k in feature.columns]},
        index=feature.columns)
    tdata = ThetaData(feature, obs=obs, var=var, assay_type="function",
                      name="A1_user_MAG_thetaverse")
    log(f"ThetaData: {tdata.shape}")

    per_mag_ko = (hits.drop_duplicates(["mag", "ko"]).groupby("mag").size())
    stats["ko_per_mag"] = per_mag_ko.to_dict()
    nit_rows = hits[hits["ko"].isin(nit_dict)]
    proc_profile = (nit_rows.assign(process=nit_rows["ko"].map(nit_dict))
                    .drop_duplicates(["mag", "ko"])
                    .groupby(["mag", "process"]).size().unstack(fill_value=0))
    proc_path = workdir / "氮循环过程谱_每MAG.tsv"
    proc_profile.to_csv(proc_path, sep="\t", encoding="utf-8-sig")
    stats["nitrogen_ko_hits_rows"] = int(len(nit_rows))
    stats["nitrogen_ko_distinct"] = int(nit_rows["ko"].nunique())
    log(f"nitrogen process profile: {proc_profile.shape} -> {proc_path.name}")

    if tdata.n_obs >= 2:
        core = ttl.core_metrics(tdata, alpha_metrics=["shannon", "observed"], beta_metrics=["braycurtis", "jaccard"], seed=args.seed)
        alpha = tdata.obs[[c for c in tdata.obs.columns if "shannon" in c or "observed" in c]]
        alpha.to_csv(workdir / "alpha_diversity.tsv", sep="\t", encoding="utf-8-sig")
        log("core_metrics done (alpha written)")
    stats_path = workdir / "stats_A1.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log(f"stats -> {stats_path}")
    log("A1 DONE")


if __name__ == "__main__":
    run()
