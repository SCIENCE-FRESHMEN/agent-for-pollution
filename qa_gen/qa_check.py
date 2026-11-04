# -*- coding: utf-8 -*-
"""程序化QA：文本溢出估算 + 越界 + 文本框重叠。"""
import sys
from pptx import Presentation
from pptx.util import Emu

sys.stdout.reconfigure(encoding='utf-8')
PATH = r"C:\Users\25416\Desktop\agent for pollution\文献下载与命题流程_20260928.pptx"
prs = Presentation(PATH)
EMU_IN = 914400.0
SW, SH = prs.slide_width / EMU_IN, prs.slide_height / EMU_IN
print(f"slides={len(prs.slides)}  canvas={SW:.2f}x{SH:.2f}in")

def est_lines(text, w_in, pt):
    # 中文按全宽，ASCII 按半宽估算每行字符数
    if w_in <= 0:
        return 99
    cpl = max(4, w_in / (pt / 144.0))  # 全角字宽≈pt/72in → 0.5*pt/72=pt/144
    lines = 0
    for seg in text.split("\n"):
        width = sum(1.0 if ord(ch) > 0x2E7F else 0.55 for ch in seg)
        lines += max(1, int(width / cpl) + (1 if width % cpl > 0.01 else 0))
    return lines

issues = []
for si, slide in enumerate(prs.slides, 1):
    boxes = []
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        tf = sh.text_frame
        text = "\n".join(p.text for p in tf.paragraphs).strip()
        if not text:
            continue
        x, y = sh.left / EMU_IN, sh.top / EMU_IN
        w, h = sh.width / EMU_IN, sh.height / EMU_IN
        sizes = [r.font.size.pt for p in tf.paragraphs for r in p.runs if r.font.size]
        pt = max(sizes) if sizes else 18
        # 行数与所需高度（行高≈1.35倍）
        need = est_lines(text, w - 0.1, pt) * pt * 1.38 / 72.0
        if need > h + 0.12:
            issues.append(f"S{si} 溢出? '{text[:18]}…' 需~{need:.2f}in 高{h:.2f}in @{pt:.0f}pt w{w:.2f}")
        if x < -0.05 or y < -0.05 or x + w > SW + 0.05 or y + h > SH + 0.05:
            issues.append(f"S{si} 越界: '{text[:15]}…' ({x:.2f},{y:.2f},{w:.2f},{h:.2f})")
        boxes.append((x, y, w, h, text[:12]))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
            oy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            if ox > 0.12 and oy > 0.12:
                issues.append(f"S{si} 重叠: '{a[4]}' × '{b[4]}' ({ox:.2f}x{oy:.2f}in)")
print("issues:", len(issues))
for i in issues:
    print(" -", i)
