"""SiteCheck web service: paste a URL, get a diagnosis card.

POST /api/audit {url}        -> {id, status}   (queued; cached result reused for 6 h)
GET  /api/audit/{id}         -> {status, step, url}
GET  /r/{id}                 -> result card (HTML), /r/{id}/<file>.png screenshots
GET  /                       -> the form
GET  /healthz                -> ok

One browser at a time; five new audits per IP per hour; results kept on disk under DATA_DIR.
"""
from __future__ import annotations

import asyncio
import collections
import json
import os
import pathlib
import re
import secrets
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from jinja2 import Environment, FileSystemLoader, select_autoescape

from audit.engine import norm_host, run_audit
from audit.findings import build_findings
from audit.render import render_html

HERE = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.environ.get("DATA_DIR", HERE / "data"))
DATA.mkdir(parents=True, exist_ok=True)
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", 6 * 3600))
PER_IP_PER_HOUR = int(os.environ.get("PER_IP_PER_HOUR", 5))
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "kali", "embalalab.com"}

app = FastAPI(title="EmbalaLab SiteCheck", docs_url=None, redoc_url=None)
env = Environment(loader=FileSystemLoader(str(HERE / "templates")), autoescape=select_autoescape(["html"]))
jobs: dict[str, dict] = {}
by_host: dict[str, str] = {}
ip_log: dict[str, collections.deque] = collections.defaultdict(collections.deque)
sem = asyncio.Semaphore(1)


def _client_ip(req: Request) -> str:
    return req.headers.get("cf-connecting-ip") or req.headers.get("x-forwarded-for", "").split(",")[0].strip() or (req.client.host if req.client else "?")


def _valid_host(h: str) -> bool:
    if not h or h in BLOCKED_HOSTS or "." not in h or len(h) > 253:
        return False
    if re.match(r"^(\d{1,3}\.){3}\d{1,3}$", h):
        return False
    return bool(re.match(r"^[a-z0-9.-]+$", h))


async def _worker(job_id: str):
    job = jobs[job_id]
    outdir = DATA / job_id
    async with sem:
        job["status"] = "running"
        try:
            def prog(step):
                job["step"] = step
            audit = await run_audit(job["host"], outdir, prog)
            report = build_findings(audit)
            (outdir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            render_html(audit, report, outdir, inline_images=False, file_base=f"/r/{job_id}/")
            job.update(status="done", step="done", finished=time.time())
        except Exception as e:  # noqa: BLE001
            job.update(status="error", step="error", error=f"{type(e).__name__}: {str(e)[:200]}", finished=time.time())


@app.exception_handler(StarletteHTTPException)
async def _no_store_errors(request, exc):
    # Cloudflare caches a 404 on image paths for hours; a file requested a second too early would stay invisible.
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers={"Cache-Control": "no-store"})


@app.get("/healthz")
async def healthz():
    return {"ok": True, "jobs": len(jobs)}


EXAMPLE_IDS = [x.strip() for x in os.environ.get("EXAMPLE_IDS", "").split(",") if x.strip()]


def _examples() -> list[dict]:
    """Cards for the home page: real runs on this service, chosen by id (EXAMPLE_IDS). A card is shown only
    while its result files still exist; nothing is fabricated for a missing run."""
    out = []
    for job_id in EXAMPLE_IDS:
        d = DATA / job_id
        try:
            a = json.loads((d / "audit.json").read_text(encoding="utf-8"))
            r = json.loads((d / "report.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not (d / "index.html").exists():
            continue
        s = r.get("summary", {})
        out.append({"id": job_id, "host": a.get("host"), "date": (a.get("checkedAt") or "")[:10], "verdict": s.get("verdict", {}),
                    "counts": s.get("counts", {}), "scores": (r.get("panels") or {}).get("scores", {}), "reachable": a.get("reachable"),
                    "shot": f"/r/{job_id}/phone-fold.png" if (d / "phone-fold.png").exists() else ""})
    return out


@app.get("/", response_class=HTMLResponse)
async def home():
    return env.get_template("home.html").render(css=(HERE / "static" / "app.css").read_text(encoding="utf-8"), examples=_examples())


@app.post("/api/audit")
async def create(req: Request):
    body = await req.json()
    host = norm_host(str(body.get("url", "")))
    if not _valid_host(host):
        raise HTTPException(400, "Escriba una dirección web válida, por ejemplo minegocio.es")
    cached = by_host.get(host)
    if cached and jobs.get(cached, {}).get("status") == "done" and time.time() - jobs[cached]["finished"] < CACHE_SECONDS and not body.get("force"):
        return {"id": cached, "status": "done", "cached": True}
    ip = _client_ip(req)
    q = ip_log[ip]
    now = time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= PER_IP_PER_HOUR:
        raise HTTPException(429, "Cinco diagnósticos por hora por persona. Vuelva en un rato.")
    q.append(now)
    job_id = secrets.token_urlsafe(8)
    jobs[job_id] = {"id": job_id, "host": host, "status": "queued", "step": "queued", "created": now, "ip": ip}
    by_host[host] = job_id
    asyncio.create_task(_worker(job_id))
    return {"id": job_id, "status": "queued"}


@app.get("/api/audit/{job_id}")
async def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        if (DATA / job_id / "index.html").exists():
            return {"id": job_id, "status": "done", "step": "done"}
        raise HTTPException(404)
    return {k: job.get(k) for k in ("id", "host", "status", "step", "error")}


@app.get("/r/{job_id}", response_class=HTMLResponse)
async def result(job_id: str):
    p = DATA / job_id / "index.html"
    if not re.match(r"^[A-Za-z0-9_-]{6,24}$", job_id) or not p.exists():
        raise HTTPException(404)
    return HTMLResponse(p.read_text(encoding="utf-8"), headers={"Cache-Control": "private, max-age=300"})


@app.get("/r/{job_id}/{name}")
async def result_file(job_id: str, name: str):
    if not re.match(r"^[A-Za-z0-9_-]{6,24}$", job_id) or not re.match(r"^(phone-fold|phone-full|desktop-fold)\.png|(audit|report)\.json$", name):
        raise HTTPException(404)
    p = DATA / job_id / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@app.on_event("startup")
async def _restore():
    """Make results on disk addressable after a restart (status only; no re-run)."""
    for d in DATA.iterdir():
        if (d / "index.html").exists():
            try:
                a = json.loads((d / "audit.json").read_text(encoding="utf-8"))
                jobs[d.name] = {"id": d.name, "host": a.get("host"), "status": "done", "step": "done", "finished": (d / "index.html").stat().st_mtime}
                by_host.setdefault(a.get("host"), d.name)
            except Exception:  # noqa: BLE001
                continue
