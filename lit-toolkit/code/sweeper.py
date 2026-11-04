# -*- coding: utf-8 -*-
"""批量下载器：单页面串行 + 出版社直链 + staging 轮询（复刻实战验证的 v3 机制）。
用法：python code/sweeper.py [队列.csv]     （不填则用 config.json 里的队列）
"""
import csv, os, re, sys, time, json, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (out_utf8, load_config, queue_path, sn, safe_dir, now,
                    RunLog, append_csv, load_json, save_json, DL, STAGING, DATA, LOGS)
out_utf8()
log = RunLog()
from playwright.sync_api import sync_playwright

FLOG = LOGS / "sweeper_log.csv"

def origin_of(doi):
    d = doi.lower()
    if d.startswith(("10.1007", "10.1038", "10.1023", "10.1134")):
        return "springer"
    if d.startswith(("10.1016", "10.1078")):
        return "elsevier"
    if d.startswith(("10.1002", "10.1111", "10.1046")):
        return "wiley"
    if d.startswith("10.1080"):
        return "tandf"
    return "other"

def poll_new_pdf(before, timeout_s):
    """staging 等新 PDF。只认已改名完成的 .pdf（.crdownload 不碰，防 0 字节空壳）"""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(1)
        if not STAGING.exists():
            continue
        for q in STAGING.glob("*.pdf"):
            if q.name in before or q.stat().st_size < 20000:
                continue
            try:
                with q.open("rb") as fh:
                    if fh.read(5) == b"%PDF-":
                        s1 = q.stat().st_size
                        time.sleep(1.2)
                        if q.stat().st_size == s1:
                            return q
            except Exception:
                continue
    return None

def crossref_pii(doi):
    """缺 PII 时向 Crossref 现查一次（Elsevier alternative-id）并缓存"""
    import requests
    try:
        r = requests.get("https://api.crossref.org/works/" + doi, timeout=20,
                         headers={"User-Agent": "lit-toolkit/1.0 (mailto:toolkit-user)"})
        if r.status_code == 200:
            for aid in r.json()["message"].get("alternative-id") or []:
                s = aid if isinstance(aid, str) else (aid or {}).get("id", "")
                if re.match(r"^S\d", s or ""):
                    return s
    except Exception:
        pass
    return None

def dl_elsevier(page, doi, pmap, target, cfg):
    pii = pmap.get(doi, "")
    if not pii:
        pii = crossref_pii(doi)
        if pii:
            pmap[doi] = pii
            save_json(DATA / "pii_map.json", pmap)
    if not pii:
        return "blocked:no-pii"
    art = f"https://www.sciencedirect.com/science/article/abs/pii/{pii}"
    page.goto(art, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3500 + int(random.uniform(0, 2000)))
    href = None
    try:
        link = page.locator('a:has-text("View PDF")').first
        if link.count() > 0:
            href = link.get_attribute("href")
    except Exception:
        pass
    if not href:
        return "blocked:no-view-pdf-entry"
    full = href if href.startswith("http") else ("https://www.sciencedirect.com" + href)
    full += "&download=true"
    before = {q.name for q in STAGING.glob("*")}
    try:
        page.goto(full, wait_until="commit", timeout=45000)
    except Exception:
        pass
    got = poll_new_pdf(before, 100)
    if not got:
        return "failed_no_pdf:no-download-event"
    time.sleep(1.5)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(got, target)
    return "downloaded"

def dl_direct(page, doi, origin, target):
    if origin == "springer":
        url = f"https://link.springer.com/content/pdf/{doi}.pdf"
    elif origin == "wiley":
        url = f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}?download=true"
    else:
        url = f"https://www.tandfonline.com/doi/pdf/{doi}?download=true"
    before = {q.name for q in STAGING.glob("*")}
    try:
        page.goto(url, wait_until="commit", timeout=45000)
    except Exception:
        pass
    got = poll_new_pdf(before, 30)
    if not got:
        u = (page.url or "").lower()
        if "/pdf" not in u:
            return "blocked:redirected-to-landing"
        return "failed_no_pdf:no-download"
    time.sleep(1.5)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(got, target)
    return "downloaded"

def dl_generic(page, doi, target):
    try:
        page.goto(f"https://doi.org/{doi}", wait_until="domcontentloaded", timeout=45000)
    except Exception:
        return "failed_other:doi-goto"
    page.wait_for_timeout(4000)
    pdf_url = None
    try:
        pdf_url = page.evaluate("""() => {
            const m = document.querySelector('meta[name="citation_pdf_url"]');
            if (m) return m.getAttribute("content");
            const pats = ["/pdfft", "pdfdirect", "/content/pdf/", "/doi/pdf/", "/pdf/"];
            for (const a of document.querySelectorAll("a")) {
                const h = (a.getAttribute("href") || "").toLowerCase();
                if (pats.some(p => h.includes(p)) && !h.startsWith("javascript")) {
                    return a.href;
                }
            }
            return null;
        }""")
    except Exception:
        pass
    if not pdf_url:
        return "blocked:no-pdf-entry"
    before = {q.name for q in STAGING.glob("*")}
    try:
        page.goto(pdf_url, wait_until="commit", timeout=45000)
    except Exception:
        pass
    got = poll_new_pdf(before, 40)
    if not got:
        return "failed_no_pdf:no-download"
    time.sleep(1.5)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(got, target)
    return "downloaded"

def run():
    cfg = load_config()
    qp = Path(sys.argv[1]) if len(sys.argv) > 1 else queue_path(cfg)
    rows = list(csv.DictReader(open(qp, encoding="utf-8-sig", newline="")))
    jmap = load_json(DATA / "journal_map.json", {})
    pmap = load_json(DATA / "pii_map.json", {})
    pmin, pmax = float(cfg.get("pace_min", 6)), float(cfg.get("pace_max", 10))

    STAGING.mkdir(parents=True, exist_ok=True)
    DL.mkdir(parents=True, exist_ok=True)
    stats = {"seq": 0, "downloaded": 0, "blocked": 0, "failed_no_pdf": 0,
             "failed_other": 0, "skipped_exists": 0}
    log(f"[sweeper] 队列 {qp.name} 共 {len(rows)} 行")

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=30000)
        sess = browser.new_browser_cdp_session()
        sess.send("Browser.setDownloadBehavior",
                  {"behavior": "allow", "downloadPath": str(STAGING), "eventsEnabled": True})
        ctx = browser.contexts[0]
        page = None
        for pg in ctx.pages:
            if "sciencedirect.com" in (pg.url or ""):
                page = pg
                break
        if page is None:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for r in rows:
            doi = (r.get("DOI") or r.get("doi") or "").strip()
            if not doi:
                continue
            stats["seq"] += 1
            journal = safe_dir(r.get("Journal") or jmap.get(doi) or "Unknown")
            target = DL / journal / (sn(doi) + ".pdf")
            if target.exists() and target.stat().st_size >= 20000:
                stats["skipped_exists"] += 1
                continue
            origin = origin_of(doi)
            try:
                if origin == "elsevier":
                    st = dl_elsevier(page, doi, pmap, target, cfg)
                elif origin in ("springer", "wiley", "tandf"):
                    st = dl_direct(page, doi, origin, target)
                else:
                    st = dl_generic(page, doi, target)
            except Exception as e:
                st = "failed_other:" + repr(e)[:90]
            if st.startswith("downloaded"):
                stats["downloaded"] += 1
            elif st.startswith("blocked"):
                stats["blocked"] += 1
            elif st.startswith("failed_no_pdf"):
                stats["failed_no_pdf"] += 1
            else:
                stats["failed_other"] += 1
            append_csv(FLOG, ["序号", "DOI", "期刊", "状态", "文件", "原因", "时间"],
                       [stats["seq"], doi, journal, st,
                        str(target.relative_to(DL)) if st.startswith("downloaded") else "",
                        "" if st.startswith("downloaded") else st, now()])
            pace = random.uniform(pmin, pmax) if st.startswith("downloaded") \
                else random.uniform(max(3, pmin / 2), max(5, pmax / 2))
            time.sleep(pace)
            if stats["seq"] % 50 == 0:
                log(f"[sweeper] {stats['seq']}/{len(rows)} dl={stats['downloaded']} "
                    f"blk={stats['blocked']} fnp={stats['failed_no_pdf']} "
                    f"other={stats['failed_other']} skip={stats['skipped_exists']}")
    log("[sweeper] SUMMARY " + json.dumps(stats, ensure_ascii=False))

if __name__ == "__main__":
    run()
