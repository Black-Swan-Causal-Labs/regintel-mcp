#!/usr/bin/env python3
"""Assemble output/<docket>/analysis.json (docs/analysis-schema.json) from the run's parts.

    python scripts/build_analysis.py FDA-2020-D-2307
"""
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _fr_text(svc, doc_id):
    return re.sub(r"\s+", " ", svc.get_guidance_text(doc_id, include_full_text=True)["full_text"])


def _sentence_after(text, start):
    i = text.find(start)
    return text[i:text.find(". ", i) + 1] if i >= 0 else None


def guidance_overview(docket, draft_ref, fr_changes):
    """What the guidance is about, in FDA's own words, from the cached Federal Register notices."""
    from regintel_mcp.service import Service
    svc = Service()
    docs = {d["documentId"]: d for d in svc.list_documents(docket)["documents"]}
    noas = sorted((d for d in docs.values() if d["subtype"] == "Notice of Availability"), key=lambda d: d["postedDate"])
    draft_noa, final_noa = noas[0], noas[-1]
    reopen = [d for d in noas[1:-1]]
    t_draft, t_final = _fr_text(svc, draft_noa["documentId"]), _fr_text(svc, final_noa["documentId"])
    summary = _sentence_after(t_final, "This guidance is intended to provide")
    topics = _sentence_after(t_final, "This guidance discusses the following topics")
    topic_list = [x.strip().rstrip(".") for x in re.split(r";\s*(?:and\s+)?", topics.split(": ", 1)[1])] if topics else []
    first_deadline = re.search(r"DATES: Submit either electronic or written comments on the draft guidance by ([A-Z][a-z]+ \d{1,2}, \d{4})", t_draft)
    timeline = [{"date": draft_noa["postedDate"][:10], "event": "Draft guidance published for comment", "doc_id": draft_noa["documentId"], "fr": draft_noa.get("frDocNum")}]
    if first_deadline:
        timeline.append({"date": first_deadline.group(1), "event": "Original comment deadline", "doc_id": draft_noa["documentId"]})
    for d in reopen:
        t = _fr_text(svc, d["documentId"])
        m = re.search(r"comments by ([A-Z][a-z]+ \d{1,2}, \d{4})", t)
        timeline.append({"date": d["postedDate"][:10], "event": "Comment period reopened", "doc_id": d["documentId"], "fr": d.get("frDocNum")})
        if m:
            timeline.append({"date": m.group(1), "event": "Comment period closed", "doc_id": d["documentId"]})
    timeline.append({"date": final_noa["postedDate"][:10], "event": "Final guidance published", "doc_id": final_noa["documentId"], "fr": final_noa.get("frDocNum")})
    for e in timeline:  # normalise "November 29, 2021" to ISO
        if not re.match(r"\d{4}-", e["date"]):
            e["date"] = datetime.strptime(e["date"], "%B %d, %Y").date().isoformat()
    timeline.sort(key=lambda e: e["date"])
    items = re.split(r"\(\d\)\s*", fr_changes.split("include:", 1)[-1])
    changes = [re.sub(r"[;,]?\s*(and)?\s*$", "", x.strip()).rstrip(".") for x in items if x.strip()]
    tail = re.search(r"In addition, editorial changes[^.]*\.", fr_changes)
    if changes and tail:
        changes[-1] = changes[-1].split(". In addition")[0]
    return {"summary": summary, "summary_source": final_noa["documentId"], "topics": topic_list, "topics_source": final_noa["documentId"],
            "timeline": timeline, "fda_listed_changes": changes, "fda_listed_changes_source": final_noa["documentId"],
            "editorial_note": tail.group(0) if tail else None,
            "draft_url": f"https://www.regulations.gov/document/{draft_ref}", "final_url": "https://www.fda.gov/media/152503/download"}


def main(docket):
    D = ROOT / "output" / docket
    load = lambda p: json.loads((D / p).read_text())
    subs = load("submitters.json")["submitters"]
    codebook = load("codebook.json")
    asks = load("asks.json")
    conc = load("concordance.json")
    diff = load("guidance_diff.json")
    decisions = json.loads((ROOT / "decisions" / f"{docket}.json").read_text())["decisions"]
    corpus = {}
    for line in (D / "corpus.jsonl").read_text().splitlines():
        c = json.loads(line)
        corpus[c["commentId"]] = c

    sub_of = {cid: s["submitter_id"] for s in subs for cid in s["comment_ids"]}
    excluded = {cid for x in decisions if x["decision"].startswith("exclude") for cid in x.get("comment_ids", [])}
    zero = {cid for x in decisions if "zero_asks" in x["decision"] for cid in x.get("comment_ids", [])}
    n_asks = Counter(a["comment_id"] for a in asks["asks"])

    comments = []
    for cid in sorted(corpus):
        c = corpus[cid]
        comments.append({
            "comment_id": cid, "submitter_id": sub_of[cid], "posted": c["postedDate"],
            "url": f"https://www.regulations.gov/comment/{cid}", "is_stub": bool(c.get("is_stub")),
            "comment_on_document": c.get("commentOnDocumentId"), "n_asks": n_asks.get(cid, 0),
            "agency_duplicate_count": c.get("duplicateComments"),
            "excluded_from_draft_final": cid in excluded, "zero_asks_by_decision": cid in zero,
        })

    checkpoints = []
    for n in (1, 2, 3, 4):
        notes = [x for x in decisions if x["checkpoint"] == n or (n == 1 and x["checkpoint"] == "Phase 1 hard stop")]
        checkpoints.append({"n": n, "approved_by": "JDD",
                            "date": max((x["date"] for x in notes), default=None),
                            "notes": " | ".join(x.get("notes") or x.get("reason") or x["decision"] for x in notes)})
    spot = next(x for x in decisions if x["decision"] == "spot_check")

    keep_a = ("ask_id", "comment_id", "theme_id", "stance", "source_span", "display_span", "draft_section",
              "section_inferred", "confidence")
    keep_c = ("ask_id", "section_id", "call", "evidence_span", "rationale", "fr_listed_change", "confidence",
              "already_addressed_in_draft", "call_original", "human_review")
    keep_s = ("section_id", "draft_section_id", "final_section_id", "heading", "draft_heading", "level", "status",
              "heading_changed", "draft_text", "final_text", "change_summary_stats", "word_diff")
    out = {
        "docket": {"id": docket,
                   "title": "Real-World Data: Assessing Electronic Health Records and Medical Claims Data To Support "
                            "Regulatory Decision-Making for Drug and Biological Products",
                   "draft_date": "2021-09-30", "final_date": "2024-07",
                   "n_comments": len(comments),
                   "n_submissions_represented": sum((c["agency_duplicate_count"] or 1) for c in comments),
                   "draft_ref": conc["draft_ref"], "final_ref": conc["final_ref"],
                   "final_ref_note": "Current fda.gov copy (JDD decision). Identical to the Jul 2024 docket copy "
                                     "(FDA-2020-D-2307-0067) except a later edit in V.E.2: 'age, gender, race' -> 'age, sex, race'.",
                   "docket_url": f"https://www.regulations.gov/docket/{docket}"},
        "run": {"date": date.today().isoformat(), "codebook_version": codebook["version"],
                "checkpoints": checkpoints, "spot_check_agreement": spot["spot_check_agreement"],
                "spot_check_n": spot["n_reviewed"],
                "method": {"retrieval": "regintel-mcp (deterministic: regulations.gov API v4, pdfplumber, section-aligned difflib diff)",
                           "judgment": "Claude with skills submitter-taxonomy, comment-theming, draft-final-concordance; "
                                       "coding and concordance fanned out to 6 subagents each",
                           "verification": "every source_span verbatim in the extracted comment text; every evidence_span "
                                           "verbatim in the final guidance text; 4 human checkpoints"}},
        "caveat": conc["caveat"],
        "submitters": subs,
        "comments": comments,
        "themes": [{"theme_id": t["theme_id"], "label": t["label"], "definition": t["definition"],
                    "notes": t.get("notes"), "emergent": bool(t.get("emergent"))} for t in codebook["themes"]],
        "asks": [{k: a[k] for k in keep_a if k in a} for a in asks["asks"]],
        "sections": [{k: s[k] for k in keep_s if k in s} for s in diff["sections"]],
        "concordance": [{k: c[k] for k in keep_c if k in c} for c in conc["concordance"]],
        "fr_listed_changes": (D / "concordance" / "fr_listed_changes.txt").read_text().strip(),
        "guidance": guidance_overview(docket, conc["draft_ref"], (D / "concordance" / "fr_listed_changes.txt").read_text()),
    }
    (D / "analysis.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {D / 'analysis.json'}: {len(out['asks'])} asks, {len(out['concordance'])} calls, "
          f"{len(out['sections'])} sections, {(D / 'analysis.json').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
