# SiteCheck — one-minute website diagnosis

Paste a URL, get a card: what is wrong with the home page, ordered by what it costs the business, in Spanish and English, with a phone screenshot and the measured facts behind every finding. Public at audit.embalalab.com (deploy in progress, 2026-10-12).

What it measures (home page only, one run, from the outside), shown as findings ordered by business cost plus three scorecards:

- **Google and SEO basics**: title and description length, one H1 and H2s, canonical consistency, noindex, robots.txt, sitemap (URL count, last modification), https and redirect, www consistency, `lang`, Open Graph, favicon, word count, image alt coverage, business structured data, breadcrumbs, hreflang.
- **Ready for AI assistants**: robots.txt access for GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended, Meta-ExternalAgent and others; text present without running scripts (raw vs rendered); `llms.txt`; completeness of the schema.org business card (address, phone, hours, sameAs, geo); FAQ (FAQPage schema or question headings); clear H1 and subheadings; first explanatory paragraph; semantic landmarks; sameAs profiles; WebSite SearchAction; Open Graph for chat previews.
- **Speed and mobile**: LCP, full load, CLS, page weight and request count, third-party requests, sideways scroll, body font size, compression, HSTS, server response time, all on an emulated Pixel 7 and a desktop.
- Plus: certificate validity and expiry, mail records (MX, SPF, DMARC), tap-to-call and WhatsApp links, phone numbers in text, forms, analytics and cookie banner, mixed content, a sample of internal links, console errors (site's own resources only), CMS and builder detection.

Scores are checks passed over checks that could run, measured once. They are our list, not a Google grade.

What it does not do: crawl beyond the home page, test forms, estimate traffic or rankings. The result page says so.

```
pip install -r requirements.txt && playwright install chromium
python -m audit.cli example.com ./runs/example   # -> audit.json, report.json, index.html, screenshots
```

Layout: `audit/engine.py` measures, `audit/findings.py` judges (ES/EN rules, no LLM), `audit/render.py` + `templates/result.html` + `static/app.css` present. Tokens in app.css are copied from `StartLab/shared/design-system/embalalab/colors_and_type.css`.
