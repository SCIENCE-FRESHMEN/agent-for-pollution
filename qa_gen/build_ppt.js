const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
p.author = "WWBench 题库组";
p.title = "从文献到题库：下载情况与命题流程";

const W = 13.33, H = 7.5, M = 0.5;
const INK = "0A3538", INK2 = "114A4C", BG = "FFFFFF";
const PRIMARY = "0E6E6B", PRIM_DK = "0A4E4C", TINT = "E3F0EE", TINT2 = "8FBDB9";
const ACCENT = "E8871E", TEXT = "1C2B2A", MUTED = "5F7A77", LINE = "D8E5E3", GREY = "C9D6D4";
const F = "Microsoft YaHei";
const src = (s, t) => s.addText(t, { x: M, y: 7.02, w: W - 2 * M, h: 0.32, fontSize: 12, fontFace: F, color: MUTED, margin: 0 });
const kick = (s, t) => s.addText(t, { x: M, y: 0.42, w: 9, h: 0.32, fontSize: 13, bold: true, fontFace: F, color: PRIMARY, charSpacing: 2, margin: 0 });
const title = (s, t) => s.addText(t, { x: M, y: 0.74, w: W - 2 * M, h: 0.62, fontSize: 26, bold: true, fontFace: F, color: TEXT, margin: 0 });

// ---------- S1 封面 ----------
let s = p.addSlide();
s.background = { color: INK };
s.addText("AI 科研智能体评测 · 题库构建复盘", { x: 0.7, y: 1.45, w: 8, h: 0.4, fontSize: 14, bold: true, fontFace: F, color: TINT2, charSpacing: 2, margin: 0 });
s.addText([
  { text: "从 754 篇文献", options: { breakLine: true } },
  { text: "到 17 道评测题" },
], { x: 0.7, y: 1.95, w: 7.8, h: 2.3, fontSize: 46, bold: true, fontFace: F, color: "FFFFFF", lineSpacingMultiple: 1.12, margin: 0 });
s.addText("高盐厌氧氨氧化方向评测题库是怎么做出来的 —— 文献下载情况 × 命题流程", { x: 0.7, y: 4.5, w: 7.6, h: 0.8, fontSize: 15, fontFace: F, color: "B9D4D1", margin: 0 });
s.addText("2026-09-28 · WWBench 题库组", { x: 0.7, y: 6.65, w: 6, h: 0.35, fontSize: 12.5, fontFace: F, color: "7FA5A2", margin: 0 });
[["3,927", "待下载清单（20260926）"], ["754", "OA 全文到库 · 19.2%"], ["17 题 · 19 DOI", "试题产出 · 全部可溯源"]].forEach((c, i) => {
  const y = 1.85 + i * 1.62;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 9.05, y, w: 3.55, h: 1.32, fill: { color: INK2 }, rectRadius: 0.07, line: { type: "none" } });
  s.addText(c[0], { x: 9.35, y: y + 0.16, w: 3.0, h: 0.62, fontSize: i === 2 ? 26 : 30, bold: true, fontFace: F, color: i === 1 ? ACCENT : "FFFFFF", margin: 0 });
  s.addText(c[1], { x: 9.35, y: y + 0.82, w: 3.0, h: 0.35, fontSize: 12.5, fontFace: F, color: "9FC3C0", margin: 0 });
});

// ---------- S2 全景流水线 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "OVERVIEW"); title(s, "全景：一条从清单到题库的流水线");
const steps = [
  ["01", "待下载清单", "主题 × 期刊\n加权筛选", "3,927 篇"],
  ["02", "OA 榨取", "多通道直链\n解析下载", "754 篇 · 19.2%"],
  ["03", "全库分诊", "前三页文本\n加权评分", "251 篇候选"],
  ["04", "证据挖掘", "段落摘要\n+ 精读", "约 25 篇"],
  ["05", "模板化命题", "对齐原库\n句式与评分", "17 题"],
  ["06", "核真验收", "DOI 对照\n原文首页", "100% 在库"],
];
steps.forEach((c, i) => {
  const x = 0.5 + i * 2.06, last = i === 5;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y: 1.75, w: 1.95, h: 3.0, fill: { color: last ? PRIMARY : TINT }, rectRadius: 0.08, line: { type: "none" } });
  const fg = last ? "FFFFFF" : TEXT, fm = last ? "BFE0DD" : MUTED, fn = last ? "FFFFFF" : PRIMARY;
  s.addText(c[0], { x: x + 0.18, y: 1.95, w: 1.0, h: 0.45, fontSize: 20, bold: true, fontFace: F, color: last ? "9FE0D8" : TINT2, margin: 0 });
  s.addText(c[1], { x: x + 0.18, y: 2.48, w: 1.62, h: 0.4, fontSize: 15, bold: true, fontFace: F, color: fg, margin: 0 });
  s.addText(c[2], { x: x + 0.18, y: 2.95, w: 1.62, h: 0.75, fontSize: 12.5, fontFace: F, color: fm, lineSpacingMultiple: 1.15, margin: 0 });
  s.addText(c[3], { x: x + 0.18, y: 3.95, w: 1.62, h: 0.6, fontSize: 14.5, bold: true, fontFace: F, color: last ? "FFD9A8" : PRIM_DK, margin: 0 });
});
s.addText([
  { text: "全程脚本化、可复现、可扩题：", options: { bold: true, color: TEXT } },
  { text: "  qa_gen/ 保存了每一步的脚本与中间产物（triage → fulltext → digest → gen → validate → verify_titles）", options: { color: MUTED } },
], { x: M, y: 5.3, w: W - 2 * M, h: 0.5, fontSize: 13.5, fontFace: F, margin: 0 });
src(s, "数据来源：qa_gen/ 各阶段日志（2026-09-26 ~ 09-27）");

// ---------- S3 下载结果 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "PART 01 · 文献下载"); title(s, "OA 榨取：3,927 篇清单，拿下 754 篇");
s.addText("754", { x: 0.45, y: 1.55, w: 4.4, h: 1.85, fontSize: 96, bold: true, fontFace: F, color: PRIMARY, margin: 0 });
s.addText("篇 PDF 到库 · 占清单 19.2%", { x: 0.5, y: 3.5, w: 4.6, h: 0.45, fontSize: 17, bold: true, fontFace: F, color: TEXT, margin: 0 });
[["580", "全文正文"], ["174", "补充材料 SI"]].forEach((c, i) => {
  const x = 0.5 + i * 2.3;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y: 4.25, w: 2.1, h: 1.05, fill: { color: TINT }, rectRadius: 0.07, line: { type: "none" } });
  s.addText(c[0], { x: x + 0.2, y: 4.37, w: 1.7, h: 0.5, fontSize: 24, bold: true, fontFace: F, color: PRIM_DK, margin: 0 });
  s.addText(c[1], { x: x + 0.2, y: 4.92, w: 1.7, h: 0.3, fontSize: 12.5, fontFace: F, color: MUTED, margin: 0 });
});
s.addText([
  { text: "旧队列 2,790 篇 OA 命中≈0，", options: { bold: true, color: TEXT } },
  { text: "已整队放弃；改用 20260926 新清单（主题聚焦 + OA 友好期刊加权）后命中 19.2%。", options: { color: MUTED } },
], { x: 0.5, y: 5.62, w: 5.6, h: 1.0, fontSize: 13, fontFace: F, lineSpacingMultiple: 1.25, margin: 0 });
// 右半：比例条 + 缺口
s.addText("清单构成与缺口", { x: 6.6, y: 1.6, w: 5.5, h: 0.4, fontSize: 15, bold: true, fontFace: F, color: TEXT, margin: 0 });
s.addText("已到库 754 · 19.2%", { x: 6.6, y: 2.12, w: 2.4, h: 0.3, fontSize: 12.5, bold: true, fontFace: F, color: PRIM_DK, margin: 0 });
s.addShape(p.shapes.RECTANGLE, { x: 6.6, y: 2.48, w: 1.19, h: 0.72, fill: { color: PRIMARY }, line: { type: "none" } });
s.addShape(p.shapes.RECTANGLE, { x: 7.79, y: 2.48, w: 5.04, h: 0.72, fill: { color: GREY }, line: { type: "none" } });
s.addText("3,173 待机构 SSO · 80.8%", { x: 7.95, y: 2.63, w: 4.7, h: 0.4, fontSize: 13.5, bold: true, fontFace: F, color: "3C4A48", margin: 0 });
[["缺口在哪里：", "集中在订阅型大刊 —— Water Research 一家占清单 1,657 篇，OA 命中仅 61 篇。"], ["怎么补：", "等机构 SSO 权限开通后运行 start_missing_20260926.cmd 一键续采；补采脚本与失败清单均已留档。"], ["为什么值得等：", "3,173 篇缺口多为主题高相关订阅刊，补齐后可支撑更大规模的扩题与证据交叉验证。"]].forEach((r, i) => {
  const y = 3.62 + i * 1.02;
  s.addText([
    { text: r[0], options: { bold: true, color: PRIM_DK } },
    { text: r[1], options: { color: MUTED } },
  ], { x: 6.6, y, w: 6.2, h: 0.95, fontSize: 13, fontFace: F, lineSpacingMultiple: 1.22, margin: 0 });
});
src(s, "来源：文献下载总览_20260926.xlsx；lit_workspace/final_stats.txt（queued=3927，pdf=754，fulltext=580，si=174，todo=3173）");

// ---------- S4 期刊分化 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "PART 01 · 文献下载"); title(s, "下载率由期刊 OA 政策决定，而非主题");
s.addChart(p.charts.BAR, [{
  name: "OA 命中率",
  labels: ["Water Research  1657→61", "Bioresource Technology  80→0", "Environ. Sci. Technol.  185→110", "Scientific Reports  158→158", "npj Clean Water  29→29", "mSystems  23→22", "Nature Communications  19→19"],
  values: [3.7, 0, 59.5, 100, 100, 95.7, 100],
}], {
  x: M, y: 1.6, w: 8.3, h: 4.9, barDir: "bar",
  chartColors: [PRIMARY], varyColors: true,
  chartArea: { fill: { color: "FFFFFF" } },
  catAxisLabelColor: TEXT, catAxisLabelFontSize: 12.5, catAxisLabelFontFace: F,
  valAxisLabelColor: MUTED, valAxisLabelFontSize: 12, valAxisLabelFontFace: F,
  valAxisMaxVal: 100, valAxisMinVal: 0,
  valGridLine: { color: "E7EFEE", size: 0.5 }, catGridLine: { style: "none" },
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT, dataLabelFontSize: 12, dataLabelFontFace: F, dataLabelFormatCode: '0.#"%"',
  showLegend: false, showTitle: false,
});
[["100% 命中", "全 OA 刊一网打尽：Sci. Rep.、npj Clean Water、Nat. Commun.、mSystems（22/23）"], ["3.7%", "Water Research 1,657 篇仅 61 篇 OA —— 全库最大缺口来源"], ["0 / 80", "Bioresource Technology 全军覆没：订阅墙，只能等 SSO"]].forEach((c, i) => {
  const y = 1.75 + i * 1.62;
  s.addText(c[0], { x: 9.15, y, w: 3.6, h: 0.5, fontSize: 20, bold: true, fontFace: F, color: i === 0 ? PRIM_DK : ACCENT, margin: 0 });
  s.addText(c[1], { x: 9.15, y: y + 0.52, w: 3.6, h: 1.0, fontSize: 12.5, fontFace: F, color: MUTED, lineSpacingMultiple: 1.2, margin: 0 });
});
src(s, "来源：lit_workspace/final_stats.txt（2026-09-26，按期刊统计）· 柱标签格式：在清单篇数 → 已下载篇数");

// ---------- S5 库的组织 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "PART 01 · 文献下载"); title(s, "到库文献：以 DOI 为主键的机器可回溯语料库");
[["oa_pdf_20260926／ — 754 个 PDF", "全部以 DOI 命名（如 10.1016_j.cej.2022.136712.pdf），题库引用可一键回查原文"],
 ["bench_pdfs_fulltext／ — 581 个文件", "面向评测的正文子集，与下载清单、状态总览表联动管理"],
 ["双轨完整性体检", "页数 / 体积 / 可解析性校验 + 解析缓存去重，损坏与失败逐条留档、支持重下"],
 ["SI 与正文同权", "174 份补充材料带关键附表（如 PI/SI 反应器对照、批次试验矩阵），是命题证据的一部分"]].forEach((r, i) => {
  const y = 1.7 + i * 1.24;
  if (i) s.addShape(p.shapes.LINE, { x: 0.5, y: y - 0.14, w: 6.9, h: 0, line: { color: LINE, width: 1 } });
  s.addShape(p.shapes.OVAL, { x: 0.5, y: y + 0.09, w: 0.14, h: 0.14, fill: { color: PRIMARY }, line: { type: "none" } });
  s.addText(r[0], { x: 0.82, y: y - 0.04, w: 6.6, h: 0.42, fontSize: 15.5, bold: true, fontFace: F, color: TEXT, margin: 0 });
  s.addText(r[1], { x: 0.82, y: y + 0.42, w: 6.6, h: 0.62, fontSize: 12.5, fontFace: F, color: MUTED, lineSpacingMultiple: 1.2, margin: 0 });
});
s.addChart(p.charts.DOUGHNUT, [{ name: "构成", labels: ["全文正文 580", "补充材料 SI 174"], values: [580, 174] }], {
  x: 7.9, y: 1.75, w: 4.7, h: 4.5, holeSize: 62,
  chartColors: [PRIMARY, TINT2],
  showPercent: true, dataLabelColor: "FFFFFF", dataLabelFontSize: 13, dataLabelFontFace: F,
  showLegend: true, legendPos: "b", legendFontSize: 12.5, legendFontFace: F, legendColor: TEXT,
  showTitle: false,
});
s.addText("754 篇构成", { x: 8.7, y: 3.62, w: 3.1, h: 0.5, fontSize: 15, bold: true, fontFace: F, color: TEXT, align: "center", margin: 0 });
src(s, "来源：lit_workspace/literature/ 目录盘点（2026-09-28）");

// ---------- S6 分段页 ----------
s = p.addSlide(); s.background = { color: INK };
s.addText("02", { x: 0.7, y: 1.15, w: 4, h: 1.5, fontSize: 80, bold: true, fontFace: F, color: "2A6B68", margin: 0 });
s.addText("题是怎么造出来的", { x: 0.7, y: 2.75, w: 11, h: 0.95, fontSize: 40, bold: true, fontFace: F, color: "FFFFFF", margin: 0 });
s.addText("六步流水线：每一步都有脚本与中间产物，可复现、可扩题", { x: 0.7, y: 3.85, w: 11, h: 0.5, fontSize: 15, fontFace: F, color: "B9D4D1", margin: 0 });
s.addText("01 对齐评测框架    ·    02 全库分诊    ·    03 全文抽取    ·    04 证据挖掘    ·    05 模板化命题    ·    06 核真验收",
  { x: 0.7, y: 5.5, w: 12, h: 0.45, fontSize: 13.5, bold: true, fontFace: F, color: TINT2, margin: 0 });

// ---------- S7 对齐评测框架 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "PART 02 · 命题流程"); title(s, "第一关：把评分器拆开看");
[["字段逐字对齐", "原库 52 题的 12 列表头原样沿用，新题题号接续 q-201 ~ q-217"],
 ["rubric_6dims 评分", "六维各 0–2 分：准确 / 完整 / 机制 / 工程 / 依据 / 逻辑，另加要点逐条命中"],
 ["要点切分规则", "ideal_keypoints 按「；」切分 → 要点内部禁用该符号，评分器行为决定写法"],
 ["evidence 维引证锚点", "启发式评分以详解中的 DOI / 期刊+年份 为锚 → 每题详解必须嵌真实引证"]].forEach((r, i) => {
  const y = 1.72 + i * 1.24;
  if (i) s.addShape(p.shapes.LINE, { x: 0.5, y: y - 0.14, w: 7.0, h: 0, line: { color: LINE, width: 1 } });
  s.addText(`0${i + 1}`, { x: 0.5, y: y + 0.02, w: 0.62, h: 0.5, fontSize: 17, bold: true, fontFace: F, color: TINT2, margin: 0 });
  s.addText(r[0], { x: 1.18, y, w: 6.3, h: 0.42, fontSize: 15.5, bold: true, fontFace: F, color: TEXT, margin: 0 });
  s.addText(r[1], { x: 1.18, y: y + 0.44, w: 6.3, h: 0.6, fontSize: 12.5, fontFace: F, color: MUTED, lineSpacingMultiple: 1.2, margin: 0 });
});
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 8.1, y: 1.72, w: 4.7, h: 4.55, fill: { color: TINT }, rectRadius: 0.09, line: { type: "none" } });
s.addText("评分器看到什么", { x: 8.4, y: 1.98, w: 4.1, h: 0.42, fontSize: 15, bold: true, fontFace: F, color: PRIM_DK, margin: 0 });
s.addText([
  { text: "keypoint_hits [true/false …]", options: { breakLine: true, bold: true, color: TEXT } },
  { text: "→ 要点逐条判定，与要点串等长", options: { breakLine: true, color: MUTED } },
  { text: " ", options: { breakLine: true } },
  { text: "dim_scores {0|1|2} × 6 维", options: { breakLine: true, bold: true, color: TEXT } },
  { text: "→ 0 缺失 / 1 部分 / 2 达标", options: { breakLine: true, color: MUTED } },
  { text: " ", options: { breakLine: true } },
  { text: "refused / overall", options: { breakLine: true, bold: true, color: TEXT } },
  { text: "→ 拒答直接记 0 分", options: { color: MUTED } },
], { x: 8.4, y: 2.5, w: 4.15, h: 3.0, fontSize: 13, fontFace: F, lineSpacingMultiple: 1.18, margin: 0 });
s.addText("出处：WWBench_v1.0/harness（prompts.py · dataset.py · graders.py）逐行核对", { x: 8.4, y: 5.62, w: 4.15, h: 0.6, fontSize: 12, fontFace: F, color: MUTED, lineSpacingMultiple: 1.2, margin: 0 });
src(s, "来源：WWBench_v1.0 harness 源码 + 原题库「Wastewater biological treatment questions.csv」");

// ---------- S8 证据挖掘 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "PART 02 · 命题流程"); title(s, "证据挖掘：从 754 篇到约 25 篇的漏斗");
const fun = [["754", "全库 PDF\n逐篇前三页文本抽取"], ["251", "候选\nanammox × 盐度 × 溶质加权"], ["155 KB", "段落级摘要库\n盐度证据结构化"], ["~25", "核心文献精读\n逐题锚定"]];
fun.forEach((c, i) => {
  const x = 0.5 + i * 3.24;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y: 1.62, w: 2.9, h: 1.42, fill: { color: TINT }, rectRadius: 0.08, line: { type: "none" } });
  s.addText(c[0], { x: x + 0.2, y: 1.74, w: 2.5, h: 0.48, fontSize: 22, bold: true, fontFace: F, color: PRIM_DK, margin: 0 });
  s.addText(c[1], { x: x + 0.2, y: 2.26, w: 2.55, h: 0.7, fontSize: 11.5, fontFace: F, color: MUTED, lineSpacingMultiple: 1.12, margin: 0 });
  if (i < 3) s.addText("→", { x: x + 2.92, y: 2.08, w: 0.34, h: 0.5, fontSize: 18, bold: true, fontFace: F, color: TINT2, align: "center", margin: 0 });
});
const rows = [
  ["锚点文献（DOI）", "为命题贡献的核心事实", "引用"],
  ["10.1021/acs.est.2c01104", "梯度 vs 急性提盐反应器对照；谷氨酸批次试验", "9 题"],
  ["10.1021/acs.est.4c01417", "Jettenia 膜重塑 vs Scalindua salt-in 策略对比", "3 题"],
  ["10.1038/s41396-021-01031-8", "Scalindua 维持能 4.3 kJ、产率随盐度反升", "3 题"],
  ["10.1038/s41396-020-00850-5", "糖原→海藻糖内源轴（饥饿预调理基础）", "3 题"],
  ["10.1128/mbio.00092-22 等", "Mg2+/K+ 串扰；EPS 阳离子交换毒性", "3 题"],
];
rows.forEach((r, i) => {
  const y = 3.42 + i * 0.62;
  if (i) s.addShape(p.shapes.LINE, { x: 0.5, y: y - 0.05, w: 12.33, h: 0, line: { color: LINE, width: 1 } });
  const bold = i === 0;
  s.addText(r[0], { x: 0.5, y, w: 4.15, h: 0.5, fontSize: 12.5, bold, fontFace: F, color: bold ? MUTED : TEXT, margin: 0 });
  s.addText(r[1], { x: 4.75, y, w: 6.7, h: 0.5, fontSize: 12.5, bold, fontFace: F, color: bold ? MUTED : TEXT, margin: 0 });
  s.addText(r[2], { x: 11.55, y, w: 1.28, h: 0.5, fontSize: 12.5, bold: true, fontFace: F, color: bold ? MUTED : PRIMARY, margin: 0 });
});
src(s, "来源：qa_gen/triage.json、digest_core.txt（共精读 25 篇，此处列前 5 个锚点）");

// ---------- S9 产出 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "PART 02 · 命题流程"); title(s, "产出：17 道题，全部为三步作答结构");
s.addChart(p.charts.BAR, [{
  name: "题量",
  labels: ["机理分析 M", "环境工程 E", "总体耐盐化 T1", "场景推理 T10", "菌株选择 T5", "培养基设计 T7"],
  values: [8, 3, 2, 2, 1, 1],
}], {
  x: M, y: 1.7, w: 6.4, h: 4.6, barDir: "col",
  chartColors: [ACCENT, PRIMARY, PRIMARY, PRIMARY, PRIMARY, PRIMARY], varyColors: true,
  chartArea: { fill: { color: "FFFFFF" } },
  catAxisLabelColor: TEXT, catAxisLabelFontSize: 12, catAxisLabelFontFace: F,
  valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT, dataLabelFontSize: 13, dataLabelFontFace: F,
  showLegend: false, showTitle: false, barGapWidthPct: 45,
});
[["复杂 13 · 中等 4", "难度分布：以复杂推理为主，中等题作能力基线"], ["微生物调控 8 · 环境工程 5 · 高盐胁迫 4", "主题分布：覆盖机理、工程与胁迫三条主线"]].forEach((c, i) => {
  const x = 7.25 + i * 2.85;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y: 1.7, w: 2.7, h: 1.5, fill: { color: TINT }, rectRadius: 0.08, line: { type: "none" } });
  s.addText(c[0], { x: x + 0.18, y: 1.84, w: 2.36, h: 0.72, fontSize: 13.5, bold: true, fontFace: F, color: PRIM_DK, lineSpacingMultiple: 1.1, margin: 0 });
  s.addText(c[1], { x: x + 0.18, y: 2.56, w: 2.36, h: 0.6, fontSize: 10.5, fontFace: F, color: MUTED, lineSpacingMultiple: 1.12, margin: 0 });
});
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 7.25, y: 3.45, w: 5.55, h: 2.0, fill: { color: "F4F9F8" }, rectRadius: 0.08, line: { color: LINE, width: 1 } });
s.addText("样例 · q-216（T1 梯度计算题）", { x: 7.5, y: 3.62, w: 5.1, h: 0.4, fontSize: 13.5, bold: true, fontFace: F, color: PRIM_DK, margin: 0 });
s.addText("1.5%→4.0%、0.5%/步 ⇒ 5 步 35 天；每梯度进级判据与监测指标；谷氨酸 2 mM 投加时机；性能不恢复的回退方案。锚：10.1021/acs.est.2c01104", { x: 7.5, y: 4.06, w: 5.1, h: 1.25, fontSize: 12.5, fontFace: F, color: TEXT, lineSpacingMultiple: 1.25, margin: 0 });
s.addText("题号接续原库（q-061 ~ q-200 → 自 q-201 起），题干只给场景参数、证据留给作答者推导", { x: 7.25, y: 5.72, w: 5.55, h: 0.75, fontSize: 12, fontFace: F, color: MUTED, lineSpacingMultiple: 1.2, margin: 0 });
src(s, "来源：高盐厌氧氨氧化AI智能体评测试题_20260927.csv（工作区根目录，17 行 × 12 列）");

// ---------- S10 质量关卡 ----------
s = p.addSlide(); s.background = { color: BG };
kick(s, "PART 02 · 命题流程"); title(s, "两轮返工与引用核真：交付即可导入");
[["v1 复盘", "题干把文献证据整段「喂」给作答者 —— 偏离原库风格，难度失真"],
 ["v2 重写", "题干只留场景参数，句式逐一对齐原库 T1 / T5 / T7 / T10 / E 五套模板"],
 ["引用核真", "19 个 DOI 逐一对照 PDF 首页标题：全部真实存在，顺带修正 4 处标题出入"],
 ["机器验收", "表头 12 列逐字一致 · 要点 3–6 条可解析 · 分隔符合规 · DOI 在库率 100%"]].forEach((r, i) => {
  const y = 1.72 + i * 1.26;
  s.addShape(p.shapes.OVAL, { x: 0.5, y: y + 0.03, w: 0.46, h: 0.46, fill: { color: i === 3 ? ACCENT : PRIMARY }, line: { type: "none" } });
  s.addText(String(i + 1), { x: 0.5, y: y + 0.05, w: 0.46, h: 0.42, fontSize: 15, bold: true, fontFace: F, color: "FFFFFF", align: "center", margin: 0 });
  if (i) s.addShape(p.shapes.LINE, { x: 0.73, y: y - 0.32, w: 0, h: 0.35, line: { color: LINE, width: 1.5 } });
  s.addText(r[0], { x: 1.22, y, w: 6.4, h: 0.42, fontSize: 15.5, bold: true, fontFace: F, color: TEXT, margin: 0 });
  s.addText(r[1], { x: 1.22, y: y + 0.44, w: 6.6, h: 0.62, fontSize: 12.5, fontFace: F, color: MUTED, lineSpacingMultiple: 1.2, margin: 0 });
});
s.addText("100%", { x: 8.7, y: 1.95, w: 4.2, h: 1.3, fontSize: 66, bold: true, fontFace: F, color: ACCENT, margin: 0 });
s.addText("19 个引用 DOI 全部在库、可回溯到原文", { x: 8.72, y: 3.32, w: 4.1, h: 0.75, fontSize: 15, bold: true, fontFace: F, color: TEXT, lineSpacingMultiple: 1.2, margin: 0 });
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 8.7, y: 4.35, w: 4.15, h: 1.35, fill: { color: TINT }, rectRadius: 0.08, line: { type: "none" } });
s.addText("39 条引用 · 19 篇唯一文献 · 4 处标题修正", { x: 8.95, y: 4.52, w: 3.7, h: 0.5, fontSize: 13.5, bold: true, fontFace: F, color: PRIM_DK, margin: 0 });
s.addText("核真脚本 verify_titles.py：DOI → PDF 首页标题逐字比对", { x: 8.95, y: 5.06, w: 3.7, h: 0.5, fontSize: 11.5, fontFace: F, color: MUTED, lineSpacingMultiple: 1.15, margin: 0 });
src(s, "来源：qa_gen/validate.py（评分器同逻辑复检）+ verify_titles.py（DOI 核真）");

// ---------- S11 结尾 ----------
s = p.addSlide(); s.background = { color: INK };
s.addText("可复用资产与下一步", { x: 0.7, y: 0.85, w: 11, h: 0.8, fontSize: 34, bold: true, fontFace: F, color: "FFFFFF", margin: 0 });
s.addText("沉淀的资产", { x: 0.7, y: 2.05, w: 5, h: 0.45, fontSize: 15, bold: true, fontFace: F, color: TINT2, margin: 0 });
[["qa_gen/ 全管线脚本", "分诊 → 全文抽取 → 摘要 → 命题 → 验收 → 核真，一条命令可重跑"],
 ["19 篇核心锚点文献清单", "每篇标注可命制考点与已用题目"],
 ["155 KB 结构化证据摘要库", "盐度 × anammox 段落级事实，扩题直接取材"]].forEach((r, i) => {
  const y = 2.6 + i * 1.18;
  s.addShape(p.shapes.OVAL, { x: 0.72, y: y + 0.08, w: 0.13, h: 0.13, fill: { color: "9FE0D8" }, line: { type: "none" } });
  s.addText(r[0], { x: 1.02, y: y - 0.06, w: 5.0, h: 0.4, fontSize: 14.5, bold: true, fontFace: F, color: "FFFFFF", margin: 0 });
  s.addText(r[1], { x: 1.02, y: y + 0.36, w: 5.0, h: 0.62, fontSize: 12, fontFace: F, color: "9FC3C0", lineSpacingMultiple: 1.18, margin: 0 });
});
s.addText("下一步", { x: 7.0, y: 2.05, w: 5, h: 0.45, fontSize: 15, bold: true, fontFace: F, color: TINT2, margin: 0 });
[["3,173 篇缺口补采", "等机构 SSO 开通后运行 start_missing_20260926.cmd 一键续跑"],
 ["并入 WWBench 跑首轮评测", "题库 CSV 已可直接导入 harness，heuristic + LLM judge 双轨"],
 ["按成绩反哺扩题", "弱项维度（如 evidence 维）定向补题、迭代题库 v2"]].forEach((r, i) => {
  const y = 2.6 + i * 1.18;
  s.addText(`0${i + 1}`, { x: 7.0, y: y - 0.02, w: 0.6, h: 0.4, fontSize: 15, bold: true, fontFace: F, color: ACCENT, margin: 0 });
  s.addText(r[0], { x: 7.62, y: y - 0.06, w: 5.1, h: 0.4, fontSize: 14.5, bold: true, fontFace: F, color: "FFFFFF", margin: 0 });
  s.addText(r[1], { x: 7.62, y: y + 0.36, w: 5.1, h: 0.62, fontSize: 12, fontFace: F, color: "9FC3C0", lineSpacingMultiple: 1.18, margin: 0 });
});
s.addText("题库文件：高盐厌氧氨氧化AI智能体评测试题_20260927.csv（工作区根目录）", { x: 0.7, y: 6.7, w: 11, h: 0.4, fontSize: 12.5, fontFace: F, color: "7FA5A2", margin: 0 });

p.writeFile({ fileName: "C:\\Users\\25416\\Desktop\\agent for pollution\\文献下载与命题流程_20260928.pptx" }).then(() => console.log("done"));
