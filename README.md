# SiteCheck — one-minute website diagnosis

Paste a URL, get a card: what is wrong with the home page, ordered by what it costs the business, in Spanish and English, with a phone screenshot and the measured facts behind every finding. Public at audit.embalalab.com (deploy in progress, 2026-10-12).

What it measures (home page only, one run, from the outside): https and certificate, http→https redirect, www consistency, DNS and mail records (MX, SPF, DMARC), title, description, H1, viewport, noindex, CMS and builder, structured data, tap-to-call and WhatsApp links, phone numbers in text, forms, analytics and cookie banner, mixed content, robots.txt (incl. AI crawlers), sitemap, llms.txt, a sample of internal links, and a Playwright render on an emulated Pixel 7 and a desktop: load time, LCP, overflow, console errors, rendered text vs raw text.

What it does not do: crawl beyond the home page, test forms, estimate traffic or rankings. The result page says so.

```
pip install -r requirements.txt && playwright install chromium
python -m audit.cli example.com ./runs/example   # -> audit.json, report.json, index.html, screenshots
```

Layout: `audit/engine.py` measures, `audit/findings.py` judges (ES/EN rules, no LLM), `audit/render.py` + `templates/result.html` + `static/app.css` present. Tokens in app.css are copied from `StartLab/shared/design-system/embalalab/colors_and_type.css`.
