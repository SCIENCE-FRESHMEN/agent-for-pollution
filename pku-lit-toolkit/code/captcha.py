# -*- coding: utf-8 -*-
"""滑块拼图验证码求解（部分学校 IdP 使用；求解失败会自动回退手动登录）"""
import io, base64, time, random
import numpy as np
from PIL import Image

def find_gap(img, piece_natural_w):
    """在背景图 30%-62% 高度带内找缺口暗色带左缘（自然像素）。"""
    if img.width < 50 or img.height < 50:
        return None
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w, _ = arr.shape
    band = arr[int(h * 0.30):int(h * 0.62)]
    colmean = band.mean(axis=2).mean(axis=0)   # 先亮度再列均值
    med = np.median(colmean)
    dark = colmean < med - 8
    best, best_score, run_start = None, -1, None
    for x in range(w):
        if dark[x] and run_start is None:
            run_start = x
        elif not dark[x] and run_start is not None:
            runlen = x - run_start
            if runlen >= piece_natural_w * 0.6:
                score = runlen * (med - colmean[run_start:x].mean())
                if run_start > piece_natural_w * 0.5 and score > best_score:
                    best, best_score = run_start, score
            run_start = None
    if best is None:
        gray = arr.mean(axis=2)
        grad = np.abs(np.diff(gray, axis=1)).sum(axis=0)
        lo = int(piece_natural_w * 0.6)
        hi = max(lo + 1, w - piece_natural_w)
        best = int(np.argmax(grad[lo:hi])) + lo
    return int(best)

def drag(p, hbox, dx):
    """拟人化拖动：eased 曲线 + 抖动"""
    sx, sy = hbox["x"] + hbox["w"] / 2, hbox["y"] + hbox["h"] / 2
    p.mouse.move(sx, sy)
    p.mouse.down()
    steps = max(14, int(dx / 3.5))
    for i in range(1, steps + 1):
        t = i / steps
        eased = 3 * t * t - 2 * t * t * t
        p.mouse.move(sx + dx * eased + random.uniform(-0.7, 0.7),
                     sy + random.uniform(-1.2, 1.2))
        time.sleep(random.uniform(0.008, 0.02))
    p.mouse.move(sx + dx + random.uniform(2, 4), sy)
    time.sleep(0.06)
    p.mouse.move(sx + dx, sy)
    time.sleep(0.15)
    p.mouse.up()

CAP_JS = """() => {
    const vis = el => el && el.offsetParent !== null && el.getClientRects().length > 0;
    const box = el => { if (!el) return null; const r = el.getBoundingClientRect();
        return {x: r.x, y: r.y, w: r.width, h: r.height}; };
    let pool = Array.from(document.querySelectorAll('#dialog-box .slider-img-bg'));
    if (!pool.length) pool = Array.from(document.querySelectorAll('.slider-img-bg'));
    for (const bg of pool) {
        if (!vis(bg) || bg.getBoundingClientRect().width < 150) continue;
        const root = bg.closest('.slider-captcha') || bg.parentElement.parentElement;
        return { bgSrc: bg.src, bg: box(bg),
                 mv: box(root.querySelector('.slider-img-move')),
                 hbox: box(root.querySelector('.slider-move-box')),
                 track: box(root.querySelector('.slider-move-bg')) };
    }
    return null;
}"""

def solve_slider_if_present(p, log=print, max_attempts=8):
    """若页面出现 .slider-* 滑块验证码则尝试求解；返回 True=页面已无滑块。"""
    for attempt in range(1, max_attempts + 1):
        data = p.evaluate(CAP_JS)
        if not data or not data.get("bgSrc"):
            return True
        try:
            img = Image.open(io.BytesIO(base64.b64decode(data["bgSrc"].split(",", 1)[1]))).convert("RGB")
        except Exception:
            return True
        if not data.get("hbox") or not data.get("track"):
            return True
        piece_nw = int(round(48 / max(data["bg"]["w"], 1) * img.width))
        gap = find_gap(img, piece_nw)
        if gap is None:
            p.wait_for_timeout(1500)
            continue
        scale = data["bg"]["w"] / img.width
        piece_off = data["mv"]["x"] - data["bg"]["x"] if data.get("mv") else 0
        dx = max(0.0, min(gap * scale - piece_off, data["track"]["w"] - data["hbox"]["w"]))
        log(f"[captcha] 第{attempt}次尝试 gap={gap} dx={dx:.1f}")
        drag(p, data["hbox"], dx)
        p.wait_for_timeout(2500)
        gone = p.evaluate("""() => {
            const vis = el => el && el.offsetParent !== null && el.getClientRects().length > 0;
            let pool = Array.from(document.querySelectorAll('#dialog-box .slider-img-bg'));
            if (!pool.length) pool = Array.from(document.querySelectorAll('.slider-img-bg'));
            for (const bg of pool) if (bg.getBoundingClientRect().width >= 150 && vis(bg)) return false;
            return true;
        }""")
        if gone:
            log("[captcha] 滑块通过")
            return True
        try:
            p.get_by_text("再试一次").first.click(timeout=2500)
        except Exception:
            pass
        p.wait_for_timeout(1800)
    log("[captcha] 滑块多次未通过，转人工")
    return False
