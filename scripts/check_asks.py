#!/usr/bin/env python3
"""Check coded asks: schema fields, theme/stance values, and verbatim source spans.

    python scripts/check_asks.py output/FDA-2020-D-2307/asks/batch_1.json [more.json ...]
Exits non-zero and lists every failing ask_id.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STANCES = {"requests more specificity", "requests more flexibility", "supports as written", "objects"}


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main(paths):
    first = json.loads(Path(paths[0]).read_text())
    docket = first["asks"][0]["comment_id"].rsplit("-", 1)[0] if first.get("asks") else None
    out = ROOT / "output" / docket
    themes = {t["theme_id"] for t in json.loads((out / "codebook.json").read_text())["themes"]} | {"T99"}
    texts = {}
    for line in (out / "corpus.jsonl").read_text().splitlines():
        c = json.loads(line)
        texts[c["commentId"]] = ws(" ".join([c.get("body") or ""] + [a.get("text") or "" for a in c["attachments"]]))
    bad, n = [], 0
    for p in paths:
        for a in json.loads(Path(p).read_text())["asks"]:
            n += 1
            probs = []
            if a.get("theme_id") not in themes:
                probs.append(f"theme {a.get('theme_id')}")
            if a.get("stance") not in STANCES:
                probs.append(f"stance {a.get('stance')!r}")
            if not a.get("source_span") or ws(a["source_span"]) not in texts.get(a.get("comment_id"), ""):
                probs.append("source_span not verbatim")
            if not re.fullmatch(re.escape(a.get("comment_id", "")) + r"-A\d{2,3}", a.get("ask_id", "")):
                probs.append("ask_id format")
            if probs:
                bad.append(f"{a.get('ask_id')}: {', '.join(probs)}")
    print("\n".join(bad) if bad else f"OK: {n} asks")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
