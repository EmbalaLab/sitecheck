"""Local benchmark: run the engine over a list of public sites and aggregate the results.

    python -m audit.benchmark run data/benchmark-sites.txt <workdir>      # one browser at a time, ~25 s per site
    python -m audit.benchmark aggregate <workdir> data/benchmark.json     # per-axis means, per-check pass rates, speed medians

The aggregate is what the result page compares a site against ("media de N webs de la provincia de Malaga,
medida el YYYY-MM-DD"). Every number in benchmark.json comes from an audit.json written by `run`; nothing is
typed in. Sites that could not be reached are counted in `nTotal` but excluded from every average.
The input file holds URLs only (one per line, `#` comments allowed), never names or phone numbers.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import pathlib
import statistics
import sys
import time

from .engine import norm_host, run_audit
from .panels import AXES, build_panels


def _sites(path: pathlib.Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


async def _run(sites: list[str], work: pathlib.Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    for i, url in enumerate(sites, 1):
        host = norm_host(url)
        out = work / host
        if (out / "audit.json").exists():
            print(f"[{i}/{len(sites)}] {host}: cached", flush=True)
            continue
        t0 = time.perf_counter()
        try:
            a = await run_audit(url, out)
            print(f"[{i}/{len(sites)}] {host}: reachable={a.get('reachable')} in {time.perf_counter() - t0:.0f}s", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(sites)}] {host}: ERROR {type(e).__name__}: {str(e)[:120]}", flush=True)


def _q(v: list[float], frac: float, nd: int) -> float:
    return round(sorted(v)[min(len(v) - 1, int(len(v) * frac))], nd)


def aggregate(work: pathlib.Path, out: pathlib.Path, region: str = "provincia de Málaga") -> dict:
    audits = []
    for d in sorted(work.iterdir()):
        f = d / "audit.json"
        if f.exists():
            try:
                audits.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
    reachable = [a for a in audits if a.get("reachable")]
    axes_vals: dict[str, list[int]] = {k: [] for k, _, _ in AXES}
    rows: dict[str, dict] = {}
    metrics: dict[str, list[float]] = {"lcpMs": [], "loadMs": [], "kb": [], "responseMs": [], "cls": []}
    for a in reachable:
        p = build_panels(a)
        for k, _, _ in AXES:
            sc = (p.get("axes") or {}).get(k, {}).get("score")
            if sc is not None:
                axes_vals[k].append(sc)
        for section in ("seo", "ai", "speed"):
            for r in p.get(section, []):
                if r["status"] == "na":
                    continue
                row = rows.setdefault(r["key"], {"pass": 0, "n": 0, "section": section})
                row["n"] += 1
                row["pass"] += 1 if r["status"] == "ok" else 0
        ph = (a.get("render") or {}).get("phone") or {}
        if ph.get("ok"):
            for m in ("lcpMs", "loadMs", "kb", "cls"):
                v = ph.get(m)
                if v is not None and (v or m == "cls"):  # a CLS of 0 is a real measurement; a 0 ms LCP means it was not observed
                    metrics[m].append(float(v))
        if a.get("responseMs"):
            metrics["responseMs"].append(float(a["responseMs"]))
    checked = sorted((a.get("checkedAt") or "")[:10] for a in reachable)
    result = {
        "asOf": checked[-1] if checked else dt.date.today().isoformat(),
        "firstRun": checked[0] if checked else "",
        "region": region,
        "nTotal": len(audits),
        "n": len(reachable),
        "axes": {k: {"mean": round(statistics.fmean(v)) if v else None, "median": round(statistics.median(v)) if v else None, "n": len(v)} for k, v in axes_vals.items()},
        "rows": rows,
        "metrics": {k: ({"median": round(statistics.median(v), 3 if k == "cls" else 0), "p25": _q(v, 0.25, 3 if k == "cls" else 0), "p75": _q(v, 0.75, 3 if k == "cls" else 0), "n": len(v)} if v else None) for k, v in metrics.items()},
        "hosts": sorted(a.get("host", "") for a in reachable),
        "unreachable": sorted(a.get("host", "") for a in audits if not a.get("reachable")),
        "tool": (reachable or audits or [{}])[0].get("tool", ""),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "run":
        asyncio.run(_run(_sites(pathlib.Path(sys.argv[2])), pathlib.Path(sys.argv[3])))
        return 0
    if cmd == "aggregate":
        r = aggregate(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]))
        print(json.dumps({k: r[k] for k in ("asOf", "n", "nTotal", "axes", "metrics")}, ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
