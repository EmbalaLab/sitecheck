"""Chart geometry for the result page: a six-axis radar and bullet bars for the speed figures.

Pure functions, no drawing library. The template draws inline SVG/HTML from the numbers
returned here, so the page needs no JavaScript to show the charts and no CDN at all.
Every value comes from the audit (this site), from Google's published Core Web Vitals
thresholds (the standard), or from data/benchmark.json (the local average, measured by
audit/benchmark.py). Nothing here invents a number: a missing measurement stays None.
"""
from __future__ import annotations

import math

from .panels import AXES

# Google Core Web Vitals thresholds (web.dev/articles/lcp, web.dev/articles/cls): good / poor.
# Load, weight and server response are our own limits, the same ones the speed scorecard uses.
SPEED_FIELDS = [
    # key, es, en, unit, good, poor, source
    ("lcpMs", "Contenido principal visible (LCP)", "Main content visible (LCP)", "s", 2500, 4000, "google"),
    ("loadMs", "Carga completa", "Full load", "s", 3000, 6000, "ours"),
    ("kb", "Peso de la portada", "Home page weight", "MB", 1500, 3500, "ours"),
    ("responseMs", "Respuesta del servidor", "Server response", "ms", 800, 2000, "ours"),
]


def fmt(key: str, v: float | None, lang: str = "es") -> str:
    if v is None:
        return "n/d" if lang == "es" else "n/a"
    if key in ("lcpMs", "loadMs"):
        s = f"{v / 1000:.1f}"
        return (s.replace(".", ",") if lang == "es" else s) + " s"
    if key == "kb":
        s = f"{v / 1024:.1f}"
        return (s.replace(".", ",") if lang == "es" else s) + " MB"
    return f"{int(round(v))} ms"


def radar(axes: dict, bench: dict | None, width: int = 520, height: int = 440, r: float = 140.0) -> dict:
    """Points for the three series on a hexagonal grid. Angles start at the top and go clockwise.
    The box is wider than tall so the side labels (anchored start/end) stay inside the viewBox."""
    cx, cy = width / 2, height / 2 + 2
    n = len(AXES)

    def pt(i: int, value: float) -> tuple[float, float]:
        ang = -math.pi / 2 + i * 2 * math.pi / n
        rr = r * max(0.0, min(100.0, value)) / 100.0
        return round(cx + rr * math.cos(ang), 1), round(cy + rr * math.sin(ang), 1)

    rings = [" ".join(f"{x},{y}" for x, y in (pt(i, lvl) for i in range(n))) for lvl in (25, 50, 75, 100)]
    spokes = [(cx, cy, *pt(i, 100)) for i in range(n)]
    labels = []
    for i, (key, es, en) in enumerate(AXES):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        lx, ly = cx + (r + 34) * math.cos(ang), cy + (r + 34) * math.sin(ang)
        anchor = "middle" if abs(math.cos(ang)) < 0.3 else ("start" if math.cos(ang) > 0 else "end")
        site = (axes.get(key) or {}).get("score")
        avg = ((bench or {}).get("axes") or {}).get(key, {}).get("mean") if bench else None
        labels.append({"key": key, "es": es, "en": en, "x": round(lx, 1), "y": round(ly, 1), "anchor": anchor, "site": site, "avg": avg,
                       "px": pt(i, site)[0] if site is not None else None, "py": pt(i, site)[1] if site is not None else None,
                       "ax": pt(i, avg)[0] if avg is not None else None, "ay": pt(i, avg)[1] if avg is not None else None,
                       "parts": (axes.get(key) or {}).get("parts", [])})
    site_pts = [(l["px"], l["py"]) for l in labels if l["px"] is not None]
    avg_pts = [(l["ax"], l["ay"]) for l in labels if l["ax"] is not None]
    return {
        "width": width, "height": height, "cx": cx, "cy": cy, "r": r, "rings": rings, "spokes": spokes, "labels": labels,
        "site": " ".join(f"{x},{y}" for x, y in site_pts) if len(site_pts) >= 3 else "",
        "avg": " ".join(f"{x},{y}" for x, y in avg_pts) if len(avg_pts) >= 3 else "",
        "standard": rings[-1],
        "siteMeasured": len(site_pts), "avgMeasured": len(avg_pts),
    }


def bullets(audit: dict, bench: dict | None) -> list[dict]:
    """One row per speed figure: the site's value as a bar, Google's/our thresholds as bands, the local median as a tick."""
    ph = ((audit.get("render") or {}).get("phone") or {}) if isinstance(audit.get("render"), dict) else {}
    out = []
    for key, es, en, unit, good, poor, source in SPEED_FIELDS:
        v = audit.get("responseMs") if key == "responseMs" else (ph.get(key) if ph.get("ok") else None)
        v = float(v) if v else None
        m = ((bench or {}).get("metrics") or {}).get(key) if bench else None
        median = float(m["median"]) if m and m.get("median") else None
        scale = max(poor * 1.3, (v or 0) * 1.15, (median or 0) * 1.15)
        pc = lambda x: round(100 * min(x, scale) / scale, 1)  # noqa: E731
        out.append({
            "key": key, "es": es, "en": en, "unit": unit, "source": source,
            "value": v, "valueEs": fmt(key, v, "es"), "valueEn": fmt(key, v, "en"),
            "status": None if v is None else ("ok" if v <= good else "warn" if v <= poor else "fail"),
            "goodPc": pc(good), "poorPc": pc(poor), "valuePc": pc(v) if v is not None else None, "clipped": bool(v and v > scale),
            "goodEs": fmt(key, good, "es"), "goodEn": fmt(key, good, "en"), "poorEs": fmt(key, poor, "es"), "poorEn": fmt(key, poor, "en"),
            "median": median, "medianPc": pc(median) if median is not None else None, "medianEs": fmt(key, median, "es"), "medianEn": fmt(key, median, "en"),
            "medianN": m.get("n") if m else None,
        })
    return out
