#!/usr/bin/env python3
"""Validate analysis.json: JSON Schema + referential integrity + verbatim spans.

    python scripts/validate_analysis.py output/FDA-2020-D-2307/analysis.json [--corpus output/.../corpus.jsonl]
"""
import json
import re
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main(path, corpus=None):
    a = json.loads(Path(path).read_text())
    errs = [f"schema: {e.json_path}: {e.message}" for e in
            jsonschema.Draft202012Validator(json.loads((ROOT / "docs/analysis-schema.json").read_text())).iter_errors(a)]
    subs = {s["submitter_id"] for s in a.get("submitters", [])}
    coms = {c["comment_id"] for c in a.get("comments", [])}
    themes = {t["theme_id"] for t in a.get("themes", [])}
    asks = {x["ask_id"] for x in a.get("asks", [])}
    secs = {s["section_id"] for s in a.get("sections", [])}
    errs += [f"comment {c['comment_id']}: unknown submitter" for c in a.get("comments", []) if c["submitter_id"] not in subs]
    errs += [f"ask {x['ask_id']}: unknown comment/theme" for x in a.get("asks", [])
             if x["comment_id"] not in coms or x["theme_id"] not in themes]
    errs += [f"concordance {c['ask_id']}: unknown ask/section" for c in a.get("concordance", [])
             if c["ask_id"] not in asks or (c["section_id"] and c["section_id"] not in secs)]
    final_text = ws(" ".join(s.get("final_text") or "" for s in a.get("sections", [])))
    errs += [f"concordance {c['ask_id']}: evidence_span not verbatim in final" for c in a.get("concordance", [])
             if c.get("evidence_span") and ws(c["evidence_span"]) not in final_text]
    if corpus:
        texts = {}
        for line in Path(corpus).read_text().splitlines():
            c = json.loads(line)
            texts[c["commentId"]] = ws(" ".join([c.get("body") or ""] + [x.get("text") or "" for x in c["attachments"]]))
        errs += [f"ask {x['ask_id']}: source_span not verbatim in comment" for x in a.get("asks", [])
                 if ws(x["source_span"]) not in texts.get(x["comment_id"], "")]
    print("\n".join(errs) if errs else f"OK: {len(a.get('asks', []))} asks, {len(a.get('concordance', []))} calls")
    return 1 if errs else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    corpus = args[args.index("--corpus") + 1] if "--corpus" in args else None
    sys.exit(main(args[0], corpus))
