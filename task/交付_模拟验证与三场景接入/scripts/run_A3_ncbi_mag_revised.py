# -*- coding: utf-8 -*-
"""
A3 链路：用户输入微生物物种注释名称 → NCBI 查找并下载该物种的 MAG → ThetaVerse 分析。

流程：
  1. esearch(db=assembly)：物种名 + latest genbank 过滤 → 组装 uid
  2. esummary：组装登录号、组装名、物种名（含 NCBI 分类学翻译记录）、FTP 路径
  3. 下载 {ftp}/{acc}_{asmname}_genomic.fna.gz → 解压为 FASTA（真实下载，记录
     URL/字节数/MD5/时间）
  4. 调用 A1 全链路脚本对下载基因组做 ThetaVerse 分析（--analyze）

用法：
  python run_A3_ncbi_mag.py --species "Candidatus Scalindua brodae" [--analyze]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(r"C:\Users\25416\Desktop\agent for pollution")
HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (agent-pollution deliverable)"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def get_json(url: str) -> dict:
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="Candidatus Scalindua brodae")
    ap.add_argument("--workdir", default=str(REPO / "task" / "交付_剩余任务_20261020" / "A_用户输入分析" / "A3_NCBI下载MAG"))
    ap.add_argument("--analyze", action="store_true", help="下载后立即跑 A1 ThetaVerse 链路")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    prov: dict = {"input_species_name": args.species, "steps": {}}

    # 1. esearch
    t0 = time.time()
    term = f'{args.species}[organism] AND "latest genbank"[filter]'
    r = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
                 f"db=assembly&term={urllib.parse.quote(term)}&retmode=json&retmax=3")
    uids = r["esearchresult"]["idlist"]
    prov["steps"]["esearch"] = {"term": term, "uids": uids, "count": r["esearchresult"]["count"],
                                "seconds": round(time.time() - t0, 1)}
    log(f"esearch: count={r['esearchresult']['count']} uids={uids}")
    if not uids:
        prov["blocked"] = "NCBI 无该物种的 genbank 组装"
        (workdir / "provenance_A3.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
        log("BLOCKED: no assembly found")
        return

    # 2. esummary
    doc = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
                   f"db=assembly&id={uids[0]}&retmode=json")["result"][uids[0]]
    acc = doc["assemblyaccession"]
    asm = doc["assemblyname"]
    species = doc["speciesname"]
    ftp = doc.get("ftppathgenbank") or doc.get("ftppathrefseq") or doc.get("ftppath_refseq")
    prov["steps"]["esummary"] = {"assemblyaccession": acc, "assemblyname": asm,
                                 "speciesname_ncbi": species, "ftppath": ftp,
                                 "uid": uids[0]}
    log(f"assembly={acc} name={asm} species={species}")
    if not ftp:
        prov["blocked"] = "esummary 无 FTP 路径"
        (workdir / "provenance_A3.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
        log("BLOCKED: no ftp path")
        return

    # 3. 下载 genomic.fna.gz（真实下载，记录 MD5）
    base = ftp.replace("ftp://", "https://")
    fna_gz_url = f"{base}/{acc}_{asm}_genomic.fna.gz"
    gz_path = workdir / f"{acc}_{asm}_genomic.fna.gz"
    t0 = time.time()
    urllib.request.urlretrieve = None  # 显式禁用，统一走 Request
    req = urllib.request.Request(fna_gz_url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as resp, open(gz_path, "wb") as fo:
        fo.write(resp.read())
    raw = gz_path.read_bytes()
    md5 = hashlib.md5(raw).hexdigest()
    fna_path = gz_path.with_suffix("")
    fna_path.write_bytes(gzip.decompress(raw))
    prov["steps"]["download"] = {
        "url": fna_gz_url, "bytes_gz": len(raw), "md5_gz": md5,
        "bytes_fna": fna_path.stat().st_size, "seconds": round(time.time() - t0, 1),
        "fasta": fna_path.name,
    }
    log(f"downloaded {len(raw)} bytes (md5 {md5[:12]}...) in {prov['steps']['download']['seconds']}s")

    (workdir / "provenance_A3.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. 交给 A1 全链路（同进程 importlib 调用：嵌套 CreateProcess 在本环境被拒 WinError 5）
    if args.analyze:
        import importlib.util
        import sys as _sys

        target_out = workdir / "thetaverse分析"
        _sys.argv = ["run_A1_mag_thetaverse_revised.py", "--fasta", str(fna_path),
                     "--workdir", str(target_out)]
        log("launching A1 chain in-process: " + " ".join(_sys.argv[1:]))
        log_fh = open(workdir / "运行日志_A1_经A3触发.txt", "w", encoding="utf-8")
        _stdout_backup = _sys.stdout
        try:
            _sys.stdout = log_fh
            spec = importlib.util.spec_from_file_location("run_A1_mag_thetaverse_revised", HERE / "run_A1_mag_thetaverse_revised.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run()
            rc = 0
        except SystemExit as e:
            rc = e.code or 0
        except Exception as e:
            log_fh.write(f"EXCEPTION: {type(e).__name__}: {e}\n")
            rc = 1
        finally:
            _sys.stdout = _stdout_backup
            log_fh.close()
        log(f"A1 chain exit code: {rc}")


if __name__ == "__main__":
    main()
