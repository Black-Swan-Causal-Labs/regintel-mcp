#!/usr/bin/env python3
"""Independent second coder: TypeSafe Jev assigns theme and stance to each ask, blind to Claude's codes.

    python scripts/jev_second_coder.py FDA-2020-D-2307 --sample --limit 20     # pilot on the spot-check sample
    python scripts/jev_second_coder.py FDA-2021-D-0548                          # every ask

Jev sees the verbatim request, the surrounding letter text and the draft section, plus the approved codebook
(each theme's definition, includes, excludes and example) and the stance definitions. It never sees Claude's
theme_id or stance. Results append to output/<docket>/jev_codes.jsonl (resumable: done ask_ids are skipped).
The API key is read from ~/.config/typesafe/api-key (or TYPESAFE_API_KEY) and never printed or stored.
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from typesafe_sdk import Choice, TypeSafeClient

ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = Path.home() / ".config" / "typesafe" / "api-key"

STANCES = {
    "requests more specificity": "Asks FDA to define, detail, explain, give examples or set thresholds.",
    "requests more flexibility": "Asks FDA to allow alternatives, relax or soften a recommendation, or reduce burden.",
    "supports as written": "Explicitly endorses a specific recommendation in the guidance, without asking for a change.",
    "objects": "Asks FDA to remove a recommendation or reverse its direction.",
}
THEME_INSTRUCTIONS = ("A commenter on an FDA draft guidance made the request quoted in `request`. Which theme best describes "
                      "what the commenter is asking FDA to do or change? Judge the quoted request itself; use `surrounding_text` "
                      "only to understand it.")
STANCE_INSTRUCTIONS = "What stance does the quoted request in `request` take toward the draft guidance?"


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def split_notes(notes):
    inc = re.search(r"Includes:\s*(.+?)(?:\s*Excludes:|$)", notes or "")
    exc = re.search(r"Excludes:\s*(.+?)(?:\s*(?:NEW|Narrowed|Expected)\b|$)", notes or "")
    return (inc.group(1).strip() if inc else None), (exc.group(1).strip() if exc else None)


def theme_criteria(codebook):
    crit = {}
    for t in codebook["themes"]:
        inc, exc = split_notes(t.get("notes"))
        d = {"what": t["definition"] + (f" Includes: {inc}" if inc else "")}
        if exc:
            d["not_for"] = exc
        if t.get("example"):
            d["examples"] = [t["example"]["span"]]
        crit[f'{t["theme_id"]} {t["label"]}'] = d
    return crit


def context(text, span, width=450):
    i = text.find(ws(span))
    return text[max(0, i - width):i + len(ws(span)) + width] if i >= 0 else None


def main(docket, sample, limit, workers, model):
    if not os.environ.get("TYPESAFE_API_KEY"):
        os.environ["TYPESAFE_API_KEY"] = KEY_FILE.read_text().strip()
    out = ROOT / "output" / docket
    codebook = json.loads((out / "codebook.json").read_text())
    asks = {a["ask_id"]: a for a in json.loads((out / "asks.json").read_text())["asks"]}
    if sample:
        order = [i["ask_id"] for i in json.loads((out / "theme_spot_check_sample.json").read_text())["items"]]
    else:
        order = sorted(asks)
    texts = {}
    for line in (out / "corpus.jsonl").read_text().splitlines():
        c = json.loads(line)
        texts[c["commentId"]] = ws(" ".join([c.get("body") or ""] + [a.get("text") or "" for a in c["attachments"]]))
    headings = {}
    if (out / "draft_sections.txt").exists():
        for row in (out / "draft_sections.txt").read_text().splitlines()[1:]:
            p = row.split("\t")
            headings[p[0]] = p[-1]

    dest = out / "jev_codes.jsonl"
    done = {json.loads(l)["ask_id"] for l in dest.read_text().splitlines()} if dest.exists() else set()
    todo = [a for a in order if a not in done][: limit or None]
    criteria = theme_criteria(codebook)
    label_to_id = {k: k.split(" ", 1)[0] for k in criteria}
    client = TypeSafeClient(model=model) if model else TypeSafeClient()

    def code(ask_id):
        a = asks[ask_id]
        sec = a.get("draft_section")
        state = {"request": a.get("display_span") or a["source_span"],
                 "surrounding_text": context(texts[a["comment_id"]], a["source_span"]),
                 "draft_section": f"{sec} {headings.get(sec, '')}".strip() if sec else "general comment (no section named)"}
        r = client.system_one(state=state, questions={
            "theme": Choice(instructions=THEME_INSTRUCTIONS, criteria=criteria),
            "stance": Choice(instructions=STANCE_INSTRUCTIONS, criteria=STANCES)})
        th, st = r.answers["theme"], r.answers["stance"]
        return {"ask_id": ask_id, "jev_theme": label_to_id[th.choice], "jev_theme_confidence": th.confidence,
                "jev_theme_probabilities": {label_to_id[k]: v for k, v in th.probabilities.items()},
                "jev_stance": st.choice, "jev_stance_confidence": st.confidence, "jev_stance_probabilities": st.probabilities,
                "model": r.model, "request_id": r.request_id,
                "usage": {"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens} if r.usage else None,
                "codebook_version": codebook["version"]}

    n_ok = n_err = 0
    with dest.open("a") as f, ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(code, a): a for a in todo}
        for fu in as_completed(futs):
            try:
                f.write(json.dumps(fu.result(), ensure_ascii=False) + "\n"); f.flush(); n_ok += 1
            except Exception as e:  # report and continue; reruns pick up what is missing
                n_err += 1
                print(f"{futs[fu]}: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
    print(f"{docket}: coded {n_ok}, errors {n_err}, already done {len(done)}, file {dest}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("docket")
    p.add_argument("--sample", action="store_true", help="only the theme spot-check sample, in its order")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--model", default=None)
    a = p.parse_args()
    main(a.docket, a.sample, a.limit, a.workers, a.model)
