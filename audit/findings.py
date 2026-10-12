"""Turn measured facts into findings an owner can understand.

Every finding has: id, severity (high | medium | low), a title, what we saw
(with the measured values), why it costs the business something, and how the
owner can see it themselves. Spanish and English. No finding may claim more
than the engine measured; where a check did not run, nothing is said.
"""
from __future__ import annotations

import datetime as dt

from .panels import build_panels

SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def _f(id_, sev, es, en, evidence=None):
    return {"id": id_, "severity": sev, "es": es, "en": en, "evidence": evidence or []}


def build_findings(a: dict) -> dict:
    """Returns {"findings": [...], "good": [...], "summary": {...}}."""
    F: list[dict] = []
    G: list[dict] = []
    host = a["host"]
    bare = host[4:] if host.startswith("www.") else host
    dnsr, cert, https = a.get("dns", {}), a.get("cert", {}), a.get("https", {})
    mx = f"https://mxtoolbox.com/SuperTool.aspx?action=mx%3a{bare}"

    # --- reachability -------------------------------------------------------
    if not a.get("reachable") and a.get("blocked"):
        codes = ", ".join(str(v["status"]) for v in a.get("variants", []) if v.get("status"))
        F.append(_f("blocked", "medium",
                    {"title": "La web rechaza las visitas automáticas", "saw": f"El servidor respondió {codes} a nuestra petición y también al navegador emulado. Suele ser un cortafuegos (Cloudflare, Hostinger, Wordfence) que bloquea direcciones de centros de datos.", "why": "Para una persona en el móvil la web probablemente funciona. Pero si ese bloqueo también alcanza a Google o a los asistentes de IA, la web desaparece de los resultados. Conviene comprobar en Search Console que Google sí la lee.", "see": "Abra la web desde el móvil con datos; si carga, el bloqueo solo afecta a robots."},
                    {"title": "The site refuses automated visits", "saw": f"The server answered {codes} to our request and to the emulated browser. Usually a firewall (Cloudflare, Hostinger, Wordfence) blocking data-centre addresses.", "why": "For a person on a phone the site probably works. But if that block also catches Google or AI assistants, the site vanishes from results. Check in Search Console that Google can read it.", "see": "Open the site on a phone over mobile data; if it loads, the block only affects robots."}))
        return {"findings": F, "good": G, "summary": _summary(F, a), "panels": build_panels(a)}
    if not a.get("reachable"):
        errs = "; ".join(f"{v['requested']}: {v['error'] or v['status']}" for v in a.get("variants", []))[:300]
        F.append(_f("down", "high",
                    {"title": "La web no responde", "saw": f"Ninguna de las cuatro direcciones cargó. {errs}", "why": "Quien busque el negocio hoy no encuentra nada. Cada visita que llega desde Google o desde una tarjeta se pierde.", "see": "Abra la web en el móvil con los datos, no con el wifi de la oficina."},
                    {"title": "The site does not respond", "saw": f"None of the four addresses loaded. {errs}", "why": "Anyone looking for the business today finds nothing. Every visit from Google or a business card is lost.", "see": "Open the site on a phone using mobile data, not the office wifi."}))
        return {"findings": F, "good": G, "summary": _summary(F, a), "panels": build_panels(a)}

    page, seo, links, rend, hdr = a.get("page", {}), a.get("seo", {}), a.get("links", {}), a.get("render", {}), a.get("headers", {})
    ph, dsk = rend.get("phone", {}), rend.get("desktop", {})
    primary = a.get("primaryUrl", "")
    if a.get("plainFetchBlocked"):
        G.append({"es": "El servidor bloquea peticiones automáticas sencillas; el navegador emulado sí entró. Las cabeceras del servidor no se pudieron leer.", "en": "The server blocks simple automated requests; the emulated browser got in. Server headers could not be read."})

    # --- https / certificate ------------------------------------------------
    if not https.get("anyHttpsOk"):
        F.append(_f("no-https", "high",
                    {"title": "La web solo carga sin cifrar (http)", "saw": f"La dirección segura https://{bare} no carga; la web se sirve por http. {cert.get('error', '')}".strip(), "why": "Chrome marca la página como 'No es seguro' al lado de la dirección. Google la coloca por debajo de las que sí lo son. Un formulario de contacto aquí viaja en claro.", "see": f"Escriba https://{bare} en el navegador y mire el aviso."},
                    {"title": "The site only loads unencrypted (http)", "saw": f"The secure address https://{bare} does not load; the site is served over http. {cert.get('error', '')}".strip(), "why": "Chrome shows 'Not secure' next to the address. Google ranks it below sites that are. A contact form here travels in the clear.", "see": f"Type https://{bare} in the browser and look at the warning."},
                    [f"https://www.ssllabs.com/ssltest/analyze.html?d={bare}"]))
    elif cert.get("valid") is False:
        F.append(_f("cert-invalid", "high",
                    {"title": "El certificado de seguridad no es válido para este dominio", "saw": f"Al conectar a https://{host} el navegador rechaza el certificado: {cert.get('error', '')}.", "why": "Quien entre por la dirección segura ve una pantalla roja de advertencia y se va. Es lo primero que ve un cliente nuevo.", "see": f"Abra https://{host} en una ventana privada."},
                    {"title": "The security certificate is not valid for this domain", "saw": f"Connecting to https://{host} the browser rejects the certificate: {cert.get('error', '')}.", "why": "Anyone arriving at the secure address sees a full-page red warning and leaves. It is the first thing a new customer sees.", "see": f"Open https://{host} in a private window."},
                    [f"https://www.ssllabs.com/ssltest/analyze.html?d={bare}"]))
    else:
        if https.get("anyHttpsOk") and not https.get("httpRedirectsToHttps"):
            F.append(_f("no-redirect", "medium",
                        {"title": "La versión http no redirige a la segura", "saw": f"http://{bare} carga y se queda en http en vez de pasar a https.", "why": "Hay dos webs iguales para Google y para el visitante: una segura y otra no. Los enlaces antiguos y las tarjetas llevan a la insegura.", "see": f"Escriba http://{bare} y mire si la dirección cambia a https."},
                        {"title": "The http version does not redirect to the secure one", "saw": f"http://{bare} loads and stays on http instead of switching to https.", "why": "Google and visitors see two identical sites, one secure and one not. Old links and business cards lead to the insecure one.", "see": f"Type http://{bare} and watch whether the address switches to https."}))
        d = cert.get("daysLeft")
        if isinstance(d, int) and d < 30:
            F.append(_f("cert-expiring", "high" if d < 7 else "medium",
                        {"title": f"El certificado de seguridad caduca en {d} días", "saw": f"Emitido por {cert.get('issuer') or 'desconocido'}, caduca en {d} días.", "why": "El día que caduque, la web mostrará una advertencia roja a todo el mundo hasta que alguien lo renueve.", "see": "Pulse el candado junto a la dirección y mire la fecha de caducidad."},
                        {"title": f"The security certificate expires in {d} days", "saw": f"Issued by {cert.get('issuer') or 'unknown'}, expires in {d} days.", "why": "The day it expires the site shows a red warning to everyone until someone renews it.", "see": "Click the padlock next to the address and check the expiry date."}))
        if cert.get("valid"):
            G.append({"es": f"Certificado de seguridad válido ({cert.get('daysLeft')} días restantes).", "en": f"Valid security certificate ({cert.get('daysLeft')} days left)."})

    if not https.get("wwwAndBareAgree", True):
        F.append(_f("www-mismatch", "low",
                    {"title": "Con y sin www acaban en páginas distintas", "saw": "Las variantes con y sin www no terminan en la misma dirección final.", "why": "Google reparte la autoridad del dominio entre dos versiones y el visitante puede acabar en la copia equivocada.", "see": f"Compare {bare} y www.{bare} en el navegador."},
                    {"title": "With and without www end on different pages", "saw": "The www and bare variants do not end at the same final address.", "why": "Google splits the domain's authority between two versions and a visitor can land on the wrong copy.", "see": f"Compare {bare} and www.{bare} in the browser."}))

    # --- speed and phone render ----------------------------------------------
    if ph.get("ok"):
        load = ph.get("loadMs") or 0
        lcp = ph.get("lcpMs") or 0
        if load > 8000 or lcp > 6000:
            sev = "high"
        elif load > 4000 or lcp > 3000:
            sev = "medium"
        else:
            sev = ""
        if sev:
            F.append(_f("slow-phone", sev,
                        {"title": "La web tarda demasiado en cargar en el móvil", "saw": f"En un móvil emulado (Pixel 7, una sola medición) la página terminó de cargar a los {load/1000:.1f} s; el contenido principal apareció a los {lcp/1000:.1f} s.", "why": "Google considera lento todo lo que pasa de 2,5 s. La mitad de los visitantes móviles abandonan una página que tarda más de 3 s en mostrar algo.", "see": "Abra la web en el móvil con datos y cuente los segundos hasta ver algo."},
                        {"title": "The site is too slow on a phone", "saw": f"On an emulated phone (Pixel 7, one measurement) the page finished loading at {load/1000:.1f} s; the main content appeared at {lcp/1000:.1f} s.", "why": "Google treats anything over 2.5 s as slow. Half of mobile visitors leave a page that takes more than 3 s to show something.", "see": "Open the site on a phone over mobile data and count the seconds until something shows."},
                        [f"https://pagespeed.web.dev/analysis?url={primary}"]))
        elif load:
            G.append({"es": f"Carga en el móvil en {load/1000:.1f} s (una medición).", "en": f"Loads on a phone in {load/1000:.1f} s (one measurement)."})
        if (ph.get("scrollWidth") or 0) > (ph.get("innerWidth") or 9999) + 4:
            F.append(_f("mobile-overflow", "medium",
                        {"title": "En el móvil la página es más ancha que la pantalla", "saw": f"Ancho de la página {ph['scrollWidth']} px en una pantalla de {ph['innerWidth']} px: hay que desplazarse de lado para leer.", "why": "Texto cortado y botones fuera de la pantalla. Es la señal más clara de una web pensada solo para ordenador.", "see": "Abra la web en el móvil e intente deslizar de izquierda a derecha."},
                        {"title": "On a phone the page is wider than the screen", "saw": f"Page width {ph['scrollWidth']} px on a {ph['innerWidth']} px screen: you have to scroll sideways to read.", "why": "Cut-off text and buttons off-screen. The clearest sign of a site designed only for desktop.", "see": "Open the site on a phone and try to swipe left to right."}))
        if ph.get("consoleErrorCount", 0) >= 3:
            F.append(_f("js-errors", "low",
                        {"title": "El navegador registra errores al cargar la página", "saw": f"{ph['consoleErrorCount']} errores en la consola del navegador en el móvil. Primero: {(ph.get('consoleErrors') or [''])[0][:120]}", "why": "Suele ser un plugin roto o un recurso que ya no existe. A veces no se nota; otras veces es el formulario que no envía.", "see": "En Chrome de escritorio: menú, Más herramientas, Herramientas para desarrolladores, pestaña Console."},
                        {"title": "The browser logs errors while loading the page", "saw": f"{ph['consoleErrorCount']} errors in the browser console on the phone. First: {(ph.get('consoleErrors') or [''])[0][:120]}", "why": "Usually a broken plugin or a resource that no longer exists. Sometimes invisible; sometimes it is the form that never sends.", "see": "In desktop Chrome: menu, More tools, Developer tools, Console tab."}))
        raw, rendered = page.get("textChars", 0), ph.get("renderedTextChars", 0)
        if raw < 300 and rendered > 800:
            F.append(_f("js-only", "medium",
                        {"title": "El texto de la web solo existe cuando se ejecuta el script", "saw": f"El código de la página trae {raw} caracteres de texto; el navegador, tras ejecutar los scripts, muestra {rendered}.", "why": "Los rastreadores de IA (ChatGPT, Perplexity, Claude) no ejecutan scripts: ven una página vacía. Google la lee, pero más tarde y peor.", "see": "En el navegador, clic derecho, 'Ver código fuente', y busque un párrafo de su web."},
                        {"title": "The site's text only exists once scripts run", "saw": f"The page code carries {raw} characters of text; the browser, after running scripts, shows {rendered}.", "why": "AI crawlers (ChatGPT, Perplexity, Claude) do not run scripts: they see an empty page. Google reads it, but later and worse.", "see": "In the browser, right-click, 'View page source', and look for a paragraph from your site."}))
    elif ph.get("error"):
        F.append(_f("render-failed", "medium",
                    {"title": "No se pudo cargar la página en un móvil emulado", "saw": f"Error al cargar en el móvil emulado: {ph['error']}", "why": "Puede ser un bloqueo a robots o un fallo real en móvil. Hay que comprobarlo en un teléfono físico.", "see": "Abra la web en un móvil con datos."},
                    {"title": "The page could not be loaded on an emulated phone", "saw": f"Error loading on the emulated phone: {ph['error']}", "why": "Could be a bot block or a real mobile failure. Check on a physical phone.", "see": "Open the site on a phone over mobile data."}))

    # --- contact ---------------------------------------------------------------
    tel = max(page.get("telLinks", 0), ph.get("telLinksRendered", 0) or 0)
    wa = max(page.get("waLinks", 0), ph.get("waLinksRendered", 0) or 0)
    phones = page.get("phonesInText", [])
    if tel == 0 and phones:
        F.append(_f("no-tap-to-call", "medium",
                    {"title": "El teléfono está escrito pero no se puede pulsar", "saw": f"La portada muestra el número {phones[0]} como texto; ningún enlace tel: lo convierte en botón de llamada.", "why": "En el móvil, un número que no se pulsa hay que memorizarlo o copiarlo. Una parte de las llamadas se pierde en ese paso.", "see": "Abra la web en el móvil y toque el número de teléfono."},
                    {"title": "The phone number is written but cannot be tapped", "saw": f"The home page shows the number {phones[0]} as text; no tel: link turns it into a call button.", "why": "On a phone, a number you cannot tap has to be memorised or copied. A share of calls is lost at that step.", "see": "Open the site on a phone and tap the phone number."}))
    elif tel == 0 and not phones and wa > 0:
        F.append(_f("no-phone-wa", "low",
                    {"title": "Hay WhatsApp pero no hay teléfono en la portada", "saw": "La portada tiene enlace de WhatsApp y ningún número de teléfono ni botón de llamada.", "why": "Una parte de los clientes, sobre todo mayores, prefiere llamar. Un número pulsable al lado del WhatsApp no quita nada.", "see": "Abra la portada en el móvil y busque cómo llamar."},
                    {"title": "WhatsApp present but no phone number on the home page", "saw": "The home page has a WhatsApp link and no phone number or call button.", "why": "Some customers, older ones especially, prefer to call. A tappable number next to WhatsApp costs nothing.", "see": "Open the home page on a phone and look for a way to call."}))
    elif tel == 0 and not phones:
        F.append(_f("no-phone", "medium",
                    {"title": "La portada no muestra ningún teléfono", "saw": "No se encontró ningún número de teléfono ni enlace de llamada en la portada.", "why": "Para un negocio local, el teléfono en la portada es la conversión más corta que existe. Sin él, el visitante tiene que buscar.", "see": "Abra la portada en el móvil y busque cómo llamar."},
                    {"title": "The home page shows no phone number", "saw": "No phone number and no call link were found on the home page.", "why": "For a local business, the phone on the home page is the shortest conversion there is. Without it the visitor has to hunt.", "see": "Open the home page on a phone and look for a way to call."}))
    else:
        G.append({"es": "Botón de llamada presente en la portada.", "en": "Tap-to-call present on the home page."})
    if wa == 0:
        F.append(_f("no-whatsapp", "low",
                    {"title": "No hay enlace de WhatsApp", "saw": "La portada no tiene ningún enlace a WhatsApp.", "why": "En España más de la mitad de los contactos a un negocio pequeño empiezan por WhatsApp. Un enlace cuesta diez minutos.", "see": "Busque el icono verde en la portada desde el móvil."},
                    {"title": "No WhatsApp link", "saw": "The home page has no WhatsApp link.", "why": "In Spain more than half of first contacts to a small business start on WhatsApp. A link takes ten minutes.", "see": "Look for the green icon on the home page from a phone."}))
    else:
        G.append({"es": "Enlace de WhatsApp presente.", "en": "WhatsApp link present."})

    # --- basics Google reads -----------------------------------------------------
    t = page.get("title", "")
    if not t:
        F.append(_f("no-title", "medium",
                    {"title": "La portada no tiene título", "saw": "La etiqueta <title> está vacía o no existe.", "why": "El título es la línea azul del resultado en Google y el nombre de la pestaña. Sin él, Google inventa uno.", "see": "Busque el negocio en Google y mire la línea azul."},
                    {"title": "The home page has no title", "saw": "The <title> tag is empty or missing.", "why": "The title is the blue line of the Google result and the tab name. Without it Google makes one up.", "see": "Search the business on Google and look at the blue line."}))
    elif len(t) < 12 or t.lower() in ("home", "inicio", "index"):
        F.append(_f("weak-title", "low",
                    {"title": "El título de la portada no dice qué hace el negocio", "saw": f"Título actual: '{t}'.", "why": "Es lo que Google muestra en azul. 'Inicio' no gana ningún clic.", "see": "Busque el negocio en Google."},
                    {"title": "The home page title does not say what the business does", "saw": f"Current title: '{t}'.", "why": "It is what Google shows in blue. 'Home' wins no clicks.", "see": "Search the business on Google."}))
    if not page.get("metaDesc"):
        F.append(_f("no-meta-desc", "low",
                    {"title": "Sin descripción para Google", "saw": "No hay meta descripción en la portada.", "why": "Google muestra bajo el enlace un trozo de texto al azar en vez de la frase que usted elegiría.", "see": "Busque el negocio en Google y lea las dos líneas grises."},
                    {"title": "No description for Google", "saw": "The home page has no meta description.", "why": "Google shows a random snippet under the link instead of the sentence you would choose.", "see": "Search the business on Google and read the two grey lines."}))
    if not page.get("h1"):
        F.append(_f("no-h1", "low",
                    {"title": "La portada no tiene un encabezado principal", "saw": "No hay ninguna etiqueta <h1>.", "why": "Es la primera pista que Google y los lectores de IA usan para saber de qué va la página.", "see": "Es técnico; no se ve a simple vista."},
                    {"title": "The home page has no main heading", "saw": "There is no <h1> tag.", "why": "It is the first clue Google and AI readers use to know what the page is about.", "see": "Technical; not visible by eye."}))
    if not page.get("viewport"):
        F.append(_f("no-viewport", "high",
                    {"title": "La página no está preparada para móvil", "saw": "Falta la etiqueta viewport: el móvil muestra la versión de ordenador encogida.", "why": "Todo se ve diminuto y hay que hacer zoom para leer. Google penaliza la página en las búsquedas desde móvil, que son la mayoría.", "see": "Abra la web en el móvil."},
                    {"title": "The page is not set up for phones", "saw": "The viewport tag is missing: the phone shows the desktop version shrunk down.", "why": "Everything is tiny and needs zooming to read. Google demotes the page in mobile searches, which are the majority.", "see": "Open the site on a phone."}))
    if page.get("noindex"):
        F.append(_f("noindex", "high",
                    {"title": "La portada pide a Google que no la muestre", "saw": "La página lleva la etiqueta robots noindex.", "why": "Google obedece: la web no aparece en las búsquedas. Suele ser un ajuste olvidado de cuando se construyó.", "see": "Busque el nombre del negocio en Google."},
                    {"title": "The home page asks Google not to show it", "saw": "The page carries a robots noindex tag.", "why": "Google obeys: the site does not appear in searches. Usually a forgotten setting from when it was built.", "see": "Search the business name on Google."}))
    if seo.get("disallowAll"):
        F.append(_f("robots-block", "high",
                    {"title": "El archivo robots.txt bloquea a todos los buscadores", "saw": "robots.txt contiene 'Disallow: /' para todos los robots.", "why": "Google tiene prohibido leer la web. No saldrá en las búsquedas hasta que se quite.", "see": f"Abra {primary.rstrip('/')}/robots.txt"},
                    {"title": "robots.txt blocks every search engine", "saw": "robots.txt contains 'Disallow: /' for all robots.", "why": "Google is forbidden from reading the site. It will not appear in searches until it is removed.", "see": f"Open {primary.rstrip('/')}/robots.txt"}))
    if not seo.get("sitemapXml"):
        F.append(_f("no-sitemap", "low",
                    {"title": "No hay mapa del sitio para Google", "saw": "No existe sitemap.xml en la dirección habitual ni declarado en robots.txt.", "why": "Google encuentra las páginas nuevas más tarde. En una web pequeña importa poco; en una tienda, mucho.", "see": f"Abra {primary.rstrip('/')}/sitemap.xml"},
                    {"title": "No sitemap for Google", "saw": "No sitemap.xml at the usual address and none declared in robots.txt.", "why": "Google finds new pages later. On a small site it matters little; on a shop, a lot.", "see": f"Open {primary.rstrip('/')}/sitemap.xml"}))
    else:
        G.append({"es": f"Mapa del sitio presente ({seo.get('sitemapUrls')} direcciones).", "en": f"Sitemap present ({seo.get('sitemapUrls')} URLs)."})
    blocked = [b for b, v in seo.get("aiBots", {}).items() if v == "blocked" and b in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended")]
    if blocked:
        F.append(_f("ai-blocked", "low",
                    {"title": "La web bloquea a los asistentes de IA", "saw": f"robots.txt prohíbe la entrada a {', '.join(blocked)}.", "why": "Cuando alguien pregunta a ChatGPT o Perplexity por un negocio como el suyo, no pueden leer su web para recomendarla. Puede ser una decisión; conviene que sea consciente.", "see": f"Abra {primary.rstrip('/')}/robots.txt"},
                    {"title": "The site blocks AI assistants", "saw": f"robots.txt forbids {', '.join(blocked)}.", "why": "When someone asks ChatGPT or Perplexity for a business like yours, they cannot read your site to recommend it. It may be deliberate; it should be conscious.", "see": f"Open {primary.rstrip('/')}/robots.txt"}))
    lt = page.get("ldTypes", [])
    if not any(x in lt for x in ("LocalBusiness", "Organization", "Store", "Restaurant", "Dentist", "MedicalBusiness", "AutoRepair", "Hotel", "ProfessionalService", "LegalService", "HomeAndConstructionBusiness")) and not any("Business" in x or "Service" in x for x in lt):
        F.append(_f("no-schema", "low",
                    {"title": "Sin datos estructurados del negocio", "saw": f"El código no incluye la ficha del negocio (nombre, dirección, horario, teléfono) en el formato que leen Google y los asistentes de IA. Tipos encontrados: {', '.join(lt) or 'ninguno'}.", "why": "Google y los asistentes de IA tienen que adivinar qué es el negocio. Con la ficha, lo saben.", "see": "Es técnico; se comprueba con la herramienta de resultados enriquecidos de Google."},
                    {"title": "No structured business data", "saw": f"The code does not include the business card (name, address, hours, phone) in the format Google and AI assistants read. Types found: {', '.join(lt) or 'none'}.", "why": "Google and AI assistants have to guess what the business is. With the card, they know.", "see": "Technical; checked with Google's rich results test."},
                    [f"https://search.google.com/test/rich-results?url={primary}"]))
    else:
        G.append({"es": f"Datos estructurados presentes ({', '.join(lt[:3])}).", "en": f"Structured data present ({', '.join(lt[:3])})."})

    # --- email ---------------------------------------------------------------
    if dnsr.get("mx"):
        if dnsr.get("spf") == "MISSING":
            F.append(_f("spf-missing", "medium",
                        {"title": "El correo del dominio no tiene registro SPF", "saw": f"No hay registro SPF en {bare}. El correo se recibe en {dnsr['mx'][0]}.", "why": "Cualquiera puede enviar correos que parecen venir de @{bare}. Y los correos legítimos de la empresa acaban más a menudo en spam.".replace("{bare}", bare), "see": "Es técnico; lo comprueba el enlace de evidencia."},
                        {"title": "The domain's email has no SPF record", "saw": f"No SPF record on {bare}. Mail is received at {dnsr['mx'][0]}.", "why": f"Anyone can send email that appears to come from @{bare}. And the company's legitimate email lands in spam more often.", "see": "Technical; the evidence link checks it."},
                        [f"https://mxtoolbox.com/SuperTool.aspx?action=spf%3a{bare}"]))
        if dnsr.get("dmarc") == "MISSING":
            F.append(_f("dmarc-missing", "medium",
                        {"title": "El correo del dominio no tiene registro DMARC", "saw": f"No existe _dmarc.{bare}.", "why": "Nada le dice a Gmail u Outlook que rechacen los correos falsificados con su dominio. Desde 2024 los grandes proveedores lo exigen para entregar correo masivo.", "see": "Es técnico; lo comprueba el enlace de evidencia."},
                        {"title": "The domain's email has no DMARC record", "saw": f"_dmarc.{bare} does not exist.", "why": "Nothing tells Gmail or Outlook to reject forged email using your domain. Since 2024 the big providers require it for bulk mail.", "see": "Technical; the evidence link checks it."},
                        [f"https://mxtoolbox.com/SuperTool.aspx?action=dmarc%3a{bare}"]))
        elif dnsr.get("dmarcPolicy") == "none":
            F.append(_f("dmarc-none", "low",
                        {"title": "DMARC está en modo 'none'", "saw": f"El registro DMARC de {bare} tiene p=none: los correos falsificados se reportan pero se entregan igual.", "why": "Es el primer paso, no el último. Con p=quarantine o p=reject, los falsos dejan de llegar.", "see": "Es técnico; lo comprueba el enlace de evidencia."},
                        {"title": "DMARC is set to 'none'", "saw": f"The DMARC record for {bare} has p=none: forged mail is reported but still delivered.", "why": "It is the first step, not the last. With p=quarantine or p=reject, the fakes stop arriving.", "see": "Technical; the evidence link checks it."},
                        [f"https://mxtoolbox.com/SuperTool.aspx?action=dmarc%3a{bare}"]))
        if dnsr.get("spf") != "MISSING" and dnsr.get("dmarcPolicy") in ("quarantine", "reject"):
            G.append({"es": "Correo protegido contra suplantación (SPF y DMARC).", "en": "Email protected against forgery (SPF and DMARC)."})

    # --- links, content, housekeeping --------------------------------------------
    if links.get("broken"):
        b = links["broken"][0]
        F.append(_f("broken-links", "medium",
                    {"title": f"{len(links['broken'])} de {links['checked']} enlaces de la portada no funcionan", "saw": f"Por ejemplo {b['url']} devuelve {b['status']}.", "why": "Un visitante que pulsa y ve 'Página no encontrada' deja de confiar. Google también lo cuenta.", "see": f"Abra {b['url']}"},
                    {"title": f"{len(links['broken'])} of {links['checked']} home-page links do not work", "saw": f"For example {b['url']} returns {b['status']}.", "why": "A visitor who clicks and sees 'Page not found' stops trusting. Google counts it too.", "see": f"Open {b['url']}"},
                    [x["url"] for x in links["broken"][:3]]))
    elif links.get("checked"):
        G.append({"es": f"Los {links['checked']} enlaces internos comprobados funcionan.", "en": f"All {links['checked']} internal links checked work."})
    if page.get("mixedContent"):
        F.append(_f("mixed-content", "medium",
                    {"title": "Página segura con recursos inseguros", "saw": f"{page['mixedContent']} imágenes o scripts se cargan por http dentro de la página https.", "why": "El navegador quita el candado o bloquea esos recursos: imágenes que no salen, y el aviso de 'no es seguro'.", "see": "Mire el candado junto a la dirección."},
                    {"title": "Secure page with insecure resources", "saw": f"{page['mixedContent']} images or scripts load over http inside the https page.", "why": "The browser removes the padlock or blocks those resources: images that do not show, and the 'not secure' warning.", "see": "Look at the padlock next to the address."}))
    y = page.get("copyrightYear")
    if y and int(y) < dt.date.today().year - 1:
        F.append(_f("old-year", "low",
                    {"title": f"El pie de página dice © {y}", "saw": f"El año del copyright en el pie es {y}.", "why": "Es un detalle, pero le dice al visitante que nadie ha tocado la web en años.", "see": "Baje hasta el final de la portada."},
                    {"title": f"The footer says © {y}", "saw": f"The copyright year in the footer is {y}.", "why": "A detail, but it tells the visitor nobody has touched the site in years.", "see": "Scroll to the bottom of the home page."}))
    if page.get("imgs", 0) >= 4 and page.get("imgsNoAlt", 0) / max(page.get("imgs", 1), 1) > 0.5:
        F.append(_f("img-alt", "low",
                    {"title": "La mayoría de las imágenes no tienen texto alternativo", "saw": f"{page['imgsNoAlt']} de {page['imgs']} imágenes sin atributo alt.", "why": "Google Imágenes no sabe qué muestran, y los lectores de pantalla las saltan.", "see": "Es técnico."},
                    {"title": "Most images have no alternative text", "saw": f"{page['imgsNoAlt']} of {page['imgs']} images without an alt attribute.", "why": "Google Images does not know what they show, and screen readers skip them.", "see": "Technical."}))
    if not page.get("analytics"):
        F.append(_f("no-analytics", "low",
                    {"title": "La web no mide visitas", "saw": "No se detectó Google Analytics, Tag Manager, Matomo, Plausible ni Umami en la portada.", "why": "Nadie sabe cuánta gente entra ni de dónde viene. Cualquier decisión sobre la web se toma a ciegas.", "see": "Es técnico."},
                    {"title": "The site does not measure visits", "saw": "No Google Analytics, Tag Manager, Matomo, Plausible or Umami detected on the home page.", "why": "Nobody knows how many people come in or from where. Every decision about the site is taken blind.", "see": "Technical."}))
    elif not page.get("cookieBanner"):
        F.append(_f("no-cookie-banner", "low",
                    {"title": "Hay analítica pero no se ve aviso de cookies", "saw": f"Se detectó {', '.join(page['analytics'])} y ningún elemento de consentimiento de cookies en el código.", "why": "La AEPD multa por medir sin consentimiento. Las sanciones a pequeñas empresas rondan los 3.000 a 10.000 euros.", "see": "Abra la web en una ventana privada y mire si aparece el aviso."},
                    {"title": "Analytics present but no cookie notice seen", "saw": f"Detected {', '.join(page['analytics'])} and no cookie consent element in the code.", "why": "The Spanish data authority fines measurement without consent. Penalties for small companies run 3,000 to 10,000 euros.", "see": "Open the site in a private window and see whether the notice appears."}))
    if page.get("cms") == "WordPress" and page.get("version"):
        G.append({"es": f"WordPress {page['version']} (versión visible en el código; conviene ocultarla).", "en": f"WordPress {page['version']} (version visible in the code; better hidden)."})

    # --- SEO basics the owner can act on -------------------------------------------
    tl = page.get("titleLen", 0)
    if tl and (tl < 30 or tl > 65):
        F.append(_f("title-length", "low",
                    {"title": f"El título de la portada tiene {tl} caracteres", "saw": f"Título: '{t}'. Google muestra entre 50 y 60; menos de 30 desaprovecha el espacio, más de 65 se corta.", "why": "El título es lo que se lee en azul en Google. Es el sitio donde decir qué hace el negocio y dónde.", "see": "Busque el negocio en Google y mire si la línea azul se corta."},
                    {"title": f"The home page title is {tl} characters", "saw": f"Title: '{t}'. Google shows 50 to 60; under 30 wastes the space, over 65 gets cut.", "why": "The title is the blue line in Google. It is where to say what the business does and where.", "see": "Search the business on Google and see whether the blue line is cut."}))
    dl = len(page.get("metaDesc", ""))
    if dl and (dl < 70 or dl > 165):
        F.append(_f("desc-length", "low",
                    {"title": f"La meta descripción tiene {dl} caracteres", "saw": "Google muestra unos 150 a 160; menos de 70 queda corta, más de 165 se corta.", "why": "Son las dos líneas grises bajo el enlace. Deciden si alguien pulsa.", "see": "Busque el negocio en Google y lea las líneas grises."},
                    {"title": f"The meta description is {dl} characters", "saw": "Google shows about 150 to 160; under 70 is short, over 165 gets cut.", "why": "They are the two grey lines under the link. They decide whether someone clicks.", "see": "Search the business on Google and read the grey lines."}))
    if len(page.get("h1", [])) > 1:
        F.append(_f("many-h1", "low",
                    {"title": f"La portada tiene {len(page['h1'])} encabezados principales", "saw": "Hay más de una etiqueta <h1>: " + " | ".join(h[:40] for h in page["h1"][:3]), "why": "Google y los asistentes de IA usan el H1 como el titular de la página. Varios titulares diluyen el mensaje.", "see": "Es técnico."},
                    {"title": f"The home page has {len(page['h1'])} main headings", "saw": "There is more than one <h1> tag: " + " | ".join(h[:40] for h in page["h1"][:3]), "why": "Google and AI assistants use the H1 as the page's headline. Several headlines dilute the message.", "see": "Technical."}))
    if page.get("canonicalHref") and not page.get("canonicalOk"):
        F.append(_f("canonical-mismatch", "medium",
                    {"title": "La etiqueta canonical apunta a otra dirección", "saw": f"La portada declara como canónica {page['canonicalHref']}, que no es la dirección por la que se cargó.", "why": "Le está diciendo a Google que la página 'oficial' es otra. Puede hacer que Google muestre la dirección equivocada o ninguna.", "see": "Es técnico; se ve en el código fuente buscando 'canonical'."},
                    {"title": "The canonical tag points to a different address", "saw": f"The home page declares {page['canonicalHref']} as canonical, which is not the address it loaded from.", "why": "It tells Google the 'official' page is another one. Google may show the wrong address, or none.", "see": "Technical; visible in the page source searching for 'canonical'."}))
    wc = page.get("wordCount", 0)
    if wc < 80:
        F.append(_f("thin-content", "medium",
                    {"title": "La portada casi no tiene texto", "saw": f"{wc} palabras en la portada.", "why": "Google y los asistentes de IA no pueden recomendar lo que no pueden leer. Una portada solo de imágenes no posiciona para nada.", "see": "Seleccione todo el texto de la portada: ¿cabe en un párrafo?"},
                    {"title": "The home page has almost no text", "saw": f"{wc} words on the home page.", "why": "Google and AI assistants cannot recommend what they cannot read. An image-only home page ranks for nothing.", "see": "Select all the text on the home page: does it fit in one paragraph?"}))
    og = page.get("ogFields", {})
    if not any(og.values()):
        F.append(_f("no-og", "low",
                    {"title": "Sin vista previa al compartir en WhatsApp o redes", "saw": "No hay etiquetas Open Graph (og:title, og:description, og:image).", "why": "Cuando alguien comparte el enlace por WhatsApp, no sale ni imagen ni título. Se comparte menos y se pulsa menos.", "see": "Pegue la dirección de la web en un chat de WhatsApp y mire la vista previa."},
                    {"title": "No preview when shared on WhatsApp or social media", "saw": "No Open Graph tags (og:title, og:description, og:image).", "why": "When someone shares the link on WhatsApp, no image or title appears. It gets shared less and clicked less.", "see": "Paste the site address into a WhatsApp chat and look at the preview."}))
    if not page.get("favicon"):
        F.append(_f("no-favicon", "low",
                    {"title": "Sin icono de pestaña (favicon)", "saw": "No hay etiqueta de icono en el código.", "why": "En Google móvil el icono aparece junto al nombre del sitio. Sin él, sale un globo gris.", "see": "Mire la pestaña del navegador."},
                    {"title": "No tab icon (favicon)", "saw": "No icon tag in the code.", "why": "On mobile Google the icon appears next to the site name. Without it, a grey globe shows.", "see": "Look at the browser tab."}))

    # --- AI readiness -------------------------------------------------------------
    biz = page.get("biz", {})
    if biz.get("type"):
        missing = [k for k in ("address", "telephone", "openingHours", "sameAs") if not biz.get(k)]
        if missing:
            names = {"address": "dirección / address", "telephone": "teléfono / phone", "openingHours": "horario / hours", "sameAs": "perfiles sociales / social profiles"}
            F.append(_f("schema-incomplete", "low",
                        {"title": "La ficha del negocio en el código está incompleta", "saw": f"Hay una ficha {biz['type']} pero le faltan: {', '.join(names[m].split(' / ')[0] for m in missing)}.", "why": "Es lo que ChatGPT, Perplexity y Google leen para saber dónde está el negocio, cómo llamar y cuándo abre. Cada campo que falta es una pregunta que no pueden responder.", "see": "Es técnico; se comprueba con la herramienta de resultados enriquecidos de Google."},
                        {"title": "The business card in the code is incomplete", "saw": f"There is a {biz['type']} card but it lacks: {', '.join(names[m].split(' / ')[1] for m in missing)}.", "why": "It is what ChatGPT, Perplexity and Google read to know where the business is, how to call and when it opens. Each missing field is a question they cannot answer.", "see": "Technical; checked with Google's rich results test."},
                        [f"https://search.google.com/test/rich-results?url={primary}"]))
    if not page.get("faqSchema") and not page.get("faqHint") and not page.get("questionHeadings"):
        F.append(_f("no-faq", "low",
                    {"title": "La portada no responde preguntas", "saw": "No hay bloque de preguntas frecuentes ni encabezados en forma de pregunta.", "why": "Los asistentes de IA citan con preferencia páginas que responden preguntas concretas ('¿cuánto tarda…?', '¿atendéis en…?'). Cinco preguntas con respuestas cortas es la mejora más barata para aparecer en ChatGPT y Perplexity.", "see": "Pregunte a ChatGPT por un negocio como el suyo en su zona y vea a quién cita."},
                    {"title": "The home page answers no questions", "saw": "No FAQ block and no question-shaped headings.", "why": "AI assistants prefer to cite pages that answer concrete questions ('how long does…?', 'do you serve…?'). Five questions with short answers is the cheapest way to show up in ChatGPT and Perplexity.", "see": "Ask ChatGPT for a business like yours in your area and see who it cites."}))
    if not seo.get("llmsTxt"):
        F.append(_f("no-llms", "low",
                    {"title": "Sin llms.txt", "saw": "No existe /llms.txt en el dominio.", "why": "Es un archivo de texto nuevo (2024) donde la web explica a los modelos de IA qué es y qué páginas importan. Pocos lo tienen todavía; cuesta media hora y no hace daño.", "see": f"Abra {primary.rstrip('/')}/llms.txt"},
                    {"title": "No llms.txt", "saw": "There is no /llms.txt on the domain.", "why": "A new (2024) plain-text file where a site tells AI models what it is and which pages matter. Few have it yet; it takes half an hour and does no harm.", "see": f"Open {primary.rstrip('/')}/llms.txt"}))
    lm = page.get("landmarks", {})
    if sum(lm.values()) < 2 and wc >= 80:
        F.append(_f("no-landmarks", "low",
                    {"title": "El código no marca qué es cabecera, menú, contenido y pie", "saw": f"Etiquetas semánticas encontradas: {', '.join(k for k, v in lm.items() if v) or 'ninguna'}.", "why": "Los lectores de IA y los lectores de pantalla usan esas marcas para saber qué parte de la página es el contenido. Sin ellas, mezclan el menú con el texto.", "see": "Es técnico."},
                    {"title": "The code does not mark header, menu, content and footer", "saw": f"Semantic tags found: {', '.join(k for k, v in lm.items() if v) or 'none'}.", "why": "AI readers and screen readers use those marks to know which part of the page is the content. Without them they mix the menu with the text.", "see": "Technical."}))
    if ph.get("ok"):
        cls = ph.get("cls") or 0
        if cls > 0.25:
            F.append(_f("cls", "medium",
                        {"title": "La página salta mientras carga en el móvil", "saw": f"Desplazamiento acumulado (CLS) de {cls:.2f}; Google considera bueno hasta 0,10.", "why": "El visitante va a pulsar un botón y el botón se mueve. Google lo mide y lo penaliza.", "see": "Abra la web en el móvil y mire si el contenido se mueve al cargar."},
                        {"title": "The page jumps while loading on a phone", "saw": f"Cumulative layout shift (CLS) of {cls:.2f}; Google rates up to 0.10 as good.", "why": "The visitor goes to tap a button and the button moves. Google measures it and demotes for it.", "see": "Open the site on a phone and watch whether content moves while loading."}))
        kb = ph.get("kb") or 0
        if kb > 3500:
            F.append(_f("heavy", "medium",
                        {"title": f"La portada pesa {kb/1024:.1f} MB", "saw": f"{ph.get('requests', 0)} peticiones, {(ph.get('imageKb') or 0)/1024:.1f} MB en imágenes.", "why": "Con datos móviles, cada megabyte son segundos. Las imágenes sin comprimir son casi siempre la causa.", "see": "Abra la web con datos móviles y mire cuánto tarda la primera imagen grande."},
                        {"title": f"The home page weighs {kb/1024:.1f} MB", "saw": f"{ph.get('requests', 0)} requests, {(ph.get('imageKb') or 0)/1024:.1f} MB of images.", "why": "On mobile data every megabyte is seconds. Uncompressed images are almost always the cause.", "see": "Open the site on mobile data and watch how long the first big image takes."}))

    F.sort(key=lambda f: SEV_ORDER[f["severity"]])
    return {"findings": F, "good": G, "summary": _summary(F, a), "panels": build_panels(a)}


def _summary(F: list[dict], a: dict) -> dict:
    counts = {s: sum(1 for f in F if f["severity"] == s) for s in ("high", "medium", "low")}
    page = a.get("page", {})
    hdr = a.get("headers", {})
    dnsr = a.get("dns", {})
    tech = {
        "cms": (page.get("cms") or "") + (f" {page['version']}" if page.get("version") else ""),
        "builder": page.get("builder", ""),
        "server": hdr.get("server", ""),
        "cdn": "Cloudflare" if hdr.get("cfRay") else (hdr.get("via") or hdr.get("xCache") and "CDN" or ""),
        "hostingHint": dnsr.get("rdns", ""),
        "mail": (dnsr.get("mx") or [""])[0],
        "ip": (dnsr.get("a") or [""])[0],
    }
    if counts["high"]:
        verdict = {"es": f"{counts['high']} problema{'s' if counts['high'] > 1 else ''} grave{'s' if counts['high'] > 1 else ''} que le cuesta{'n' if counts['high'] > 1 else ''} clientes hoy.", "en": f"{counts['high']} serious problem{'s' if counts['high'] > 1 else ''} costing customers today."}
    elif counts["medium"]:
        verdict = {"es": f"Sin fallos graves. {counts['medium']} cosa{'s' if counts['medium'] > 1 else ''} que conviene arreglar este mes.", "en": f"No serious faults. {counts['medium']} thing{'s' if counts['medium'] > 1 else ''} worth fixing this month."}
    elif counts["low"]:
        verdict = {"es": "La web está bien. Solo detalles.", "en": "The site is fine. Details only."}
    else:
        verdict = {"es": "No encontramos nada que arreglar desde fuera.", "en": "We found nothing to fix from the outside."}
    return {"counts": counts, "verdict": verdict, "tech": tech}
