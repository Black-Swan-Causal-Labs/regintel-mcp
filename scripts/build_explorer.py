#!/usr/bin/env python3
"""Build explorer/<docket>/ : index.html (template + embedded logo) and its analysis.json.

    python scripts/build_explorer.py FDA-2020-D-2307
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
docket = sys.argv[1]
out = ROOT / "explorer" / docket
out.mkdir(parents=True, exist_ok=True)
logo = (ROOT / "explorer" / "assets" / "feather.b64").read_text().strip()
html = (ROOT / "explorer" / "template.html").read_text().replace("__FEATHER__", "data:image/png;base64," + logo)
# artifact.html: page body only (the claude.ai Artifact publisher adds the document skeleton).
(out / "artifact.html").write_text(html)
# index.html: standalone document for local use / GitHub Pages.
(out / "index.html").write_text(
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    '<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
    + html + "</body></html>")
shutil.copy(ROOT / "output" / docket / "analysis.json", out / "analysis.json")
print(f"built {out}")
