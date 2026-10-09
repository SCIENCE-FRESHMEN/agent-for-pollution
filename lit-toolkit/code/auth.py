# -*- coding: utf-8 -*-
"""机构登录（CARSI/Shibboleth）：先自动、失败转人工，一次登录全程复用。
用法（supervisor 已封装，一般无需直接运行）：
    python code/auth.py            # 完整登录 + 验证
"""
import io, re, sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import out_utf8, load_config, RunLog, LOGS
out_utf8()
import chrome_ctl
import captcha
from playwright.sync_api import sync_playwright

log = RunLog()
GOLD = "https://www.sciencedirect.com/science/article/pii/S0043135421010265"  # 探测用文章

def entitlement_state(p):
    """返回 (entitled, note)。判据：能免费看全文的出版社页面不会同时出现 Purchase PDF 且无 View PDF。"""
    try:
        p.goto(GOLD, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        pass
    p.wait_for_timeout(5000)
    body = p.evaluate("() => document.body ? document.body.innerText.slice(0,1500) : ''")
    flat = re.sub(r"\s+", " ", body).lower()
    if "are you a robot" in flat or "captcha" in flat:
        return None, "robot-challenge"
    view = "view pdf" in flat
    purchase = "purchase pdf" in flat
    if view and not purchase:
        return True, "View PDF 可用"
    if purchase and not view:
        return False, "Purchase PDF（未登录或未订阅）"
    return None, "无法判断"

def pick_org(p, cfg):
    """id.elsevier.com 的组织选择页：填邮箱 → 选机构"""
    for i in range(25):
        p.wait_for_timeout(1000)
        if "id.elsevier.com" in (p.url or ""):
            break
    p.wait_for_timeout(3500)
    try:
        btn = p.locator("#onetrust-accept-btn-handler")
        if btn.count() >= 1 and btn.is_visible():
            btn.click(timeout=3000)
            p.wait_for_timeout(800)
    except Exception:
        pass
    box = p.locator("input#bdd-email")
    if box.count() == 0:
        box = p.locator("input[name='els_institution']")
    if box.count() == 0:
        raise RuntimeError("找不到组织输入框")
    box.first.click()
    box.first.fill(cfg.get("email") or cfg["institution_en"])
    p.locator("#bdd-els-searchBtn, button:has-text('提交并继续')").first.click(timeout=8000)
    p.wait_for_timeout(4000)
    pat = re.compile(re.escape(cfg["institution_en"]) + "|" + re.escape(cfg["institution_zh"]), re.I)
    for i in range(10):
        loc = p.get_by_text(pat)
        if loc.count() >= 1:
            loc.first.click(timeout=5000)
            log("[auth] 已选择机构:", cfg["institution_zh"])
            return True
        p.wait_for_timeout(1000)
    # 有时邮箱联邦直达，无列表
    log("[auth] 未出现机构列表（可能已直达学校认证页）")
    return True

def idp_form_fill(p, cfg):
    """学校 IdP 登录表单：通用选择器 + 常见占位符，填不上则抛异常转人工"""
    for i in range(35):
        p.wait_for_timeout(1000)
        if "sciencedirect" in (p.url or ""):
            return "sso-direct"
        u = p.url or ""
        if (".edu.cn" in u) or ("idp" in u) or ("sso" in u) or ("iaaa" in u):
            break
    p.wait_for_timeout(3000)
    if "sciencedirect" in (p.url or ""):
        return "sso-direct"
    # 扫码登录则先切账密
    try:
        p.click("#qrToggle", timeout=3000)
        p.wait_for_timeout(1200)
    except Exception:
        pass
    user_sels = ["input#username", "input[name='username']", "input[name='user_name']",
                 "input[name='account']", "input[placeholder*='学号']", "input[placeholder*='工号']",
                 "input[placeholder*='账号']", "input[placeholder*='用户']", "input[type='text']"]
    pwd_sels = ["input#password", "input[name='password']", "input[placeholder*='密码']",
                "input[type='password']"]
    if not str(cfg.get("password", "")).strip():
        raise RuntimeError("config.json 未填密码（有意留空则走人工登录），转人工")
    for su in user_sels:
        for sp in pwd_sels:
            try:
                ub, wb = p.locator(su).first, p.locator(sp).first
                if ub.count() >= 1 and wb.count() >= 1 and ub.is_visible() and wb.is_visible():
                    ub.fill(cfg["username"])
                    wb.fill(cfg["password"])
                    log(f"[auth] 表单已填: {su} / {sp}")
                    for name in ["登 录", "登录", "Login", "login", "Sign in", "登  录"]:
                        try:
                            btn = p.get_by_role("button", name=re.compile("^\\s*" + re.escape(name) + "\\s*$"))
                            if btn.count() >= 1:
                                btn.first.click(timeout=3000)
                                log("[auth] 已点击:", name)
                                return "submitted"
                        except Exception:
                            continue
                    p.keyboard.press("Enter")
                    log("[auth] 已回车提交")
                    return "submitted"
            except Exception:
                continue
    raise RuntimeError("学校登录页表单无法自动填写（界面不识别），转人工")

def auto_flow(p, cfg):
    """Elsevier/ScienceDirect 自动机构登录。成功返回 True；需人工返回 False。"""
    p.goto(GOLD, wait_until="domcontentloaded", timeout=60000)
    p.wait_for_timeout(5000)
    try:
        p.get_by_role("link", name=re.compile("Access through", re.I)).first.click(timeout=10000)
    except Exception as e:
        log("[auth] 找不到机构入口:", type(e).__name__)
        return False
    try:
        pick_org(p, cfg)
    except Exception as e:
        log("[auth] 选机构失败:", repr(e)[:120])
        return False
    try:
        st = idp_form_fill(p, cfg)
    except Exception as e:
        log("[auth]", e)
        return False
    if st == "sso-direct":
        log("[auth] 学校会话仍有效，直接放行")
        return True
    # 等待回跳，途中处理滑块
    for i in range(60):
        p.wait_for_timeout(1000)
        if "sciencedirect" in (p.url or ""):
            break
        if ".edu.cn" in (p.url or ""):
            captcha.solve_slider_if_present(p, log, max_attempts=3)
    p.wait_for_timeout(5000)
    return "sciencedirect" in (p.url or "")

MANUAL_STEPS = """
==================== 需要人工登录一次 ====================
脚本已在专用 Chrome 里打开 ScienceDirect 文章页。请在该浏览器里：
 1. 点击页面上的 “Access through your organization / 机构登录 / Sign in”
 2. 机构检索框输入：{inst_zh}（或 {inst_en}），回车后在列表中点选贵校
 3. 跳到学校统一认证页后，输入账号 {user} 和密码完成登录
    （如有滑块/验证码/短信/扫码 2FA，请按学校要求完成）
 4. 回到 ScienceDirect 页面，看到文章可以阅读全文（出现 View PDF / Download PDF）
 5. 回到本控制台，按回车继续
注：登录一次后浏览器会保留会话，之后无人值守；会话过期脚本会自动叫你再来一次。
=========================================================
"""

def manual_flow(p, cfg):
    print(MANUAL_STEPS.format(inst_zh=cfg["institution_zh"], inst_en=cfg["institution_en"],
                              user=cfg["username"]), flush=True)
    input("完成登录后，回到这里按回车 > ")
    st, note = entitlement_state(p)
    log("[auth] 人工登录后探测:", note)
    return st is True

def other_publishers_checklist(p, cfg):
    """首次运行可选：Springer / Wiley / T&F 手动机构登录各一次（自动化不稳，人工最稳）"""
    pages = {
        "Springer": "https://link.springer.com/login",
        "Wiley": "https://onlinelibrary.wiley.com/login",
        "Taylor & Francis": "https://www.tandfonline.com/action/showLogin",
    }
    print("""
===============（可选但强烈建议）其他出版社登录 ===============
Elsevier 已登录。下面再人工登录一次另外三家（各 1 分钟），之后全部无人值守：
  • Springerlink / Wiley / Taylor & Francis 各打开一个登录页，
    都选 “Sign in via your institution / 机构登录 / Shibboleth”
    → 检索并选择 {inst_zh} → 学校统一认证登录。
  • 不需要的社可以跳过（对应社的文献会被记为 no-access）。
===============================================================""", flush=True)
    done = []
    marker = LOGS / "auth_done.json"
    try:
        done = json.load(open(marker, encoding="utf-8"))
    except Exception:
        pass
    opened = []
    for name, url in pages.items():
        if name in done:
            continue
        try:
            t = p.context.new_page()
            t.goto(url, wait_until="domcontentloaded", timeout=45000)
            opened.append(name)
        except Exception:
            pass
    if opened:
        input(f"已打开 {', '.join(opened)} 登录页；逐个完成机构登录后，回车继续 > ")
    done = sorted(set(done) | set(pages.keys()))
    LOGS.mkdir(parents=True, exist_ok=True)
    json.dump(done, open(marker, "w", encoding="utf-8"), ensure_ascii=False)

def ensure_entitled(cfg, log=log, skip_other=False):
    chrome_ctl.ensure_chrome(cfg, log)
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=30000)
        ctx = b.contexts[0]
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        for _ in range(3):
            st, note = entitlement_state(p)
            if st is None and note == "robot-challenge":
                log("[auth] ScienceDirect 出现人机挑战，冷却 20 分钟后重试")
                time.sleep(20 * 60)
                continue
            break
        if st is True:
            log("[auth] 机构会话有效，无需登录")
            return True
        log("[auth] 自动登录尝试 ...")
        ok = False
        for _ in range(2):
            try:
                if auto_flow(p, cfg):
                    ok = True
                    break
            except Exception as e:
                log("[auth] 自动流程异常:", repr(e)[:150])
        if not ok:
            st, note = entitlement_state(p)
            if st is not True:
                ok = manual_flow(p, cfg)
        if not ok:
            raise SystemExit("[auth] 登录未完成，无法继续下载。")
        if not skip_other:
            try:
                other_publishers_checklist(p, cfg)
            except SystemExit:
                raise
            except Exception as e:
                log("[auth] 其他出版社登录页异常（可忽略）:", repr(e)[:100])
        return True

if __name__ == "__main__":
    cfg = load_config()
    ensure_entitled(cfg)
    print("登录完成 ✔")
