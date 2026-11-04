# -*- coding: utf-8 -*-
"""从实际出发 v3：磁盘真实PDF(含PII命名文件抽内部DOI反查核验清单) -> 去已下 -> 剩余三等分。"""
import openpyxl, io, sys, re, random, csv, os
from pathlib import Path
from collections import Counter
from openpyxl.styles import Font, PatternFill, Alignment

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
# 路径均可经环境变量覆盖（见 config.example.env）
ROOT = Path(os.environ.get("LIT_ROOT", r"D:\Compatible_solute_project"))
SRC = os.environ.get("HEN_XLSX",
    r"D:\xwechat_files\wxid_oybpumgljy8b11_7a1e\msg\file\2026-09\non_oa_literature_links_核验(1).xlsx")
OUTDIR = Path(os.environ.get("OUTDIR", r"C:\Users\17965\WorkBuddy\2026-09-16-19-38-28\output"))
OUTDIR.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "logs" / "authorized_browser_download_v2.csv"
def sn(d): return re.sub(r'[<>:"/\\|?*]', "_", d).lower()
doi_pat = re.compile(rb'10\.\d{4,9}/[^\s<>"\'\)]{6,80}')

# ---------- 读核验清单 ----------
wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
ws = wb["Sheet2"]; rows = list(ws.iter_rows(values_only=True))
hdr = [str(h) if h is not None else "" for h in rows[0]]
def col(name):
    for i, h in enumerate(hdr):
        if h == name: return i
    return None
i_doi, i_title = col("DOI"), col("标题")
i_lib, i_rel = col("在文献库"), col("是否相容性溶质相关")
i_cat, i_stress = col("分类_主类别"), col("分类_胁迫标签")
hen_dois, items, order = set(), {}, []
for r in rows[1:]:
    d = str(r[i_doi] or "").strip() if i_doi is not None else ""
    if not d or d.lower() == "none": continue
    sd = sn(d)
    if sd in hen_dois: continue
    hen_dois.add(sd); items[d] = r; order.append(d)
print("核验清单条目:", len(items))

# ---------- 扫描磁盘真实PDF，构建'已下载DOI'集合(含PII反查) ----------
print("扫描磁盘 PDF ...")
downloaded_dois = set(); total_real = 0; bad = 0; pii_in = 0; pii_out = 0
for p in ROOT.rglob("*.pdf"):
    try: sz = p.stat().st_size
    except OSError: continue
    if sz < 1024: bad += 1; continue
    try: head = p.read_bytes()[:5]
    except OSError: bad += 1; continue
    if not head.startswith(b"%PDF"): bad += 1; continue
    total_real += 1
    stem = p.stem.lower()
    if re.match(r'^10\.', stem):                      # DOI命名
        if stem in hen_dois: downloaded_dois.add(stem)
    else:                                             # 非DOI命名(如 ScienceDirect PII)
        m = doi_pat.search(p.read_bytes())
        if m:
            cand = sn(m.group().decode('latin1').rstrip('.;,'))
            if cand in hen_dois: downloaded_dois.add(cand); pii_in += 1
            else: pii_out += 1
print(f"  磁盘真实PDF {total_real} | 坏文件 {bad}")
print(f"  PII命名且内部DOI命中核验清单: {pii_in}(计入已下) | 命中清单外: {pii_out}")
print(f"  核验清单确已下载(磁盘): {len(downloaded_dois)} | 磁盘上不属于本清单的PDF: {total_real - len(downloaded_dois)}")

# ---------- 下载日志(回填失败原因) ----------
attempts, last_status, last_err = {}, {}, {}
if LOG.exists():
    with LOG.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            d = (row.get("DOI") or "").strip(); st = (row.get("状态") or "").strip()
            if not d: continue
            attempts[d] = attempts.get(d, 0) + 1
            if st != "skipped_exists":
                last_status[d] = st; last_err[d] = (row.get("错误原因") or "").strip()
STATUS_LABEL = {"downloaded": "已下载", "failed_no_pdf": "失败-无PDF", "blocked": "失败-无权限",
    "failed_other": "失败-其他", "challenge_unresolved": "失败-验证", "http_error": "失败-HTTP",
    "not_pdf": "失败-非PDF", "exception": "失败-异常"}

# ---------- 判定 ----------
records = []
for d in order:
    r = items[d]; sd = sn(d)
    status = "已下载" if sd in downloaded_dois else (
        STATUS_LABEL.get(last_status.get(d, ""), f"失败-{last_status.get(d,'')}") if last_status.get(d) else "未下载")
    records.append({"DOI": d, "标题": (str(r[i_title])[:120] if i_title is not None else ""),
        "状态": status, "文件名": (sn(d) + ".pdf") if sd in downloaded_dois else "",
        "尝试次数": attempts.get(d, 0), "失败原因": (last_err.get(d, "") if sd not in downloaded_dois else ""),
        "在文献库": (str(r[i_lib]) if i_lib is not None else ""),
        "是否相容性溶质相关": (str(r[i_rel]) if i_rel is not None else ""),
        "分类_主类别": (str(r[i_cat]) if i_cat is not None else ""),
        "分类_胁迫标签": (str(r[i_stress]) if i_stress is not None else ""),
        "下载链接": f"https://doi.org/{d}"})
cnt = Counter(x["状态"] for x in records)
print("状态分布:", cnt.most_common())

# ---------- 总览 + 统计 ----------
def style_header(ws, ncol):
    fill = PatternFill("solid", fgColor="DDEBF7")
    for c in range(1, ncol + 1):
        cell = ws.cell(row=1, column=c); cell.font = Font(bold=True); cell.fill = fill
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
ov = openpyxl.Workbook(); s = ov.active; s.title = "总览"
cols = ["序号", "DOI", "标题", "状态", "文件名", "尝试次数", "失败原因",
        "在文献库", "是否相容性溶质相关", "分类_主类别", "分类_胁迫标签", "下载链接"]
s.append(cols)
for i, x in enumerate(records, 1):
    s.append([i, x["DOI"], x["标题"], x["状态"], x["文件名"], x["尝试次数"], x["失败原因"],
              x["在文献库"], x["是否相容性溶质相关"], x["分类_主类别"], x["分类_胁迫标签"], x["下载链接"]])
style_header(s, len(cols))
for w, c in zip([6, 42, 60, 14, 40, 8, 26, 10, 16, 16, 24, 42], "ABCDEFGHIJKL"):
    s.column_dimensions[c].width = w
st = ov.create_sheet("统计"); st.append(["项目", "数量"])
for k, v in cnt.most_common(): st.append([k, v])
st.append(["—— 合计 ——", len(records)]); st.append([])
st.append(["已下载(磁盘真实PDF)", sum(1 for x in records if x["状态"] == "已下载")])
st.append(["剩余待下载=未下+失败", sum(1 for x in records if x["状态"] != "已下载")])
st.append(["  其中 失败(曾失败过)", sum(1 for x in records if x["状态"].startswith("失败"))])
st.append(["  其中 未下载(从未尝试)", sum(1 for x in records if x["状态"] == "未下载")])
st.append(["磁盘上不属于本清单的PDF(多数为OA文献)", total_real - len(downloaded_dois)])
style_header(st, 2); st.column_dimensions["A"].width = 34; st.column_dimensions["B"].width = 12
ov.save(OUTDIR / "文献下载总览.xlsx"); print("总览 ->", OUTDIR / "文献下载总览.xlsx")

# ---------- 剩余 + 三等分 ----------
remain = [x for x in records if x["状态"] != "已下载"]
print(f"剩余(未下+失败): {len(remain)}")
rem_wb = openpyxl.Workbook(); rs = rem_wb.active; rs.title = "剩余待下载"
rcols = ["序号", "DOI", "标题", "状态", "在文献库", "是否相容性溶质相关",
         "分类_主类别", "分类_胁迫标签", "下载链接", "建议文件名", "历史失败原因"]
rs.append(rcols)
for j, x in enumerate(remain, 1):
    rs.append([j, x["DOI"], x["标题"], x["状态"], x["在文献库"], x["是否相容性溶质相关"],
               x["分类_主类别"], x["分类_胁迫标签"], x["下载链接"], sn(x["DOI"]) + ".pdf", x["失败原因"]])
style_header(rs, len(rcols))
for w, c in zip([6, 42, 60, 14, 10, 16, 16, 24, 42, 42, 30], "ABCDEFGHIJK"):
    rs.column_dimensions[c].width = w
rem_wb.save(OUTDIR / "剩余待下载_汇总.xlsx"); print("剩余汇总 ->", OUTDIR / "剩余待下载_汇总.xlsx")

random.seed(20260917); random.shuffle(remain)
n = len(remain); base, rmd = n // 3, n % 3
sizes = [base + 1] * rmd + [base] * (3 - rmd)
parts, idx = [], 0
for sz in sizes: parts.append(remain[idx:idx + sz]); idx += sz
assert idx == n and len(set(x["DOI"] for x in [y for p in parts for y in p])) == n
print("三份:", [len(p) for p in parts])
pcols = ["序号", "DOI", "标题", "在文献库", "是否相容性溶质相关", "分类_主类别",
         "分类_胁迫标签", "下载链接", "建议文件名", "历史失败原因"]
for i, part in enumerate(parts, 1):
    w = openpyxl.Workbook(); sh = w.active; sh.title = f"第{i}份"
    sh.append(pcols)
    for j, x in enumerate(part, 1):
        sh.append([j, x["DOI"], x["标题"], x["在文献库"], x["是否相容性溶质相关"],
                   x["分类_主类别"], x["分类_胁迫标签"], x["下载链接"], sn(x["DOI"]) + ".pdf", x["失败原因"]])
    style_header(sh, len(pcols))
    for wd, c in zip([6, 42, 60, 10, 16, 16, 24, 42, 42, 30], "ABCDEFGHIJ"):
        sh.column_dimensions[c].width = wd
    w.save(OUTDIR / f"待下载_第{i}份.xlsx"); print(f"第{i}份 -> {len(part)} 篇")
print("DONE")
