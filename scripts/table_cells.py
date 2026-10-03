#!/usr/bin/env python3
"""Recover reading-order quotes for asks that came from table-layout comments.

PDF text extraction reads a multi-column table one printed line at a time, so a cell's
text is interleaved with its neighbours'. pdfplumber can also read tables cell by cell.
For each ask, find the table cell whose words best cover the ask's source_span; if the
coverage is high, store that cell's text as `display_span` (verbatim cell text in reading
order) and keep `source_span` (verbatim extracted text) as the audit anchor.

    python scripts/table_cells.py output/FDA-2020-D-2307
"""
import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
MIN_COVER = 0.9


def words(s):
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def rows_for(pdf_path):
    """Every table row as a list of non-empty cell texts, in column order."""
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = [re.sub(r"\s+", " ", c or "").strip() for c in row]
                    cells = [c for c in cells if len(c) > 15]
                    if cells:
                        out.append(cells)
    return out


def ordered_hits(span_w, cell_w):
    """Span word positions matched, in order, by runs of >= 3 consecutive words of the cell."""
    sm = difflib.SequenceMatcher(None, span_w, cell_w, autojunk=False)
    return {b.a + k for b in sm.get_matching_blocks() if b.size >= 3 for k in range(b.size)}


def main(out_dir):
    d = Path(out_dir)
    A = json.loads((d / "asks.json").read_text())
    docket = A["docket_id"]
    by_comment = defaultdict(list)
    for a in A["asks"]:
        a.pop("display_span", None), a.pop("display_span_method", None)
        by_comment[a["comment_id"]].append(a)
    n_set = 0
    for cid, asks in sorted(by_comment.items()):
        rows = [r for p in sorted((ROOT / "data" / "raw" / docket).glob(f"{cid}_att*.pdf")) for r in rows_for(p)]
        if not rows:
            continue
        rows_w = [[(c, words(c)) for c in r] for r in rows]
        for a in asks:
            sw = words(a["source_span"])
            if len(sw) < 6:
                continue
            flat = " ".join(sw)
            if any(flat in " ".join(w) for r in rows_w for _, w in r):
                continue  # already a clean, in-order run of one cell
            best = None
            for r in rows_w:
                per = [(c, ordered_hits(sw, w)) for c, w in r]
                union = set().union(*[h for _, h in per])
                cover = len(union) / len(sw)
                if best is None or cover > best[0]:
                    best = (cover, [c for c, h in per if len(h) >= 0.15 * len(sw)])
            if best and best[0] >= MIN_COVER and best[1]:
                a["display_span"] = " … ".join(best[1])
                a["display_span_method"] = f"pdf table row, cells in column order (in-order word coverage {best[0]:.2f})"
                n_set += 1
    (d / "asks.json").write_text(json.dumps(A, indent=1))
    print(f"display_span set on {n_set} asks")


if __name__ == "__main__":
    main(sys.argv[1])
