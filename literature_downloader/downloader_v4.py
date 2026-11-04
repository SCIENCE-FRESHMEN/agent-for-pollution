# -*- coding: utf-8 -*-
"""
授权 PDF 下载器 v4 —— 真实 Chrome（CDP 连接，非 persistent context）。
- 已登录机构 profile 的真实 Chrome，通过 CDP 控制真实点击/导航/下载
- 断点续跑：按目标文件名跳过已存在 PDF
- 日志：逐条追加，立即 flush
- 间隔：每篇 5-10s 随机
用法：
  python downloader_v4.py --limit 25 --tag pilot
  python downloader_v4.py --limit 300 --tag batch1
"""
import sys, io, os, csv, re, json, time, random, argparse, urllib.request, traceback
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# 路径均可经环境变量覆盖（见 config.example.env），缺省为本机配置
ROOT = Path(os.environ.get("LIT_ROOT", r"D:\Compatible_solute_project"))
OUT = Path(os.environ.get("LIT_OUT", str(ROOT / "literature" / "authorized_pdf_v2")))
LIT = Path(os.environ.get("LIT_DIR", str(ROOT / "literature")))
LOG = Path(os.environ.get("LIT_LOG", str(ROOT / "logs" / "authorized_browser_download_v2.csv")))
STATE = Path(os.environ.get("LIT_STATE", str(ROOT / "logs" / "v4_runner_state.json")))
CDP_HTTP = os.environ.get("CDP_HTTP", "http://127.0.0.1:9222")
QUEUE = Path(os.environ.get("QUEUE_PATH",
              r"C:\Users\17965\WorkBuddy\2026-09-16-19-38-28\remaining.csv"))

LOG_FIELDS = ["序号","DOI","标题","出版商","状态","文件名","错误原因","时间","备注"]

def log_row(seq, doi, title, pub, status, fname, err, note):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    exists = LOG.exists()
    with LOG.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(LOG_FIELDS)
        w.writerow([seq, doi, title, pub, status, fname, "" if not err else err,
                    datetime.now().isoformat(timespec="seconds"), note or ""])
        f.flush()

def journal_prefix(doi: str) -> str:
    """期刊级前缀：10.1016/j.envexpbot.2018.01.001 -> 10.1016/j.envexpbot"""
    parts = doi.split("/")
    if len(parts) < 2:
        return ""
    head, rest = parts[0], parts[1]
    seg = rest.split(".")
    if len(seg) >= 2 and seg[0].isalpha() and len(seg[0]) <= 3:
        return f"{head}/{seg[0]}.{seg[1]}"
    return head

def blocked_journals_from_log(min_blocked: int = 3) -> set:
    """从历史日志推导"整刊无权限"：该刊 blocked>=3 且从未成功下载过。"""
    stat = {}
    if LOG.exists():
        with LOG.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                d = (row.get("DOI") or "").strip()
                s = (row.get("状态") or "").strip()
                pre = journal_prefix(d)
                if not pre:
                    continue
                b, ok = stat.get(pre, (0, 0))
                if s == "downloaded":
                    ok += 1
                elif s == "blocked":
                    b += 1
                stat[pre] = (b, ok)
    return {p for p, (b, ok) in stat.items() if b >= min_blocked and ok == 0}

def safe_name(doi):
    # 与既有文件一致：Windows 非法字符 < > : " / \ | ? * → _，再全小写
    return re.sub(r'[<>:"/\\|?*]', "_", doi).lower() + ".pdf"

def existing_stems():
    s = set()
    if LIT.exists():
        for p in LIT.rglob("*.pdf"):
            s.add(p.stem.lower())
    return s

def load_queue():
    rows = []
    with QUEUE.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows.append((r["DOI"].strip(), r["Title"].strip(), r["Publisher"].strip()))
    return rows

def cdp_ws():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(CDP_HTTP + "/json/version", timeout=5) as r:
        return json.loads(r.read().decode())["webSocketDebuggerUrl"]

# ---------- 页面辅助 ----------
COOKIE_JS = """() => {
    const sel = [
        '#onetrust-accept-btn-handler','#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
        '.cookie-consent__accept','button[aria-label*="Accept"]','#accept-cookies',
        'button#onetrust-accept-btn-handler','.osano-cm-accept-all','#hs-eu-confirmation-button'
    ];
    for (const s of sel) {
        const el = document.querySelector(s);
        if (el && el.offsetParent !== null) { el.click(); return s; }
    }
    const txts = ['accept all','accept all cookies','accept cookies','i accept','agree','allow all','got it','ok'];
    for (const b of document.querySelectorAll('button,a')) {
        const t = (b.textContent||'').trim().toLowerCase();
        if (txts.includes(t) && b.offsetParent !== null && t.length < 30) { b.click(); return 'text:'+t; }
    }
    return null;
}"""

def dismiss_cookies(page):
    try:
        return page.evaluate(COOKIE_JS)
    except Exception:
        return None

CHALLENGE_MARKERS = ("are you a robot","verify you are human","captcha","just a moment",
                     "checking your browser","请稍候","access denied","request blocked",
                     "unusual activity")
def detect_challenge(page):
    try:
        body = page.locator("body").inner_text(timeout=2000)[:4000].lower()
    except Exception:
        return False
    return any(m in body for m in CHALLENGE_MARKERS)

def meta_pdf_url(page):
    try:
        return page.evaluate("""() => {
            const m = document.querySelector('meta[name="citation_pdf_url"]');
            return m ? m.getAttribute('content') : null;
        }""")
    except Exception:
        return None

def find_anchor(page, patterns):
    """在真实 DOM 中找匹配锚点，返回绝对 href。patterns: [substr,...]"""
    try:
        return page.evaluate("""(pats) => {
            const links = Array.from(document.querySelectorAll('a'));
            for (const pat of pats) {
                const hit = links.find(a => {
                    const h = (a.getAttribute('href')||'').toLowerCase();
                    if (!h.includes(pat)) return false;
                    if (h.startsWith('javascript')) return false;
                    return true;
                });
                if (hit) return hit.href;
            }
            return null;
        }""", [p.lower() for p in patterns])
    except Exception:
        return None

def abs_url(page, href):
    if not href: return None
    if href.startswith("//"): return "https:" + href
    if href.startswith("/"):
        m = re.match(r"(https?://[^/]+)", page.url)
        return (m.group(1) + href) if m else href
    return href

# ---------- 各出版商策略 ----------
def strategy_elsevier(page, doi):
    # PII 精确匹配，避免命中"推荐文献"的 View PDF
    m = re.search(r"pii/([A-Z0-9]{16,})", page.url, re.I)
    
    if m:
        pii = m.group(1)
        # 老文章用 /pdf，新文章用 /pdfft；按优先级依次尝试
        href = find_anchor(page, [f"/science/article/pii/{pii}/pdfft",
                                  f"/science/article/pii/{pii}/pdf"])
        if href:
            u = abs_url(page, href)
            return u + ("&" if "?" in u else "?") + "download=true", "pdfft+download"
    href = find_anchor(page, ["/pdfft", "/science/article/pii/"])
    if href:
        u = abs_url(page, href)
        if "/pdf" in u or "/pdfft" in u:
            return u + ("&" if "?" in u else "?") + "download=true", "pdfft-any"
    mu = meta_pdf_url(page)
    if mu: return mu, "citation_pdf_url"
    return None, None

def strategy_springer(page, doi):
    href = find_anchor(page, ["/content/pdf/"])
    if href:
        return abs_url(page, href), "content/pdf"
    mu = meta_pdf_url(page)
    if mu: return mu, "citation_pdf_url"
    q = quote(doi, safe="/")
    return f"https://link.springer.com/content/pdf/{q}.pdf", "constructed"

def strategy_wiley(page, doi):
    href = find_anchor(page, ["pdfdirect", "/doi/pdf/", "/doi/epdf"])
    if href and "pdfdirect" in href:
        return abs_url(page, href), "pdfdirect"
    if href and "/doi/pdf/" in href:
        u = abs_url(page, href)
        return u + ("?" if "?" not in u else "&") + "download=true", "doi/pdf"
    mu = meta_pdf_url(page)
    if mu: return mu, "citation_pdf_url"
    q = quote(doi, safe="/")
    return f"https://onlinelibrary.wiley.com/doi/pdfdirect/{q}", "constructed"

def strategy_acs(page, doi):
    href = find_anchor(page, ["/doi/pdf/", "pdfdirect", "/doi/epdf"])
    if href:
        u = abs_url(page, href)
        if "/doi/epdf" in u:
            u = u.replace("/doi/epdf", "/doi/pdf")
        return u + ("?" if "?" not in u else "&") + "download=true", "acs-pdf"
    mu = meta_pdf_url(page)
    if mu: return mu, "citation_pdf_url"
    q = quote(doi, safe="/")
    return f"https://pubs.acs.org/doi/pdf/{q}?download=true", "constructed"

def strategy_generic(page, doi):
    mu = meta_pdf_url(page)
    if mu: return mu, "citation_pdf_url"
    href = find_anchor(page, ["pdfft", "pdfdirect", "/content/pdf/", "/doi/pdf/",
                              "/pdf?", ".pdf"])
    if href:
        u = abs_url(page, href)
        return u, "anchor"
    return None, None

def strategy_for(url, doi):
    u = url.lower()
    if "sciencedirect" in u or "elsevier" in u or "linkinghub" in u:
        return lambda p: strategy_elsevier(p, doi)
    if "link.springer" in u or "springer" in u: return lambda p: strategy_spinger_wrap(p, doi)
    if "onlinelibrary.wiley" in u or "wiley" in u: return lambda p: strategy_wiley(p, doi)
    if "pubs.acs.org" in u: return lambda p: strategy_acs(p, doi)
    return lambda p: strategy_generic(p, doi)

def strategy_spinger_wrap(page, doi):
    return strategy_springer(page, doi)

# ---------- 主下载流程 ----------
def process_one(ctx, page, doi, title, pub, target, timeout_s=120):
    t0 = time.time()
    info = {"status": "", "err": "", "note": "", "file": "", "orig": "", "kind": ""}
    try:
        page.goto(f"https://doi.org/{doi}", wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        msg = str(e)
        if "interrupted by another navigation" not in msg:
            info.update(status="failed_other", err=f"goto: {msg[:120]}")
            return info
    # 等 doi.org → 出版社落地页完成重定向。
    # linkinghub 有时会长时间停在空白页，若过早解析就会误判为"无 PDF 入口"。
    def settled():
        try:
            u = page.url or ""
        except Exception:
            return False
        return ("linkinghub" not in u) and ("doi.org" not in u)

    for _ in range(25):
        if settled():
            break
        time.sleep(1)

    if not settled():
        # 卡在 linkinghub：重新导航再给一次机会
        try:
            page.goto(f"https://doi.org/{doi}", wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass
        for _ in range(25):
            if settled():
                break
            time.sleep(1)

    # 等正文渲染出内容（空白页会让后续锚点查找全部落空）
    for _ in range(15):
        try:
            n = page.evaluate("() => document.body ? document.body.innerText.length : 0")
            if n and n > 500:
                break
        except Exception:
            pass
        time.sleep(1)

    info["note"] = "landing=" + page.url[:100]

    if detect_challenge(page):
        info.update(status="blocked", err="challenge/verification page")
        return info

    dismiss_cookies(page)

    strat = strategy_for(page.url, doi)
    pdf_url, how = strat(page)
    if not pdf_url:
        # 迟渲染：等 PDF 锚点出现（最多 6s，出现即返回）
        try:
            page.wait_for_selector(
                'a[href*="pdfft"], a[href*="pdfdirect"], a[href*="/content/pdf"], '
                'a[href*="/doi/pdf/"], a[href$=".pdf"]',
                timeout=6000, state="attached")
        except Exception:
            pass
        pdf_url, how = strat(page)
    if not pdf_url:
        # 页面压根没有 PDF 入口 = 无权限（书章节/未订阅期刊），属永久失败，
        # 必须记为 blocked 而非 failed_no_pdf，否则会误触发限速熔断白白冷却 20 分钟
        info.update(status="blocked", err="no pdf entry on landing",
                    note=info["note"] + " | " + page.url[:90])
        return info

    # 真实浏览器导航触发下载；Chrome 直接写入 OUT，用目录差异轮询捕获
    before = {p.name for p in OUT.glob("*")}
    try:
        clicked = False
        if how == "content/pdf":
            # Springer 等把 PDF 用内嵌查看器显示：goto 不产生下载文件，
            # 必须像真人一样点击带 download 属性的锚点才会落盘（README：strategy 补丁位）
            try:
                from urllib.parse import urlparse as _up
                _path = _up(pdf_url).path
                _loc = page.locator(f'a[href="{_path}"]').first
                if _loc.count() > 0:
                    _loc.click(timeout=8000)
                    clicked = True
            except Exception:
                clicked = False
        if not clicked:
            page.goto(pdf_url, wait_until="commit", timeout=45000)
    except Exception:
        pass  # 下载型导航常以 ERR_ABORTED 结束，属正常

    # 页面上没有真实下载入口（仅靠 meta/构造 URL）时多半是无权限，快速失败不空等
    fast_fail = how in ("citation_pdf_url", "constructed")
    info["kind"] = "no_entitlement" if fast_fail else "download_failed"
    deadline = time.time() + (12 if fast_fail else 30)
    got_file = None
    while time.time() < deadline:
        time.sleep(0.4)
        new = [p for p in OUT.glob("*") if p.name not in before]
        pdfs = []
        for p in new:
            if p.suffix.lower() != ".pdf" or p.stat().st_size < 20000:
                continue
            try:
                if open(p, "rb").read(5) == b"%PDF-":
                    pdfs.append(p)
            except Exception:
                pass
        if pdfs:
            pdfs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            got_file = pdfs[0]
            break
        # 仍在下载中则继续等
        if any(p.suffix.lower() == ".crdownload" for p in new):
            continue

    if got_file:
        size = got_file.stat().st_size
        got_file.replace(target)
        # 清理同一次下载的去重副本 xxx (n).pdf
        for p in OUT.glob("*"):
            if p.name not in before and p.exists() and p != target and p.suffix.lower() == ".pdf":
                try: p.unlink()
                except Exception: pass
        info.update(status="downloaded", file=str(target), orig=got_file.name,
                    note=f"via {how}; orig={got_file.name}; {size}B")
        return info

    # 没等到：清理残留半成品/异常负载
    for p in OUT.glob("*"):
        if p.name not in before and p.exists():
            try:
                head = open(p, "rb").read(64)
                p.unlink()
                info["err"] = f"cleanup {p.name[:40]}: {head[:32]!r}"
            except Exception:
                pass
    # 区分"未订阅"与"疑似限速"：落地页带明确订阅拒绝文案时按 blocked（永久）处理，
    # 否则非订阅环境下大量 Elsevier/Wiley 文章（有入口但拒绝下载）会被误判限速而触发熔断
    if info["kind"] == "download_failed":
        try:
            _body = page.locator("body").inner_text(timeout=3000)[:4000].lower()
        except Exception:
            _body = ""
        _deny = ("does not subscribe", "not entitled", "rent or subscribe",
                 "purchase pdf", "subscribe to this content", "recommend this library",
                 "institution does not have access", "no access to content",
                 "log in via an institution")
        if any(m in _body for m in _deny):
            info["kind"] = "no_entitlement"
            if not info["err"]:
                info["err"] = "publisher denial on landing"
    # 无下载入口 = 无权限（永久，不触发熔断）；有入口却下不来 = 疑似限速（触发熔断）
    st = "blocked" if info["kind"] == "no_entitlement" else "failed_no_pdf"
    info.update(status=st, err=info["err"] or "no download",
                note=f"pdf_url={pdf_url[:110]}")
    return info

# ---------- 主循环 ----------
def main():
    global QUEUE
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--tag", type=str, default="run")
    ap.add_argument("--queue", type=str, default=str(QUEUE))
    ap.add_argument("--pause-min", type=float, default=30.0, help="每篇最小间隔秒")
    ap.add_argument("--pause-max", type=float, default=45.0, help="每篇最大间隔秒")
    ap.add_argument("--rest-every", type=int, default=40, help="每 N 篇长休息一次")
    ap.add_argument("--rest-sec", type=float, default=300.0, help="长休息秒数")
    ap.add_argument("--max-consec-fail", type=int, default=3, help="连续失败达此数即熔断停车")
    ap.add_argument("--max-consec-blocked", type=int, default=5, help="已授权期刊上连续无PDF入口达此数即熔断")
    args = ap.parse_args()
    if args.queue:
        QUEUE = Path(args.queue)

    stems = existing_stems()
    queue = load_queue()
    seq_base = 0
    if LOG.exists():
        with LOG.open(encoding="utf-8-sig", newline="") as f:
            seq_base = sum(1 for _ in f)
    print(f"queue={len(queue)} existing_pdf_stems={len(stems)} log_rows={seq_base}", flush=True)

    # 已知死条目：日志中同一 DOI 失败 2 次以上 → 判定永久无权限，直接跳过
    # failed_other 视为瞬态错误（网络/拦截抖动），不计入死条目判定，留给补跑轮重试
    fail_counts = {}
    if LOG.exists():
        with LOG.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                s = (row.get("状态") or "").strip()
                if s in ("downloaded", "skipped_exists", "failed_other"):
                    continue
                d = (row.get("DOI") or "").strip()
                if d:
                    fail_counts[d] = fail_counts.get(d, 0) + 1
    dead = {d for d, c in fail_counts.items() if c >= 2}
    bad_journals = blocked_journals_from_log()
    # 曾成功下载过的期刊：这些刊若突然"无 PDF 入口"，基本可判定为限速降级页而非未订阅
    ok_journals = set()
    if LOG.exists():
        with LOG.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("状态") or "").strip() == "downloaded":
                    pre = journal_prefix((row.get("DOI") or "").strip())
                    if pre:
                        ok_journals.add(pre)

    picked = []
    skipped = 0
    for doi, title, pub in queue[args.offset:]:
        if safe_name(doi).removesuffix(".pdf") in stems:
            skipped += 1
            continue
        if doi in dead:
            skipped += 1
            continue
        if journal_prefix(doi) in bad_journals:
            skipped += 1
            continue
        picked.append((doi, title, pub))
        if len(picked) >= args.limit:
            break
    print(f"[{args.tag}] picked={len(picked)} skipped_existing={skipped} "
          f"dead_entries={len(dead)} blocked_journals={len(bad_journals)}", flush=True)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_ws())
        ctx = browser.contexts[0]
        bcdp = browser.new_browser_cdp_session()
        bcdp.send("Browser.setDownloadBehavior", {
            "behavior": "allow", "downloadPath": str(OUT), "eventsEnabled": True})
        print("downloadPath ->", OUT, flush=True)

        page = None
        for p in ctx.pages:
            if "pdfft" not in p.url and not p.url.lower().endswith(".pdf"):
                page = p; break
        if page is None:
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
            except Exception:
                page = ctx.new_page()

        counts = {}
        consec_fail = 0
        consec_throttle = 0
        for i, (doi, title, pub) in enumerate(picked, 1):
            target = OUT / safe_name(doi)
            if target.exists() or safe_name(doi).removesuffix(".pdf") in stems:
                log_row(seq_base + i, doi, title, pub, "skipped_exists", safe_name(doi), "", "already local")
                counts["skipped_exists"] = counts.get("skipped_exists", 0) + 1
                continue
            try:
                r = process_one(ctx, page, doi, title, pub, target)
            except Exception as e:
                r = {"status": "failed_other", "err": f"exc: {repr(e)[:150]}", "note": "", "file": "", "orig": ""}
            log_row(seq_base + i, doi, title, pub, r["status"], safe_name(doi) if r["status"]=="downloaded" else "",
                    r.get("err",""), (r.get("note","") + (" | " + r.get("orig","") if r.get("orig") else "")))
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            stems.add(safe_name(doi).removesuffix(".pdf"))
            print(f"  {i}/{len(picked)} {doi[:52]:52} {r['status']:>14} {r.get('err','')[:60]}", flush=True)

            # 熔断：只统计"疑似限速"型失败（有下载入口却下不来）
            # 无权限（blocked）是永久性的，不计入，否则队列头部的死条目会永久卡死整批
            if r["status"] == "downloaded":
                consec_fail = 0
                consec_throttle = 0
            elif r["status"] == "failed_no_pdf":
                consec_fail += 1
                consec_throttle = 0
                if consec_fail >= args.max_consec_fail:
                    print(f"\n!! 连续 {consec_fail} 篇下载失败，触发熔断 —— 立即停车（疑似再次限速）", flush=True)
                    print("   请等待解封后再恢复，或用 --pause-min/--pause-max 放慢节奏。", flush=True)
                    break
            elif r["status"] == "blocked":
                # blocked 是永久性失败（非订阅/无入口），不算限速，重置连续失败计数，
                # 否则散布在 blocked 之间的个别 failed_no_pdf 会累计成"假连续"误触熔断
                consec_fail = 0
                # 该刊以前下成功过，现在却没 PDF 入口 → 限速降级页，而非真的未订阅
                if journal_prefix(doi) in ok_journals:
                    consec_throttle += 1
                    if consec_throttle >= args.max_consec_blocked:
                        print(f"\n!! 连续 {consec_throttle} 篇在已授权期刊上拿不到 PDF 入口，"
                              f"触发熔断 —— 立即停车（疑似限速降级）", flush=True)
                        break
                # 从未成功过的期刊 → 大概率未订阅，不算限速
            else:
                consec_fail = 0

            # 周期性长休息，避免持续高频请求
            if args.rest_every > 0 and i % args.rest_every == 0 and i < len(picked):
                print(f"  -- 已下 {i} 篇，长休息 {args.rest_sec:.0f}s --", flush=True)
                time.sleep(args.rest_sec)

            time.sleep(random.uniform(args.pause_min, args.pause_max))

        print("== summary ==", flush=True)
        for k, v in counts.items(): print(f"  {k}: {v}", flush=True)
        # 保存进度
        STATE.write_text(json.dumps({"tag": args.tag, "offset": args.offset,
                                     "processed": len(picked),
                                     "counts": counts,
                                     "ts": datetime.now().isoformat()}, ensure_ascii=False),
                         encoding="utf-8")

if __name__ == "__main__":
    main()
