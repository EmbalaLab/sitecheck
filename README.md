# SiteCheck

Type a web address. Half a minute later you get a page that says what is wrong with the site's home page, in the order it costs the owner money, in Spanish or English. Live at [webaudit.embalalab.com](https://webaudit.embalalab.com).

## What a result looks like

A verdict in one sentence. Three scores out of 100: Google and SEO, AI assistants, speed and mobile. A radar chart with six axes that puts the site next to a reference line and next to the average of other local sites. A phone screenshot. Then the findings, each with three parts: what we saw, why it matters, how to check it yourself.

## What it checks

The home page only, once, from outside, with no login. Roughly:

- Does it load over https, is the certificate valid, does http redirect.
- How it looks and how long it takes on an emulated Pixel 7: LCP, full load, layout shift, page weight, font size, sideways scroll.
- Can a visitor call or write on WhatsApp with one tap. Is the phone number on the page.
- What Google reads: title, description, headings, canonical, robots, sitemap, structured data, Open Graph, favicon, alt text.
- Whether AI crawlers (GPTBot, ClaudeBot, PerplexityBot and others) are allowed in, whether the text exists without running scripts, llms.txt, how complete the schema.org business card is, whether the page answers questions.
- Mail records: MX, SPF, DMARC.
- A sample of internal links, mixed content, script errors, the CMS and the page builder.

It does not crawl past the home page, does not submit forms, and knows nothing about traffic or rankings. The result page says so.

## The local average

The grey line on the radar is the mean of sites we ran through this same engine. The list of URLs is in `data/benchmark-sites.txt`, the numbers in `data/benchmark.json`, with the count and the date. No average is ever typed in by hand. If the file is missing, the chart shows the site and the reference only.

```
python -m audit.benchmark run data/benchmark-sites.txt ./bench-runs
python -m audit.benchmark aggregate ./bench-runs data/benchmark.json
```

## Run it

```
pip install -r requirements.txt && playwright install chromium
python -m audit.cli example.com ./runs/example     # one site, writes index.html next to the data
uvicorn app:app --port 3000                        # the web service
```

Docker: `docker-compose.kali.yml` runs it as one container with one browser at a time, five new runs per IP per hour, and a six hour cache per host.

## Code

`audit/engine.py` fetches and measures. `audit/findings.py` turns measurements into findings. `audit/panels.py` scores the three areas and the six radar axes. `audit/charts.py` computes the chart geometry (inline SVG, no library). `audit/benchmark.py` builds the local average. `templates/` and `static/app.css` are the page.

MIT licence. Made by EmbalaLab in Alhaurín de la Torre, Málaga.
