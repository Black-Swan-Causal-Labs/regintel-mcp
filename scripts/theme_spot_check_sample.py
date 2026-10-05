#!/usr/bin/env python3
"""Draw the seeded theme-coding spot-check sample for one docket (Checkpoint 4).

    python scripts/theme_spot_check_sample.py FDA-2021-D-0548 [--frac 0.15] [--seed 20261004]

Stratified by theme_id in proportion to the population, then shuffled with the same seed, so any
prefix the reviewer completes is itself a random sample. Writes output/<docket>/theme_spot_check_sample.json.
"""
import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def context(text, span, width=450):
    i = text.find(ws(span))
    if i < 0:
        return None
    return ("…" if i > width else "") + text[max(0, i - width):i + len(ws(span)) + width] + ("…" if i + len(ws(span)) + width < len(text) else "")


def main(docket, frac, seed):
    out = ROOT / "output" / docket
    asks = json.loads((out / "asks.json").read_text())["asks"]
    codebook = json.loads((out / "codebook.json").read_text())
    themes = {t["theme_id"]: t for t in codebook["themes"]}
    subs = json.loads((out / "submitters.json").read_text())["submitters"]
    sub_of = {c: s for s in subs for c in s["comment_ids"]}
    texts = {}
    for line in (out / "corpus.jsonl").read_text().splitlines():
        c = json.loads(line)
        texts[c["commentId"]] = ws(" ".join([c.get("body") or ""] + [a.get("text") or "" for a in c["attachments"]]))
    headings = {}
    sec_file = out / "draft_sections.txt"
    if sec_file.exists():
        for row in sec_file.read_text().splitlines()[1:]:
            parts = row.split("\t")
            headings[parts[0]] = parts[-1]

    rng = random.Random(seed)
    by_theme = defaultdict(list)
    for a in asks:
        by_theme[a["theme_id"]].append(a)
    target = round(frac * len(asks))
    picked = []
    for tid in sorted(by_theme):
        pool = sorted(by_theme[tid], key=lambda a: a["ask_id"])
        k = max(1, round(frac * len(pool)))
        picked += rng.sample(pool, min(k, len(pool)))
    rng.shuffle(picked)

    items = []
    for n, a in enumerate(picked, 1):
        s = sub_of[a["comment_id"]]
        t = themes.get(a["theme_id"], {"label": "Unclassified", "definition": ""})
        items.append({
            "n": n, "ask_id": a["ask_id"], "comment_id": a["comment_id"],
            "url": f"https://www.regulations.gov/comment/{a['comment_id']}",
            "submitter": s["name"], "bucket": s["bucket"],
            "span": a.get("display_span") or a["source_span"], "context": context(texts[a["comment_id"]], a["source_span"]),
            "draft_section": a.get("draft_section"), "draft_heading": headings.get(a.get("draft_section") or ""),
            "theme_id": a["theme_id"], "theme": t["label"], "stance": a["stance"], "confidence": a.get("confidence"),
        })
    doc = {"docket_id": docket, "seed": seed, "codebook_version": codebook["version"],
           "design": f"{len(items)} of {len(asks)} asks ({100 * len(items) / len(asks):.0f}%), stratified by theme in proportion "
                     f"to the population (at least one per theme), then shuffled; review in order so any completed prefix is random.",
           "themes": [{"theme_id": k, "label": v["label"], "definition": v["definition"], "notes": v.get("notes")} for k, v in themes.items()],
           "items": items}
    (out / "theme_spot_check_sample.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"{docket}: {len(items)} of {len(asks)} asks (target {target}); missing context: {sum(1 for i in items if not i['context'])}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("docket")
    p.add_argument("--frac", type=float, default=0.15)
    p.add_argument("--seed", type=int, default=20261004)
    a = p.parse_args()
    main(a.docket, a.frac, a.seed)
