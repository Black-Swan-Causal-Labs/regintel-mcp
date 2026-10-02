#!/usr/bin/env python3
"""Check concordance calls: required fields, call values, verbatim evidence in the FINAL guidance text.

    python scripts/check_concordance.py output/FDA-2020-D-2307/concordance/batch_1.json
"""
import json
import re
import sys
from pathlib import Path

CALLS = {"adopted", "partially adopted", "not adopted", "not assessable"}


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main(path):
    p = Path(path)
    final = ws(re.sub(r"^### .*$", " ", (p.parent / "final_text.md").read_text(), flags=re.M))
    sections = set(re.findall(r"^### \[([^\]]+)\]", (p.parent / "final_text.md").read_text(), flags=re.M))
    batch = p.name.split(".")[0]
    expected = {a["ask_id"] for a in json.loads((p.parent / f"{batch}.asks.json").read_text())}
    got, bad = set(), []
    for c in json.loads(p.read_text())["concordance"]:
        got.add(c.get("ask_id"))
        probs = []
        if c.get("call") not in CALLS:
            probs.append(f"call {c.get('call')!r}")
        if c.get("section_id") and c["section_id"] not in sections:
            probs.append(f"unknown final section {c['section_id']}")
        if c.get("evidence_span") and ws(c["evidence_span"]) not in final:
            probs.append("evidence_span not verbatim in final")
        if c.get("call") in ("adopted", "partially adopted") and not c.get("evidence_span"):
            probs.append("adopted/partial needs evidence_span")
        if not c.get("rationale"):
            probs.append("no rationale")
        if probs:
            bad.append(f"{c.get('ask_id')}: {', '.join(probs)}")
    bad += [f"{a}: missing call" for a in sorted(expected - got)]
    bad += [f"{a}: not in this batch" for a in sorted(got - expected)]
    print("\n".join(bad) if bad else f"OK: {len(got)} calls")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
