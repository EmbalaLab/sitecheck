# SiteCheck — one-minute website diagnosis

Paste a URL, get a card: what is wrong with the home page, ordered by what it costs the business, in Spanish and English, with a phone screenshot, a radar chart against the standard and the local average, and the measured facts behind every finding. Public at webaudit.embalalab.com (a free tool by EmbalaLab; the old hostname audit.embalalab.com redirects there).

What it measures (home page only, one run, from the outside), shown as findings ordered by business cost plus three scorecards:

- **Google and SEO basics**: title and description length, one H1 and H2s, canonical consistency, noindex, robots.txt, sitemap (URL count, last modification), https and redirect, www consistency, `lang`, Open Graph, favicon, word count, image alt coverage, business structured data, breadcrumbs, hreflang.
- **Ready for AI assistants**: robots.txt access for GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended, Meta-ExternalAgent and others; text present without running scripts (raw vs rendered); `llms.txt`; completeness of the schema.org business card (address, phone, hours, sameAs, geo); FAQ (FAQPage schema or question headings); clear H1 and subheadings; first explanatory paragraph; semantic landmarks; sameAs profiles; WebSite SearchAction; Open Graph for chat previews.
- **Speed and mobile**: LCP, full load, CLS, page weight and request count, third-party requests, sideways scroll, body font size, compression, HSTS, server response time, all on an emulated Pixel 7 and a desktop.
- Plus: certificate validity and expiry, mail records (MX, SPF, DMARC), tap-to-call and WhatsApp links, phone numbers in text, forms, analytics and cookie banner, mixed content, a sample of internal links, console errors (site's own resources only), CMS and builder detection.

Scores are checks passed over checks that could run, measured once. They are our list, not a Google grade.

## Charts

- **Radar, six axes 0-100**: Security (https, redirect, certificate, mixed content, HSTS), Mobile (viewport, sideways scroll, font size, CLS), Speed (LCP, load, weight, server response), Google/SEO (the SEO scorecard), AI (the AI scorecard), Contact (tap-to-call, WhatsApp, phone in text, form or mailto). The formula is in `audit/panels.py` (`build_axes`): each axis is the mean of its parts scored 1 / 0.5 / 0; parts that could not be measured are left out, never counted as 0. Three series: this site; the **standard** (100 on every axis: a site that passes every check, with Google's published Core Web Vitals thresholds, LCP ≤ 2.5 s and CLS ≤ 0.1); and the **local average**.
- **Speed bullets**: LCP, full load, weight and server response as bars against the thresholds (LCP per Google; the others are our scorecard limits) with the local median as a tick.
- **Per-check pass rates**: each scorecard row shows the share of local sites that pass it.

The charts are inline SVG and HTML drawn from numbers computed in `audit/charts.py`; no chart library, no CDN. They work in light and dark and on a 412 px phone.

## The local average is measured, never typed in

`data/benchmark.json` is produced by running this same engine over `data/benchmark-sites.txt` (public business websites in the province of Málaga, URLs only, no names or phone numbers):

```
python -m audit.benchmark run data/benchmark-sites.txt ./bench-runs      # one browser at a time, ~25 s per site
python -m audit.benchmark aggregate ./bench-runs data/benchmark.json     # per-axis means, per-check pass rates, speed medians, N, as-of
```

The result page's legend states N and the measurement date. If the file is missing, the chart shows only the site and the standard and says the average has not been measured; it never shows a made-up number. Sites that did not respond are counted in `nTotal` but excluded from every average.

What it does not do: crawl beyond the home page, test forms, estimate traffic or rankings. The result page says so.

```
pip install -r requirements.txt && playwright install chromium
python -m audit.cli example.com ./runs/example   # -> audit.json, report.json, index.html, screenshots
uvicorn app:app --port 3000                      # the web service; EXAMPLE_IDS=id1,id2 shows real runs as example cards on the home page
```

Layout: `audit/engine.py` measures, `audit/findings.py` judges (ES/EN rules, no LLM), `audit/panels.py` builds the scorecards and the six axes, `audit/charts.py` computes chart geometry, `audit/benchmark.py` measures the local average, `audit/render.py` + `templates/` + `static/app.css` present. Tokens in app.css are copied from `StartLab/shared/design-system/embalalab/colors_and_type.css`.
