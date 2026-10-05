#!/usr/bin/env python3
"""Draw the seeded concordance spot-check sample for one docket (Checkpoint 4).

    python scripts/concordance_spot_check_sample.py FDA-2021-D-0548 [--frac 0.15] [--seed 20261020]

Same design as the FDA-2020-D-2307 run: about 15% of calls, with roughly a third drawn from the
low-confidence calls and the rest stratified by call type in proportion to the population; then
shuffled so any completed prefix is random. Writes output/<docket>/spot_check_sample.json.
"""
import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sections(md_path):
    out, cur = {}, None
    for line in Path(md_path).read_text().splitlines():
        m = re.match(r"^### \[([^\]]+)\] ?(.*)$", line)
        if m:
            cur = m.group(1)
            out[cur] = {"heading": m.group(2), "text": ""}
        elif cur:
            out[cur]["text"] += line + "\n"
    return {k: {"heading": v["heading"], "text": v["text"].strip()} for k, v in out.items()}


def main(docket, frac, seed):
    out = ROOT / "output" / docket
    asks = {a["ask_id"]: a for a in json.loads((out / "asks.json").read_text())["asks"]}
    calls = json.loads((out / "concordance.json").read_text())["concordance"]
    subs = {c: s for s in json.loads((out / "submitters.json").read_text())["submitters"] for c in s["comment_ids"]}
    labels = {t["theme_id"]: t["label"] for t in json.loads((out / "codebook.json").read_text())["themes"]}
    draft = sections(out / "concordance" / "draft_text.md")
    final = sections(out / "concordance" / "final_text.md")

    rng = random.Random(seed)
    target = round(frac * len(calls))
    low = sorted((c for c in calls if c["confidence"] == "low"), key=lambda c: c["ask_id"])
    n_low = min(len(low), round(target / 3))
    picked = rng.sample(low, n_low)
    rest = [c for c in calls if c not in picked]
    by_call = defaultdict(list)
    for c in sorted(rest, key=lambda c: c["ask_id"]):
        by_call[c["call"]].append(c)
    remaining = target - n_low
    for call, pool in sorted(by_call.items()):
        k = max(1, round(remaining * len(pool) / len(rest)))
        picked += rng.sample(pool, min(k, len(pool)))
    rng.shuffle(picked)

    items = []
    for n, c in enumerate(picked, 1):
        a = asks[c["ask_id"]]
        s = subs[a["comment_id"]]
        ds, fs = a.get("draft_section"), c.get("section_id")
        items.append({
            "n": n, "ask_id": c["ask_id"], "comment_id": a["comment_id"], "submitter": s["name"], "bucket": s["bucket"],
            "theme": labels.get(a["theme_id"], "Unclassified"), "stance": a["stance"], "source_span": a["source_span"],
            "display_span": a.get("display_span"),
            "draft_section": ds, "draft_heading": draft.get(ds, {}).get("heading") if ds else None,
            "draft_text": draft.get(ds, {}).get("text") if ds else None,
            "final_section": fs, "final_heading": final.get(fs, {}).get("heading") if fs else None,
            "final_text": final.get(fs, {}).get("text") if fs and fs in final else None,
            "call": c["call"], "evidence_span": c.get("evidence_span"), "rationale": c["rationale"],
            "confidence": c["confidence"], "fr_listed_change": c.get("fr_listed_change", False),
            "url": f"https://www.regulations.gov/comment/{a['comment_id']}",
        })
    doc = {"docket_id": docket, "seed": seed,
           "design": f"{len(items)} of {len(calls)} calls ({100 * len(items) / len(calls):.0f}%): {n_low} drawn from the {len(low)} "
                     f"low-confidence calls, the rest stratified by call type in proportion to the population; shuffled.",
           "items": items}
    (out / "spot_check_sample.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(doc["design"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("docket")
    p.add_argument("--frac", type=float, default=0.15)
    p.add_argument("--seed", type=int, default=20261020)
    a = p.parse_args()
    main(a.docket, a.frac, a.seed)
