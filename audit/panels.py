"""Scorecards: SEO basics, AI readiness, speed. Each row is a measured fact with a status.

status: ok | warn | fail | na. Nothing here is a guess; "na" means the check could not run.
"""
from __future__ import annotations


def _row(es, en, status, value=""):
    return {"es": es, "en": en, "status": status, "value": str(value)}


def build_panels(a: dict) -> dict:
    page, seo, rend, dnsr, https, cert = a.get("page", {}), a.get("seo", {}), a.get("render", {}), a.get("dns", {}), a.get("https", {}), a.get("cert", {})
    ph = rend.get("phone", {}) if isinstance(rend, dict) else {}
    if not a.get("reachable"):
        return {"seo": [], "ai": [], "speed": [], "scores": {}}

    # ---------------------------------------------------------------- SEO ---
    S = []
    tl = page.get("titleLen", 0)
    S.append(_row("Título de la portada", "Home page title", "fail" if not tl else "warn" if (tl < 30 or tl > 65) else "ok", f"{tl} caracteres" if tl else "falta / missing"))
    dl = len(page.get("metaDesc", ""))
    S.append(_row("Meta descripción", "Meta description", "fail" if not dl else "warn" if (dl < 70 or dl > 165) else "ok", f"{dl} caracteres" if dl else "falta / missing"))
    h1n = len(page.get("h1", []))
    S.append(_row("Un solo encabezado H1", "Exactly one H1", "fail" if h1n == 0 else "warn" if h1n > 1 else "ok", h1n))
    S.append(_row("Subtítulos H2", "H2 subheadings", "ok" if page.get("h2", 0) else "warn", page.get("h2", 0)))
    S.append(_row("Etiqueta canonical coherente", "Canonical tag consistent", "ok" if page.get("canonicalHref") and page.get("canonicalOk") else "warn" if page.get("canonicalHref") else "warn", page.get("canonicalHref") or "falta / missing"))
    S.append(_row("Indexable (sin noindex)", "Indexable (no noindex)", "fail" if page.get("noindex") else "ok"))
    S.append(_row("robots.txt permite a Google", "robots.txt allows Google", "fail" if seo.get("disallowAll") else "ok" if seo.get("robotsTxt") else "warn", "robots.txt presente" if seo.get("robotsTxt") else "sin robots.txt / none"))
    S.append(_row("Mapa del sitio (sitemap.xml)", "Sitemap (sitemap.xml)", "ok" if seo.get("sitemapXml") else "warn", f"{seo.get('sitemapUrls', 0)} URLs" + (f", última modificación {seo.get('sitemapLastmod')}" if seo.get("sitemapLastmod") else "") if seo.get("sitemapXml") else "falta / missing"))
    S.append(_row("https y redirección desde http", "https and redirect from http", "ok" if https.get("anyHttpsOk") and https.get("httpRedirectsToHttps") else "warn" if https.get("anyHttpsOk") else "fail"))
    S.append(_row("www y sin www coinciden", "www and bare domain agree", "ok" if https.get("wwwAndBareAgree", True) else "warn"))
    S.append(_row("Idioma declarado (lang)", "Language declared (lang)", "ok" if page.get("lang") else "warn", page.get("lang") or "falta / missing"))
    S.append(_row("Open Graph (título, descripción, imagen)", "Open Graph (title, description, image)", "ok" if all(page.get("ogFields", {}).values()) else "warn" if any(page.get("ogFields", {}).values()) else "fail", ", ".join(k for k, v in page.get("ogFields", {}).items() if v) or "ninguno / none"))
    S.append(_row("Favicon", "Favicon", "ok" if page.get("favicon") else "warn"))
    wc = page.get("wordCount", 0)
    S.append(_row("Texto en la portada", "Text on the home page", "fail" if wc < 80 else "warn" if wc < 250 else "ok", f"{wc} palabras / words"))
    im, na = page.get("imgs", 0), page.get("imgsNoAlt", 0)
    S.append(_row("Imágenes con texto alternativo", "Images with alt text", "na" if not im else "ok" if na == 0 else "warn" if na / im <= 0.5 else "fail", f"{im - na}/{im}" if im else "sin imágenes / no images"))
    S.append(_row("Datos estructurados del negocio", "Business structured data", "ok" if page.get("biz", {}).get("type") else "fail", page.get("biz", {}).get("type") or "ninguno / none"))
    S.append(_row("Migas de pan (BreadcrumbList)", "Breadcrumbs (BreadcrumbList)", "ok" if page.get("breadcrumb") else "na"))
    S.append(_row("Versiones por idioma (hreflang)", "Language versions (hreflang)", "ok" if page.get("hreflang") else "na", page.get("hreflang") or ""))

    # ----------------------------------------------------------------- AI ---
    A = []
    bots = seo.get("aiBots", {})
    key_bots = ["GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Applebot-Extended", "Meta-ExternalAgent"]
    blocked = [b for b in key_bots if bots.get(b) == "blocked"]
    A.append(_row("Asistentes de IA pueden entrar (robots.txt)", "AI assistants allowed (robots.txt)", "ok" if not blocked else "warn" if len(blocked) < len(key_bots) else "fail", ("bloqueados / blocked: " + ", ".join(blocked)) if blocked else "todos permitidos / all allowed"))
    raw, rendered = page.get("textChars", 0), ph.get("renderedTextChars") or 0
    A.append(_row("El texto está en el HTML, sin ejecutar scripts", "Text present in HTML without running scripts", "fail" if (raw < 300 and rendered > 800) else "warn" if (rendered and raw < rendered * 0.4) else "ok", f"{raw} caracteres en el código / in code" + (f", {rendered} renderizados / rendered" if rendered else "")))
    A.append(_row("llms.txt (guía para modelos de IA)", "llms.txt (guide for AI models)", "ok" if seo.get("llmsTxt") else "warn", "presente / present" if seo.get("llmsTxt") else "falta / missing"))
    biz = page.get("biz", {})
    have = [k for k in ("name", "address", "telephone", "openingHours", "sameAs", "geo", "url", "image") if biz.get(k)]
    A.append(_row("Ficha del negocio completa (schema.org)", "Complete business card (schema.org)", "fail" if not biz.get("type") else "ok" if len(have) >= 5 else "warn", (biz.get("type") + ": " + ", ".join(have)) if biz.get("type") else "sin ficha / no card"))
    A.append(_row("Preguntas y respuestas (FAQ)", "Questions and answers (FAQ)", "ok" if page.get("faqSchema") else "warn" if (page.get("faqHint") or page.get("questionHeadings")) else "na", "FAQPage schema" if page.get("faqSchema") else (f"{page.get('questionHeadings', 0)} encabezados-pregunta / question headings" if page.get("questionHeadings") else "")))
    A.append(_row("Un H1 claro y subtítulos", "A clear H1 and subheadings", "ok" if (len(page.get("h1", [])) == 1 and page.get("h2", 0)) else "warn" if page.get("h1") else "fail"))
    fp = page.get("firstParagraph", "")
    A.append(_row("Primer párrafo que explica qué es el negocio", "First paragraph explaining what the business is", "ok" if 60 <= len(fp) <= 260 else "warn" if fp else "fail", (fp[:90] + "…") if fp else "no se encontró un párrafo / none found"))
    lm = page.get("landmarks", {})
    A.append(_row("HTML semántico (header, nav, main, footer)", "Semantic HTML (header, nav, main, footer)", "ok" if sum(lm.values()) >= 3 else "warn" if any(lm.values()) else "fail", ", ".join(k for k, v in lm.items() if v) or "ninguno / none"))
    A.append(_row("Nombre y perfiles enlazados (sameAs)", "Name and linked profiles (sameAs)", "ok" if biz.get("sameAs") else "warn" if page.get("socials") else "na", ", ".join(page.get("socials", [])[:3])))
    A.append(_row("Buscador declarado (WebSite SearchAction)", "Site search declared (WebSite SearchAction)", "ok" if page.get("websiteSearch") else "na"))
    A.append(_row("Open Graph para vistas previas en chats", "Open Graph for chat previews", "ok" if all(page.get("ogFields", {}).values()) else "warn"))

    # -------------------------------------------------------------- speed ---
    P = []
    if ph.get("ok"):
        load, lcp, cls = ph.get("loadMs") or 0, ph.get("lcpMs") or 0, ph.get("cls") or 0
        P.append(_row("Contenido principal visible (LCP, móvil emulado)", "Main content visible (LCP, emulated phone)", "ok" if lcp <= 2500 else "warn" if lcp <= 4000 else "fail", f"{lcp/1000:.1f} s" if lcp else "n/d"))
        P.append(_row("Carga completa (móvil emulado)", "Full load (emulated phone)", "ok" if load <= 3000 else "warn" if load <= 6000 else "fail", f"{load/1000:.1f} s"))
        P.append(_row("Estabilidad visual (CLS)", "Visual stability (CLS)", "ok" if cls <= 0.1 else "warn" if cls <= 0.25 else "fail", f"{cls:.2f}"))
        kb = ph.get("kb") or 0
        P.append(_row("Peso de la portada", "Home page weight", "ok" if kb <= 1500 else "warn" if kb <= 3500 else "fail", f"{kb/1024:.1f} MB, {ph.get('requests', 0)} peticiones / requests" + (f", {(ph.get('imageKb') or 0)/1024:.1f} MB imágenes / images" if (ph.get('imageKb') or 0) > 100 else "")))
        P.append(_row("Peticiones a terceros", "Third-party requests", "ok" if (ph.get("thirdPartyRequests") or 0) <= 15 else "warn" if (ph.get("thirdPartyRequests") or 0) <= 40 else "fail", ph.get("thirdPartyRequests", 0)))
        P.append(_row("Sin desplazamiento lateral en el móvil", "No sideways scroll on phone", "ok" if (ph.get("scrollWidth") or 0) <= (ph.get("innerWidth") or 0) + 4 else "fail"))
        P.append(_row("Tamaño de letra en el móvil", "Font size on phone", "ok" if (ph.get("fontSizeBody") or 16) >= 15 else "warn", f"{ph.get('fontSizeBody')} px"))
    hdr = a.get("headers", {})
    if hdr:
        P.append(_row("Compresión (gzip/brotli)", "Compression (gzip/brotli)", "ok" if hdr.get("contentEncoding") else "warn", hdr.get("contentEncoding") or "ninguna / none"))
        P.append(_row("HSTS", "HSTS", "ok" if hdr.get("hsts") else "na"))
    P.append(_row("Tiempo de respuesta del servidor", "Server response time", "ok" if (a.get("responseMs") or 0) <= 800 else "warn" if (a.get("responseMs") or 0) <= 2000 else "fail", f"{a.get('responseMs', 0)} ms"))

    def score(rows):
        pts = {"ok": 1.0, "warn": 0.5, "fail": 0.0}
        scored = [r for r in rows if r["status"] in pts]
        return round(100 * sum(pts[r["status"]] for r in scored) / len(scored)) if scored else None

    return {"seo": S, "ai": A, "speed": P, "scores": {"seo": score(S), "ai": score(A), "speed": score(P)}}
