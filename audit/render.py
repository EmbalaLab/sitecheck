"""Render an audit result (facts + findings) to a standalone HTML card."""
from __future__ import annotations

import base64
import json
import pathlib

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"


def _b64(p: pathlib.Path) -> str:
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def render_html(audit: dict, report: dict, outdir: pathlib.Path, inline_images: bool = True, file_base: str = "") -> str:
    """file_base: URL prefix for screenshots when not inlined, e.g. "/r/<id>/" (the card lives at /r/<id>, so a
    bare relative name would resolve one level too high)."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    tpl = env.get_template("result.html")
    css = (HERE.parent / "static" / "app.css").read_text(encoding="utf-8")
    shots = {}
    for k in ("phone-fold", "phone-full", "desktop-fold"):
        p = outdir / f"{k}.png"
        shots[k] = ("data:image/png;base64," + _b64(p)) if (inline_images and p.exists()) else (f"{file_base}{k}.png" if p.exists() else "")
    html = tpl.render(a=audit, r=report, shots=shots, css=css, raw=json.dumps({k: v for k, v in audit.items() if k != "variants"}, ensure_ascii=False, indent=1))
    (outdir / "index.html").write_text(html, encoding="utf-8")
    return html
