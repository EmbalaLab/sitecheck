"""One-minute website diagnosis engine.

run_audit(url, outdir) fetches a site the way a visitor, Google and an AI
crawler would, and returns a plain dict of facts. No judgement here; the rules
that turn facts into findings live in findings.py.

Every value is something we measured on this run. Nothing is inferred from a
directory or a cache. Where a measurement failed, the field says so.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import pathlib
import re
import socket
import ssl
import time
from urllib.parse import urljoin, urlparse

import dns.resolver
import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9,en;q=0.7", "X-SiteCheck": "EmbalaLab SiteCheck, https://audit.embalalab.com"}
AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot", "Googlebot"]
TIMEOUT = httpx.Timeout(15.0, connect=10.0)
PHONE_RE = re.compile(r"(?<!\d)(?:\+34[\s.-]?)?(?:[6789]\d{2})[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)")
SOCIALS = ("facebook.com", "instagram.com", "linkedin.com", "tiktok.com", "youtube.com", "x.com", "twitter.com")


def norm_host(raw: str) -> str:
    s = raw.strip()
    if not re.match(r"^[a-z]+://", s, re.I):
        s = "http://" + s
    host = urlparse(s).hostname or ""
    return host.lower().strip(".")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- network ---

async def probe_variants(host: str) -> list[dict]:
    """Try https/http with and without www. Records what a browser would get."""
    bare = host[4:] if host.startswith("www.") else host
    variants = [f"https://{bare}/", f"https://www.{bare}/", f"http://{bare}/", f"http://www.{bare}/"]
    out = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT, headers=HEADERS) as c:
        for v in variants:
            t0 = time.perf_counter()
            rec = {"requested": v, "ok": False, "status": None, "finalUrl": None, "ms": None, "error": "", "redirects": 0}
            try:
                r = await c.get(v)
                rec.update(ok=r.status_code < 400, status=r.status_code, finalUrl=str(r.url), redirects=len(r.history),
                           ms=int((time.perf_counter() - t0) * 1000))
                if rec["ok"] and "html" not in r.headers.get("content-type", ""):
                    rec["ok"] = False
                    rec["error"] = f"not html: {r.headers.get('content-type', '')[:40]}"
                if rec["ok"]:
                    rec["html"] = r.text
                    h = r.headers
                    rec["headers"] = {
                        "server": h.get("server", ""), "poweredBy": h.get("x-powered-by", ""),
                        "contentEncoding": h.get("content-encoding", ""), "cacheControl": h.get("cache-control", ""),
                        "cfRay": bool(h.get("cf-ray")), "via": h.get("via", ""), "xCache": h.get("x-cache", ""),
                        "hsts": bool(h.get("strict-transport-security")),
                        "csp": bool(h.get("content-security-policy")), "xFrame": h.get("x-frame-options", ""),
                    }
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
                rec["ms"] = int((time.perf_counter() - t0) * 1000)
            out.append(rec)
    return out


def cert_info(host: str) -> dict:
    """Days left and whether the certificate is valid for this host."""
    res = {"host": host, "valid": None, "daysLeft": None, "issuer": "", "error": ""}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as s, ctx.wrap_socket(s, server_hostname=host) as ss:
            cert = ss.getpeercert()
        exp = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
        res["daysLeft"] = (exp - dt.datetime.now(dt.timezone.utc)).days
        res["issuer"] = " ".join(v for t in cert.get("issuer", ()) for k, v in t if k == "organizationName")
        res["valid"] = True
    except ssl.SSLCertVerificationError as e:
        res["valid"] = False
        res["error"] = str(e).split("(")[0][:140]
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {str(e)[:100]}"
    return res


def dns_info(host: str) -> dict:
    bare = host[4:] if host.startswith("www.") else host
    r = dns.resolver.Resolver()
    r.lifetime = 8
    res = {"domain": bare, "a": [], "mx": [], "spf": "MISSING", "dmarc": "MISSING", "dmarcPolicy": "", "rdns": "", "error": ""}

    def q(name, rtype):
        try:
            return [str(x.to_text()) for x in r.resolve(name, rtype)]
        except Exception:  # noqa: BLE001
            return []

    res["a"] = q(bare, "A")
    res["mx"] = sorted(m.split()[-1].rstrip(".") for m in q(bare, "MX"))
    for t in q(bare, "TXT"):
        if "v=spf1" in t:
            res["spf"] = t.strip('"')
    for t in q(f"_dmarc.{bare}", "TXT"):
        if "v=DMARC1" in t:
            res["dmarc"] = t.strip('"')
            m = re.search(r"\bp=(\w+)", t)
            res["dmarcPolicy"] = m.group(1) if m else ""
    if res["a"]:
        try:
            res["rdns"] = socket.gethostbyaddr(res["a"][0])[0]
        except Exception:  # noqa: BLE001
            pass
    return res


# ------------------------------------------------------------------- html ---

def detect_cms(html: str, soup: BeautifulSoup) -> dict:
    gen = (soup.find("meta", attrs={"name": re.compile("generator", re.I)}) or {}).get("content", "") if soup else ""
    cms, ver = "", ""
    checks = [
        ("WordPress", r"wp-content|wp-includes|wp-json"), ("PrestaShop", r"prestashop|/modules/ps_"),
        ("Shopify", r"cdn\.shopify\.com|Shopify\."), ("Wix", r"wix\.com|wixstatic"), ("Squarespace", r"squarespace"),
        ("Joomla", r"/media/jui/|joomla"), ("Webflow", r"webflow"), ("Odoo", r"/web/image/|odoo"),
        ("Drupal", r"drupal"), ("HubSpot", r"hs-scripts|hubspot"),
    ]
    for name, pat in checks:
        if re.search(pat, html, re.I):
            cms = name
            break
    m = re.search(r"WordPress\s+([\d.]+)", gen or "")
    if m:
        cms, ver = "WordPress", m.group(1)
    elif gen and not cms:
        cms = gen.split()[0]
    builder = ""
    for b, pat in [("Elementor", r"elementor-(frontend|element|widget)|/plugins/elementor/"), ("Divi", r"et_pb_|/themes/divi/|et-core"), ("WPBakery", r"js_composer|wpb_wrapper"), ("Gutenberg", r"wp-block-")]:
        if re.search(pat, html, re.I):
            builder = b
            break
    return {"cms": cms, "version": ver, "generator": gen, "builder": builder}


def analyze_html(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    base_host = urlparse(page_url).hostname or ""
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    abs_links = [urljoin(page_url, h) for h in links]
    internal = sorted({u.split("#")[0] for u in abs_links if (urlparse(u).hostname or "").replace("www.", "") == base_host.replace("www.", "") and urlparse(u).scheme in ("http", "https") and "/cdn-cgi/" not in u and not re.search(r"\.(pdf|jpg|jpeg|png|gif|webp|svg|zip|mp4)(\?|$)", u, re.I)})
    ld_types: list[str] = []
    for s in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
        try:
            data = json.loads(s.string or "")
        except Exception:  # noqa: BLE001
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                t = x.get("@type")
                if t:
                    ld_types.extend(t if isinstance(t, list) else [t])
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    text = soup.get_text(" ", strip=True)
    body_text = text[:200000]
    imgs = soup.find_all("img")
    page_https = page_url.startswith("https://")
    mixed = 0
    if page_https:
        for tag, attr in (("img", "src"), ("script", "src"), ("link", "href"), ("iframe", "src")):
            for el in soup.find_all(tag):
                v = el.get(attr, "")
                if isinstance(v, str) and v.startswith("http://"):
                    mixed += 1
    low = html.lower()
    analytics = [n for n, pat in [("GA4/gtag", "gtag("), ("Google Tag Manager", "googletagmanager.com"), ("Matomo", "matomo"), ("Plausible", "plausible.io"), ("Umami", "umami"), ("Hotjar", "hotjar"), ("Clarity", "clarity.ms")] if pat in low]
    cookie_banner = bool(re.search(r"cookie|consent|cmp|rgpd|gdpr", " ".join((el.get("id", "") + " " + " ".join(el.get("class", []))) for el in soup.find_all(True, limit=4000)), re.I))
    phones_text = sorted({re.sub(r"[\s.-]", "", m) for m in PHONE_RE.findall(text)})
    yr = re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(20\d{2})", html, re.I)
    return {
        "title": title, "titleLen": len(title),
        "metaDesc": (md.get("content", "") if md else "").strip(), "h1": [h.get_text(" ", strip=True)[:120] for h in soup.find_all("h1")],
        "viewport": bool(soup.find("meta", attrs={"name": "viewport"})), "canonical": bool(soup.find("link", rel=lambda v: v and "canonical" in v)),
        "lang": (soup.html.get("lang", "") if soup.html else ""), "og": bool(soup.find("meta", property=re.compile("^og:", re.I))),
        "noindex": bool(soup.find("meta", attrs={"name": re.compile("robots", re.I), "content": re.compile("noindex", re.I)})),
        **detect_cms(html, soup),
        "ldTypes": sorted(set(ld_types)), "telLinks": sum(1 for h in links if h.lower().startswith("tel:")),
        "waLinks": sum(1 for h in links if re.search(r"wa\.me|api\.whatsapp\.com|whatsapp://|web\.whatsapp\.com", h, re.I)),
        "mailtoLinks": sum(1 for h in links if h.lower().startswith("mailto:")),
        "forms": len(soup.find_all("form")), "textChars": len(body_text), "imgs": len(imgs), "imgsNoAlt": sum(1 for i in imgs if not (i.get("alt") or "").strip()),
        "htmlKb": round(len(html) / 1024), "analytics": analytics, "metaPixel": "fbq(" in low or "connect.facebook.net" in low,
        "cookieBanner": cookie_banner, "phonesInText": phones_text[:5], "copyrightYear": max(yr) if yr else "",
        "socials": sorted({s for s in SOCIALS for h in abs_links if s in h}), "mixedContent": mixed,
        "internalLinks": internal[:60], "booking": bool(re.search(r"calendly|cal\.com|booksy|treatwell|reservar|book now|reserva", low)),
    }


async def robots_sitemap_llms(base: str) -> dict:
    res = {"robotsTxt": False, "disallowAll": False, "sitemapInRobots": False, "aiBots": {}, "sitemapXml": False, "sitemapUrls": 0, "sitemapPath": "", "llmsTxt": False}
    async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT, headers=HEADERS) as c:
        try:
            r = await c.get(urljoin(base, "/robots.txt"))
            if r.status_code == 200 and "<html" not in r.text[:300].lower():
                res["robotsTxt"] = True
                txt = r.text
                res["sitemapInRobots"] = bool(re.search(r"^sitemap:", txt, re.I | re.M))
                groups: dict[str, list[str]] = {}
                cur: list[str] = []
                for line in txt.splitlines():
                    line = line.split("#")[0].strip()
                    if not line:
                        continue
                    k, _, v = line.partition(":")
                    k, v = k.strip().lower(), v.strip()
                    if k == "user-agent":
                        cur = groups.setdefault(v.lower(), [])
                    elif k == "disallow" and cur is not None:
                        cur.append(v)
                star = groups.get("*", [])
                res["disallowAll"] = "/" in star
                for b in AI_BOTS:
                    rules = groups.get(b.lower(), star)
                    res["aiBots"][b] = "blocked" if "/" in rules else "allowed"
            else:
                for b in AI_BOTS:
                    res["aiBots"][b] = "allowed (no robots.txt)"
        except Exception:  # noqa: BLE001
            pass
        for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
            try:
                r = await c.get(urljoin(base, path))
                if r.status_code == 200 and "<urlset" in r.text[:2000] or r.status_code == 200 and "<sitemapindex" in r.text[:2000]:
                    res["sitemapXml"] = True
                    res["sitemapPath"] = path
                    res["sitemapUrls"] = len(re.findall(r"<loc>", r.text))
                    break
            except Exception:  # noqa: BLE001
                continue
        try:
            r = await c.get(urljoin(base, "/llms.txt"))
            res["llmsTxt"] = r.status_code == 200 and "<html" not in r.text[:300].lower()
        except Exception:  # noqa: BLE001
            pass
    return res


async def check_links(links: list[str], limit: int = 15) -> dict:
    res = {"checked": 0, "broken": [], "sample": []}
    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(10.0), headers=HEADERS) as c:
        async def one(u):
            try:
                r = await c.head(u)
                if r.status_code in (403, 405, 501):
                    r = await c.get(u)
                return u, r.status_code
            except Exception as e:  # noqa: BLE001
                return u, f"error: {type(e).__name__}"
        results = await asyncio.gather(*(one(u) for u in links[:limit]))
    for u, st in results:
        res["checked"] += 1
        res["sample"].append({"url": u, "status": st})
        if isinstance(st, str) or st >= 400:
            res["broken"].append({"url": u, "status": st})
    return res


# ------------------------------------------------------------- playwright ---

LCP_SCRIPT = """
window.__lcp = 0;
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true}); } catch (e) {}
"""


async def render(url: str, outdir: pathlib.Path) -> dict:
    """Load the page on an emulated phone and a desktop. One measurement each."""
    from playwright.async_api import async_playwright

    res = {"phone": {}, "desktop": {}}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for kind in ("phone", "desktop"):
            ctx_kw = dict(**p.devices["Pixel 7"]) if kind == "phone" else dict(viewport={"width": 1366, "height": 800})
            ctx = await browser.new_context(**ctx_kw, locale="es-ES")
            await ctx.add_init_script(LCP_SCRIPT)
            page = await ctx.new_page()
            errs: list[str] = []
            failed: list[str] = []
            site_host = (urlparse(url).hostname or "").replace("www.", "")
            # Third-party resources (trackers, ad pixels, fonts) failing from our network are not the site's fault:
            # count only script errors and same-site resources that fail.
            page.on("pageerror", lambda e: errs.append(str(e)[:160]))
            page.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
            page.on("requestfailed", lambda r: failed.append(r.url[:160]) if (urlparse(r.url).hostname or "").replace("www.", "").endswith(site_host) else None)
            rec: dict = {"ok": False, "error": ""}
            t0 = time.perf_counter()
            try:
                resp = await page.goto(url, wait_until="load", timeout=40000)
                rec["loadMs"] = int((time.perf_counter() - t0) * 1000)
                await page.wait_for_timeout(1500)
                rec["status"] = resp.status if resp else None
                rec["finalUrl"] = page.url
                nav = await page.evaluate("() => { const n = performance.getEntriesByType('navigation')[0]; return n ? {dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd), ttfb: Math.round(n.responseStart)} : null }")
                rec.update(nav or {})
                rec["lcpMs"] = int(await page.evaluate("() => window.__lcp || 0"))
                rec["scrollWidth"] = await page.evaluate("document.documentElement.scrollWidth")
                rec["innerWidth"] = await page.evaluate("window.innerWidth")
                rec["renderedTextChars"] = await page.evaluate("document.body ? document.body.innerText.length : 0")
                rec["telLinksRendered"] = await page.evaluate("document.querySelectorAll('a[href^=\"tel:\"]').length")
                rec["waLinksRendered"] = await page.evaluate("document.querySelectorAll('a[href*=\"wa.me\"],a[href*=\"whatsapp\"]').length")
                rec["fontSizeBody"] = await page.evaluate("parseFloat(getComputedStyle(document.body).fontSize)")
                if kind == "phone":
                    res["html"] = await page.content()
                await page.screenshot(path=str(outdir / f"{kind}-fold.png"))
                if kind == "phone":
                    await page.evaluate("() => new Promise(r => { let y = 0; const t = setInterval(() => { window.scrollBy(0, 700); y += 700; if (y > document.body.scrollHeight) { clearInterval(t); window.scrollTo(0, 0); r(); } }, 100); })")
                    await page.wait_for_timeout(600)
                    await page.screenshot(path=str(outdir / f"{kind}-full.png"), full_page=True)
                rec["ok"] = True
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:140]}"
            rec["consoleErrors"] = (errs + [f"Failed to load (same site): {u}" for u in failed])[:10]
            rec["consoleErrorCount"] = len(errs) + len(failed)
            rec["failedRequests"] = failed[:10]
            res[kind] = rec
            await ctx.close()
        await browser.close()
    return res


# -------------------------------------------------------------------- main ---

async def run_audit(raw_url: str, outdir: pathlib.Path, progress=None) -> dict:
    """Full run. `progress(step: str)` is called as each stage finishes."""
    outdir.mkdir(parents=True, exist_ok=True)
    host = norm_host(raw_url)
    say = progress or (lambda s: None)
    t0 = time.perf_counter()
    result: dict = {"input": raw_url, "host": host, "checkedAt": _now(), "tool": "EmbalaLab SiteCheck 0.1"}

    say("dns")
    result["dns"] = await asyncio.to_thread(dns_info, host)
    say("variants")
    variants = await probe_variants(host)
    primary = next((v for v in variants if v["ok"] and v["requested"].startswith("https")), None) or next((v for v in variants if v["ok"]), None)
    result["variants"] = [{k: v for k, v in x.items() if k != "html"} for x in variants]
    result["https"] = {
        "anyHttpsOk": any(v["ok"] and v["requested"].startswith("https") for v in variants),
        "httpRedirectsToHttps": any(v["ok"] and v["requested"].startswith("http://") and (v["finalUrl"] or "").startswith("https://") for v in variants),
        "wwwAndBareAgree": len({(v["finalUrl"] or "").rstrip("/") for v in variants if v["ok"]}) <= 1,
    }
    say("cert")
    result["cert"] = await asyncio.to_thread(cert_info, host)
    blocked = [v for v in variants if v["status"] in (401, 403, 406, 429, 503)]
    if not primary and blocked:
        # A WAF refused the plain fetch. Try a real browser before calling the site down.
        say("render")
        try:
            result["render"] = await render(blocked[0]["requested"], outdir)
        except Exception as e:  # noqa: BLE001
            result["render"] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
        ph = result["render"].get("phone", {})
        if ph.get("ok") and (ph.get("status") or 0) < 400 and result["render"].get("html"):
            primary = {"finalUrl": ph.get("finalUrl") or blocked[0]["requested"], "html": result["render"].pop("html"), "headers": {}, "ms": ph.get("ttfb")}
            result["fetchedVia"] = "browser"
            result["plainFetchBlocked"] = True
    result.get("render", {}).pop("html", None) if isinstance(result.get("render"), dict) else None
    if not primary:
        result["reachable"] = False
        result["blocked"] = bool(blocked)
        result["elapsedMs"] = int((time.perf_counter() - t0) * 1000)
        (outdir / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        return result
    result["reachable"] = True
    result["primaryUrl"] = primary["finalUrl"]
    result["headers"] = primary.get("headers", {})
    result["responseMs"] = primary["ms"]

    say("html")
    result["page"] = analyze_html(primary["html"], primary["finalUrl"])
    say("robots")
    result["seo"] = await robots_sitemap_llms(primary["finalUrl"])
    say("links")
    result["links"] = await check_links([u for u in result["page"]["internalLinks"] if u.rstrip("/") != primary["finalUrl"].rstrip("/")])
    if "render" not in result:
        say("render")
        try:
            result["render"] = await render(primary["finalUrl"], outdir)
        except Exception as e:  # noqa: BLE001
            result["render"] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
    result["render"].pop("html", None)
    result["elapsedMs"] = int((time.perf_counter() - t0) * 1000)
    (outdir / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result
