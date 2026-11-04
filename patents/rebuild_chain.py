# -*- coding: utf-8 -*-
"""OCR 完成后的一键重建链（阶段一→阶段二→增量→评测→界面），逐步落盘+打印摘要。
运行前提：ocr_batch.py 已完成（所有 _OCR.txt 就位）。
"""
import os, sys, io, subprocess, json, csv, re, shutil, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = r"C:\Users\25416\Desktop\agent for pollution"
PY = os.path.join(ROOT, ".rc_venv", "Scripts", "python.exe")
PAT = os.path.join(ROOT, "patents")
INC = os.path.join(PAT, "RAG", "产出", "RAG知识库", "env_increment")
ENV = os.path.join(PAT, "RAG", "产出", "环境工程专利")

def run(script, cwd=None):
    t0 = time.time()
    r = subprocess.run([PY, script], capture_output=True, text=True, encoding="utf-8", errors="ignore",
                       cwd=cwd or ROOT)
    out = (r.stdout or "") + (r.stderr or "")
    print(f"\n===== {os.path.basename(script)} ({time.time()-t0:.0f}s, rc={r.returncode}) =====")
    print("\n".join(out.strip().splitlines()[-14:]))
    return r.returncode == 0, out

ok, out1 = run(os.path.join(PAT, "full_rebuild_p1.py"))
assert ok, "阶段一失败"

# ---- 环境重筛结果导出已由 p1 写 env_screen_v2.txt；此处输出候选供人工复核 ----
p = os.path.join(PAT, "analysis", "env_screen_v2.txt")
if os.path.exists(p):
    print("\n===== env_screen_v2（新增 OCR 件的环境候选） =====")
    for line in open(p, encoding="utf-8"):
        if "RapidOCR" in line:
            print("  ", line.strip())

# ---- 语料指针切换：下游老脚本读 v1 文件名 ----
shutil.copy(os.path.join(PAT, "analysis", "compliance_v2.csv"), os.path.join(PAT, "analysis", "compliance.csv"))
recs = json.load(open(os.path.join(PAT, "analysis", "grounding_records_v2.json"), encoding="utf-8"))
json.dump(recs, open(os.path.join(PAT, "analysis", "grounding_records.json", "w" if False else "w"), encoding="utf-8"), ensure_ascii=False) if False else \
    json.dump(recs, open(os.path.join(PAT, "analysis", "grounding_records.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---- 主库 v2 ----
ok, _ = run(os.path.join(PAT, "build_rag_v2.py"))
assert ok, "主库重建失败"

# ---- 配方库 v2（全语料，规则路径）----
run(os.path.join(PAT, "产出", "scripts", "task1_formulation.py"))

# ---- 图谱 v2 ----
run(os.path.join(PAT, "产出", "scripts", "task3_graph.py"))

# ---- 总清单 v2 = 现 v1 清单（环境集合未变则沿用；新增环境件时人工并入后再跑 v2 增量） ----
src_manifest = os.path.join(ENV, "环境工程专利总清单.csv")
if not os.path.exists(os.path.join(ENV, "环境工程专利总清单_v2.csv")):
    shutil.copy(src_manifest, os.path.join(ENV, "环境工程专利总清单_v2.csv"))

# ---- env_increment v2 ----
run(os.path.join(INC, "task2v2_build.py"))
run(os.path.join(INC, "task3_gold_merge.py"))
ok, _ = run(os.path.join(INC, "task3_eval_v2.py"))
if not ok:
    print("WARN: 评测失败，检查 INC 数据文件")

# ---- 可视化界面 ----
run(os.path.join(PAT, "RAG", "产出", "RAG可视化界面", "gen_ui.py"))

print("\n===== 链条完成。新增数字见上方各段摘要 =====")
