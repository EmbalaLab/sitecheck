"""CLI: python -m audit.cli <url> <outdir>   -> outdir/audit.json, report.json, index.html, screenshots"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import time

from .engine import run_audit
from .findings import build_findings
from .render import render_html


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    url, outdir = sys.argv[1], pathlib.Path(sys.argv[2])
    t0 = time.perf_counter()

    def prog(step):
        print(f"  {time.perf_counter() - t0:5.1f}s  {step}", flush=True)

    audit = asyncio.run(run_audit(url, outdir, prog))
    report = build_findings(audit)
    (outdir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    render_html(audit, report, outdir)
    s = report["summary"]
    print(f"done in {audit.get('elapsedMs', 0) / 1000:.1f}s: {s['counts']} -> {outdir / 'index.html'}")
    for f in report["findings"]:
        print(f"  [{f['severity']:6}] {f['en']['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
