"""Scorecards: SEO basics, AI readiness, speed. Each row is a measured fact with a status.

status: ok | warn | fail | na. Nothing here is a guess; "na" means the check could not run.
"""
from __future__ import annotations


def _row(key, es, en, status, value=""):
    """key: stable id of the check (benchmark.json reports pass rates per key)."""
    return {"key": key, "es": es, "en": en, "status": status, "value": str(value)}


def build_panels(a: dict) -> dict:
    page, seo, rend, dnsr, https, cert = a.get("page", {}), a.get("seo", {}), a.get("render", {}), a.get("dns", {}), a.get("https", {}), a.get("cert", {})
    ph = rend.get("phone", {}) if isinstance(rend, dict) else {}
    if not a.get("reachable"):
        return {"seo": [], "ai": [], "speed": [], "scores": {}, "axes": {}}

    # ---------------------------------------------------------------- SEO ---
    S = []
    tl = page.get("titleLen", 0)
    S.append(_row("title", "Título de la portada", "Home page title", "fail" if not tl else "warn" if (tl < 30 or tl > 65) else "ok", f"{tl} caracteres" if tl else "falta / missing"))
    dl = len(page.get("metaDesc", ""))
    S.append(_row("metaDesc", "Meta descripción", "Meta description", "fail" if not dl else "warn" if (dl < 70 or dl > 165) else "ok", f"{dl} caracteres" if dl else "falta / missing"))
    h1n = len(page.get("h1", []))
    S.append(_row("h1", "Un solo encabezado H1", "Exactly one H1", "fail" if h1n == 0 else "warn" if h1n > 1 else "ok", h1n))
    S.append(_row("h2", "Subtítulos H2", "H2 subheadings", "ok" if page.get("h2", 0) else "warn", page.get("h2", 0)))
    S.append(_row("canonical", "Etiqueta canonical coherente", "Canonical tag consistent", "ok" if page.get("canonicalHref") and page.get("canonicalOk") else "warn" if page.get("canonicalHref") else "warn", page.get("canonicalHref") or "falta / missing"))
    S.append(_row("indexable", "Indexable (sin noindex)", "Indexable (no noindex)", "fail" if page.get("noindex") else "ok"))
    S.append(_row("robots", "robots.txt permite a Google", "robots.txt allows Google", "fail" if seo.get("disallowAll") else "ok" if seo.get("robotsTxt") else "warn", "robots.txt presente" if seo.get("robotsTxt") else "sin robots.txt / none"))
    S.append(_row("sitemap", "Mapa del sitio (sitemap.xml)", "Sitemap (sitemap.xml)", "ok" if seo.get("sitemapXml") else "warn", f"{seo.get('sitemapUrls', 0)} URLs" + (f", última modificación {seo.get('sitemapLastmod')}" if seo.get("sitemapLastmod") else "") if seo.get("sitemapXml") else "falta / missing"))
    S.append(_row("httpsRedirect", "https y redirección desde http", "https and redirect from http", "ok" if https.get("anyHttpsOk") and https.get("httpRedirectsToHttps") else "warn" if https.get("anyHttpsOk") else "fail"))
    S.append(_row("wwwAgree", "www y sin www coinciden", "www and bare domain agree", "ok" if https.get("wwwAndBareAgree", True) else "warn"))
    S.append(_row("lang", "Idioma declarado (lang)", "Language declared (lang)", "ok" if page.get("lang") else "warn", page.get("lang") or "falta / missing"))
    S.append(_row("og", "Open Graph (título, descripción, imagen)", "Open Graph (title, description, image)", "ok" if all(page.get("ogFields", {}).values()) else "warn" if any(page.get("ogFields", {}).values()) else "fail", ", ".join(k for k, v in page.get("ogFields", {}).items() if v) or "ninguno / none"))
    S.append(_row("favicon", "Favicon", "Favicon", "ok" if page.get("favicon") else "warn"))
    wc = page.get("wordCount", 0)
    S.append(_row("wordCount", "Texto en la portada", "Text on the home page", "fail" if wc < 80 else "warn" if wc < 250 else "ok", f"{wc} palabras / words"))
    im, na = page.get("imgs", 0), page.get("imgsNoAlt", 0)
    S.append(_row("imgAlt", "Imágenes con texto alternativo", "Images with alt text", "na" if not im else "ok" if na == 0 else "warn" if na / im <= 0.5 else "fail", f"{im - na}/{im}" if im else "sin imágenes / no images"))
    S.append(_row("bizSchema", "Datos estructurados del negocio", "Business structured data", "ok" if page.get("biz", {}).get("type") else "fail", page.get("biz", {}).get("type") or "ninguno / none"))
    S.append(_row("breadcrumb", "Migas de pan (BreadcrumbList)", "Breadcrumbs (BreadcrumbList)", "ok" if page.get("breadcrumb") else "na"))
    S.append(_row("hreflang", "Versiones por idioma (hreflang)", "Language versions (hreflang)", "ok" if page.get("hreflang") else "na", page.get("hreflang") or ""))

    # ----------------------------------------------------------------- AI ---
    A = []
    bots = seo.get("aiBots", {})
    key_bots = ["GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Applebot-Extended", "Meta-ExternalAgent"]
    blocked = [b for b in key_bots if bots.get(b) == "blocked"]
    A.append(_row("aiBots", "Asistentes de IA pueden entrar (robots.txt)", "AI assistants allowed (robots.txt)", "ok" if not blocked else "warn" if len(blocked) < len(key_bots) else "fail", ("bloqueados / blocked: " + ", ".join(blocked)) if blocked else "todos permitidos / all allowed"))
    raw, rendered = page.get("textChars", 0), ph.get("renderedTextChars") or 0
    A.append(_row("textInHtml", "El texto está en el HTML, sin ejecutar scripts", "Text present in HTML without running scripts", "fail" if (raw < 300 and rendered > 800) else "warn" if (rendered and raw < rendered * 0.4) else "ok", f"{raw} caracteres en el código / in code" + (f", {rendered} renderizados / rendered" if rendered else "")))
    A.append(_row("llmsTxt", "llms.txt (guía para modelos de IA)", "llms.txt (guide for AI models)", "ok" if seo.get("llmsTxt") else "warn", "presente / present" if seo.get("llmsTxt") else "falta / missing"))
    biz = page.get("biz", {})
    have = [k for k in ("name", "address", "telephone", "openingHours", "sameAs", "geo", "url", "image") if biz.get(k)]
    A.append(_row("bizComplete", "Ficha del negocio completa (schema.org)", "Complete business card (schema.org)", "fail" if not biz.get("type") else "ok" if len(have) >= 5 else "warn", (biz.get("type") + ": " + ", ".join(have)) if biz.get("type") else "sin ficha / no card"))
    A.append(_row("faq", "Preguntas y respuestas (FAQ)", "Questions and answers (FAQ)", "ok" if page.get("faqSchema") else "warn" if (page.get("faqHint") or page.get("questionHeadings")) else "na", "FAQPage schema" if page.get("faqSchema") else (f"{page.get('questionHeadings', 0)} encabezados-pregunta / question headings" if page.get("questionHeadings") else "")))
    A.append(_row("h1Clear", "Un H1 claro y subtítulos", "A clear H1 and subheadings", "ok" if (len(page.get("h1", [])) == 1 and page.get("h2", 0)) else "warn" if page.get("h1") else "fail"))
    fp = page.get("firstParagraph", "")
    A.append(_row("firstPara", "Primer párrafo que explica qué es el negocio", "First paragraph explaining what the business is", "ok" if 60 <= len(fp) <= 260 else "warn" if fp else "fail", (fp[:90] + "…") if fp else "no se encontró un párrafo / none found"))
    lm = page.get("landmarks", {})
    A.append(_row("landmarks", "HTML semántico (header, nav, main, footer)", "Semantic HTML (header, nav, main, footer)", "ok" if sum(lm.values()) >= 3 else "warn" if any(lm.values()) else "fail", ", ".join(k for k, v in lm.items() if v) or "ninguno / none"))
    A.append(_row("sameAs", "Nombre y perfiles enlazados (sameAs)", "Name and linked profiles (sameAs)", "ok" if biz.get("sameAs") else "warn" if page.get("socials") else "na", ", ".join(page.get("socials", [])[:3])))
    A.append(_row("searchAction", "Buscador declarado (WebSite SearchAction)", "Site search declared (WebSite SearchAction)", "ok" if page.get("websiteSearch") else "na"))
    A.append(_row("ogChat", "Open Graph para vistas previas en chats", "Open Graph for chat previews", "ok" if all(page.get("ogFields", {}).values()) else "warn"))

    # -------------------------------------------------------------- speed ---
    P = []
    if ph.get("ok"):
        load, lcp, cls = ph.get("loadMs") or 0, ph.get("lcpMs") or 0, ph.get("cls") or 0
        P.append(_row("lcp", "Contenido principal visible (LCP, móvil emulado)", "Main content visible (LCP, emulated phone)", "ok" if lcp <= 2500 else "warn" if lcp <= 4000 else "fail", f"{lcp/1000:.1f} s" if lcp else "n/d"))
        P.append(_row("load", "Carga completa (móvil emulado)", "Full load (emulated phone)", "ok" if load <= 3000 else "warn" if load <= 6000 else "fail", f"{load/1000:.1f} s"))
        P.append(_row("cls", "Estabilidad visual (CLS)", "Visual stability (CLS)", "ok" if cls <= 0.1 else "warn" if cls <= 0.25 else "fail", f"{cls:.2f}"))
        kb = ph.get("kb") or 0
        P.append(_row("weight", "Peso de la portada", "Home page weight", "ok" if kb <= 1500 else "warn" if kb <= 3500 else "fail", f"{kb/1024:.1f} MB, {ph.get('requests', 0)} peticiones / requests" + (f", {(ph.get('imageKb') or 0)/1024:.1f} MB imágenes / images" if (ph.get('imageKb') or 0) > 100 else "")))
        P.append(_row("thirdParty", "Peticiones a terceros", "Third-party requests", "ok" if (ph.get("thirdPartyRequests") or 0) <= 15 else "warn" if (ph.get("thirdPartyRequests") or 0) <= 40 else "fail", ph.get("thirdPartyRequests", 0)))
        P.append(_row("overflow", "Sin desplazamiento lateral en el móvil", "No sideways scroll on phone", "ok" if (ph.get("scrollWidth") or 0) <= (ph.get("innerWidth") or 0) + 4 else "fail"))
        P.append(_row("fontSize", "Tamaño de letra en el móvil", "Font size on phone", "ok" if (ph.get("fontSizeBody") or 16) >= 15 else "warn", f"{ph.get('fontSizeBody')} px"))
    hdr = a.get("headers", {})
    if hdr:
        P.append(_row("compression", "Compresión (gzip/brotli)", "Compression (gzip/brotli)", "ok" if hdr.get("contentEncoding") else "warn", hdr.get("contentEncoding") or "ninguna / none"))
        P.append(_row("hsts", "HSTS", "HSTS", "ok" if hdr.get("hsts") else "na"))
    P.append(_row("responseMs", "Tiempo de respuesta del servidor", "Server response time", "ok" if (a.get("responseMs") or 0) <= 800 else "warn" if (a.get("responseMs") or 0) <= 2000 else "fail", f"{a.get('responseMs', 0)} ms"))

    def score(rows):
        pts = {"ok": 1.0, "warn": 0.5, "fail": 0.0}
        scored = [r for r in rows if r["status"] in pts]
        return round(100 * sum(pts[r["status"]] for r in scored) / len(scored)) if scored else None

    scores = {"seo": score(S), "ai": score(A), "speed": score(P)}
    return {"seo": S, "ai": A, "speed": P, "scores": scores, "axes": build_axes(a, scores)}


# ------------------------------------------------------------------ axes ---
# Six 0-100 axes for the radar chart. Every axis is the mean of its parts, each part scored
# 1 (passes), 0.5 (borderline) or 0 (fails) from a measured value; a part that could not be
# measured on this run is None and is left out of the mean. An axis with no measurable part
# is None, never 0. Thresholds for speed and mobile are Google's published Core Web Vitals
# thresholds (LCP good <= 2.5 s / poor > 4 s; CLS good <= 0.1 / poor > 0.25) plus the
# weight/load limits already used by the speed scorecard. A complete site scores 100 on every
# axis: that is what the "standard" series on the chart means.

AXES = [
    ("security", "Seguridad", "Security"), ("mobile", "Móvil", "Mobile"), ("speed", "Velocidad", "Speed"),
    ("seo", "Google / SEO", "Google / SEO"), ("ai", "IA", "AI"), ("contact", "Contacto", "Contact"),
]


def _part(key, es, en, pts, value=""):
    return {"key": key, "es": es, "en": en, "pts": pts, "value": str(value)}


def _mean(parts):
    sc = [x["pts"] for x in parts if x["pts"] is not None]
    return round(100 * sum(sc) / len(sc)) if sc else None


def build_axes(a: dict, scores: dict) -> dict:
    page, https, cert, hdr = a.get("page", {}), a.get("https", {}), a.get("cert", {}), a.get("headers", {}) or {}
    rend = a.get("render", {}) if isinstance(a.get("render"), dict) else {}
    ph = rend.get("phone", {}) if isinstance(rend.get("phone"), dict) else {}
    phone_ok = bool(ph.get("ok"))

    def tri(v, good, warn, lower_is_better=True):
        """1 if v within the good limit, 0.5 within the warn limit, else 0; None when not measured."""
        if v is None:
            return None
        if lower_is_better:
            return 1.0 if v <= good else 0.5 if v <= warn else 0.0
        return 1.0 if v >= good else 0.5 if v >= warn else 0.0

    # Security: https works, http redirects to https, certificate valid and not about to expire, no mixed content, HSTS.
    days = cert.get("daysLeft")
    sec = [
        _part("https", "Carga por https", "Loads over https", 1.0 if https.get("anyHttpsOk") else 0.0),
        _part("redirect", "http redirige a https", "http redirects to https", 1.0 if https.get("httpRedirectsToHttps") else 0.0),
        _part("certValid", "Certificado válido", "Certificate valid", None if cert.get("valid") is None else (1.0 if cert.get("valid") else 0.0), cert.get("error", "")),
        _part("certDays", "Certificado con margen (> 30 días)", "Certificate not about to expire (> 30 days)", None if days is None else tri(days, 30, 14, lower_is_better=False), f"{days} d" if days is not None else ""),
        _part("mixed", "Sin contenido mixto (http dentro de https)", "No mixed content (http inside https)", None if not page else (1.0 if not page.get("mixedContent") else 0.0), page.get("mixedContent", "")),
        _part("hsts", "HSTS", "HSTS", None if not hdr else (1.0 if hdr.get("hsts") else 0.0)),
    ]
    # Mobile: viewport meta, no sideways scroll, body font >= 15 px (13-15 borderline), CLS within Google's thresholds.
    fs = ph.get("fontSizeBody") if phone_ok else None
    mob = [
        _part("viewport", "Etiqueta viewport", "Viewport meta tag", None if not page else (1.0 if page.get("viewport") else 0.0)),
        _part("overflow", "Sin desplazamiento lateral", "No sideways scroll", (1.0 if (ph.get("scrollWidth") or 0) <= (ph.get("innerWidth") or 0) + 4 else 0.0) if phone_ok else None),
        _part("fontSize", "Letra legible (>= 15 px)", "Readable font size (>= 15 px)", tri(fs, 15, 13, lower_is_better=False) if fs is not None else None, f"{fs} px" if fs is not None else ""),
        _part("cls", "Estabilidad visual (CLS <= 0.1)", "Visual stability (CLS <= 0.1)", tri(ph.get("cls"), 0.1, 0.25) if phone_ok else None, ph.get("cls", "") if phone_ok else ""),
    ]
    # Speed: Google's LCP thresholds, full load, page weight, server response time (same limits as the speed scorecard).
    lcp = (ph.get("lcpMs") or None) if phone_ok else None
    spd = [
        _part("lcp", "LCP <= 2,5 s", "LCP <= 2.5 s", tri(lcp, 2500, 4000), f"{lcp/1000:.1f} s" if lcp else ""),
        _part("load", "Carga completa <= 3 s", "Full load <= 3 s", tri(ph.get("loadMs"), 3000, 6000) if phone_ok else None, f"{(ph.get('loadMs') or 0)/1000:.1f} s" if phone_ok else ""),
        _part("weight", "Peso <= 1,5 MB", "Weight <= 1.5 MB", tri(ph.get("kb"), 1500, 3500) if phone_ok else None, f"{(ph.get('kb') or 0)/1024:.1f} MB" if phone_ok else ""),
        _part("responseMs", "Respuesta del servidor <= 0,8 s", "Server response <= 0.8 s", tri(a.get("responseMs"), 800, 2000), f"{a.get('responseMs', '')} ms"),
    ]
    # Contact: tap-to-call link, WhatsApp link, a phone number in the text, a form or mailto link.
    tel = (page.get("telLinks") or 0) + (ph.get("telLinksRendered") or 0)
    wa = (page.get("waLinks") or 0) + (ph.get("waLinksRendered") or 0)
    con = [
        _part("tel", "Llamar con un toque (tel:)", "Tap to call (tel:)", 1.0 if tel else 0.0),
        _part("whatsapp", "Enlace a WhatsApp", "WhatsApp link", 1.0 if wa else 0.0),
        _part("phoneText", "Teléfono visible en el texto", "Phone number in the text", 1.0 if page.get("phonesInText") else 0.0),
        _part("form", "Formulario o correo", "Form or email link", 1.0 if (page.get("forms") or page.get("mailtoLinks")) else 0.0),
    ] if page else []
    axes = {
        "security": {"score": _mean(sec), "parts": sec},
        "mobile": {"score": _mean(mob), "parts": mob},
        "speed": {"score": _mean(spd), "parts": spd},
        "seo": {"score": scores.get("seo"), "parts": []},   # the SEO scorecard score (checks passed over checks that ran)
        "ai": {"score": scores.get("ai"), "parts": []},     # the AI-readiness scorecard score
        "contact": {"score": _mean(con), "parts": con},
    }
    for k, es, en in AXES:
        axes[k].update(es=es, en=en)
    return axes
