"""Split an FDA guidance into numbered sections and diff draft vs final.

Deterministic throughout: regex + font cues for headings, difflib for
similarity. No model calls.

Section structure in FDA guidances:
    I.  INTRODUCTION            level 1  (Roman, upper case, bold)
    A.  Relevance of Data       level 2  (letter, bold)
    1.  Enrollment and ...      level 3  (number, bold)

PDF cleanup before sectioning:
  * footnotes / superscripts / small boilerplate dropped by font size (extract.py)
  * running headers ("Contains Nonbinding Recommendations", page numbers) dropped
    when the same line recurs on >= 30% of pages
  * draft line numbering (left-margin integers) stripped when present
  * table-of-contents lines (dot leaders) ignored
"""
from __future__ import annotations

import difflib
import re
from collections import Counter

PARSER_VERSION = "1"
PARA = "\u00b6"  # paragraph-break token in word diffs

ROMAN = r"(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
RE_ROMAN = re.compile(rf"^(?P<num>{ROMAN})\.\s+(?P<title>[A-Z][A-Z0-9 ,;:&/()'’\-–—]+)$")
RE_ROMAN_TITLE = re.compile(rf"^(?P<num>{ROMAN})\.\s+(?P<title>[A-Z][^.]{{2,120}})$")
RE_LETTER = re.compile(r"^(?P<num>[A-Z])\.\s+(?P<title>\S.{1,160})$")
RE_NUMBER = re.compile(r"^(?P<num>\d{1,2})\.\s+(?P<title>\S.{1,160})$")
RE_CAPS = re.compile(r"^(?P<title>[A-Z][A-Z0-9 ,;:&/()'’\-–—]{3,80})$")
RE_LINENO = re.compile(r"^\d{1,4}(?:\s+|$)")
RE_DOTS = re.compile(r"\.{5,}|…{2,}")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _key(s: str) -> str:
    """Normalisation used for comparison only: case, punctuation, quotes, hyphenation."""
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[-–—]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _words(s: str) -> list[str]:
    return _key(s).split()


# ------------------------------------------------------------------ cleanup
def clean_lines(lines: list[dict], page_count: int) -> list[dict]:
    if not lines:
        return []
    # Running headers/footers: same text (digits removed) on many pages.
    sig = lambda t: re.sub(r"\d+", "#", _norm(t))
    pages_per_sig = {}
    for ln in lines:
        pages_per_sig.setdefault(sig(ln["text"]), set()).add(ln["page"])
    threshold = max(3, int(0.3 * page_count))
    running = {s for s, ps in pages_per_sig.items() if len(ps) >= threshold and len(s) < 120}
    # Line numbering: most non-empty lines start with an integer token.
    nonempty = [ln for ln in lines if ln["text"].strip()]
    numbered = sum(bool(RE_LINENO.match(ln["text"])) for ln in nonempty) > 0.4 * len(nonempty)

    margin = min((ln["x0"] for ln in nonempty), default=0) + 20
    out = []
    for ln in lines:
        t = ln["text"]
        bare = re.fullmatch(r"\s*\d{1,4}\s*", t)
        if bare:
            # In line-numbered drafts a bare margin number is a blank line (paragraph
            # break); anywhere else a bare number is a page number.
            if numbered and ln["x0"] < margin:
                out.append({**ln, "text": ""})
            continue
        if numbered:
            t = RE_LINENO.sub("", t, count=1)
        if sig(t) in running:
            continue
        out.append({**ln, "text": _norm(t)})
    return out


def _heading(ln: dict, from_pdf: bool):
    t = ln["text"]
    if not t or RE_DOTS.search(t):
        return None
    bold, styled = ln.get("bold", 0), ln.get("bold", 0) + ln.get("italic", 0)
    if not from_pdf:
        # Plain text / HTML (Federal Register notices): title-case Roman headings, no font cues.
        m = RE_ROMAN_TITLE.match(t)
        if m and not m.group("title").endswith("."):
            return 1, m.group("num"), m.group("title").strip()
    for level, rx in ((1, RE_ROMAN), (2, RE_LETTER), (3, RE_NUMBER)):
        m = rx.match(t)
        if m and m.group("num"):
            title = m.group("title").strip()
            if from_pdf and (bold < 0.7 if level < 3 else styled < 0.7):
                return None     # numbered list items are set in roman body type
            if title.endswith(".") and not from_pdf:
                return None
            return level, m.group("num"), title
    # Unnumbered all-caps bold heading (e.g. a final guidance's "REFERENCES").
    m = RE_CAPS.match(t)
    if m and from_pdf and bold >= 0.9:
        return 1, re.sub(r"[^A-Z0-9]+", "_", t).strip("_"), m.group("title")
    return None


# ---------------------------------------------------------------- sectioning
def sectionize(lines: list[dict], from_pdf: bool = True) -> list[dict]:
    """Lines -> [{section_id, level, number, heading, parent_heading, paragraphs, text}]."""
    sections = [{"section_id": "front", "level": 0, "number": "", "heading": "Front matter",
                 "parent_heading": "", "paragraphs": []}]
    stack: list[dict] = []          # current heading path
    cur_par: list[str] = []
    started = False                 # body starts at the first Roman heading

    def flush():
        if cur_par:
            sections[-1]["paragraphs"].append(_norm(" ".join(cur_par)))
            cur_par.clear()

    i = 0
    while i < len(lines):
        ln = lines[i]
        h = _heading(ln, from_pdf)
        # A numbered (level-3) heading only exists under a lettered (level-2) one;
        # elsewhere "1. ..." in italics is an emphasised list item.
        if h and h[0] == 3 and not any(s["level"] == 2 for s in stack):
            h = None
        if h and (started or h[1] == "I"):
            level, num, title = h
            # Roman headings wrap: absorb following all-caps bold lines.
            while level == 1 and i + 1 < len(lines) and lines[i + 1]["text"].isupper() \
                    and (not from_pdf or lines[i + 1].get("bold", 0) >= 0.7) \
                    and not any(rx.match(lines[i + 1]["text"]) for rx in (RE_ROMAN, RE_LETTER, RE_NUMBER)):
                i += 1
                title += " " + lines[i]["text"]
            started = True
            flush()
            stack = [s for s in stack if s["level"] < level]
            sid = ".".join([s["number"] for s in stack] + [num])
            parent = stack[-1]["heading"] if stack else ""
            node = {"section_id": sid, "level": level, "number": num, "heading": _norm(title),
                    "parent_heading": parent, "paragraphs": []}
            sections.append(node)
            stack.append(node)
            i += 1
            continue
        t = ln["text"]
        if not t:
            flush()
        else:
            gap, height = ln.get("gap_before"), ln.get("height") or 12
            if gap is not None and gap > 0.6 * height and cur_par:
                flush()
            cur_par.append(t)
        i += 1
    flush()

    seen = Counter()
    for s in sections:              # disambiguate repeated ids (rare, malformed numbering)
        seen[s["section_id"]] += 1
        if seen[s["section_id"]] > 1:
            s["section_id"] += f"~{seen[s['section_id']]}"
        s["text"] = "\n\n".join(s["paragraphs"])
    return sections


def sectionize_plain_text(text: str) -> list[dict]:
    """Fallback for HTML/plain text (e.g. Federal Register notices): regex headings only."""
    lines = [{"text": _norm(t), "gap_before": None, "height": 12} for t in text.splitlines()]
    return sectionize(lines, from_pdf=False)


# --------------------------------------------------------------------- diff
def _sim(a: str, b: str, cap: int = 600) -> float:
    wa, wb = _words(a)[:cap], _words(b)[:cap]
    if not wa and not wb:
        return 1.0
    return difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio()


def _heading_key(s: dict) -> str:
    return _key(s["heading"])


def align(draft: list[dict], final: list[dict]) -> list[tuple[int | None, int | None, float]]:
    """Match sections by heading (parent-qualified first), then by heading+text similarity."""
    pairs: dict[int, tuple[int, float]] = {}
    used_f: set[int] = set()

    def exact(keyfn):
        idx = {}
        for j, f in enumerate(final):
            if j not in used_f:
                idx.setdefault(keyfn(f), []).append(j)
        for i, d in enumerate(draft):
            if i in pairs:
                continue
            js = idx.get(keyfn(d))
            if js:
                j = js.pop(0)
                pairs[i] = (j, 1.0)
                used_f.add(j)

    exact(lambda s: (s["level"], _key(s["parent_heading"]), _heading_key(s)))
    exact(lambda s: (s["level"], _heading_key(s)))

    cands = []
    for i, d in enumerate(draft):
        if i in pairs:
            continue
        for j, f in enumerate(final):
            if j in used_f or abs(d["level"] - f["level"]) > 1:
                continue
            hs = difflib.SequenceMatcher(None, _words(d["heading"]), _words(f["heading"])).ratio()
            ts = _sim(d["text"], f["text"], cap=300)
            score = 0.5 * hs + 0.5 * ts
            if score >= 0.55 or hs >= 0.75 or ts >= 0.7:
                cands.append((round(score, 4), -i, -j, i, j))
    for score, _, _, i, j in sorted(cands, reverse=True):
        if i not in pairs and j not in used_f:
            pairs[i] = (j, score)
            used_f.add(j)

    # Emit in final order; removed draft sections slot in after their predecessor.
    f_to_d = {j: (i, sc) for i, (j, sc) in pairs.items()}
    out, emitted_d = [], set()
    for j in range(len(final)):
        if j in f_to_d:
            i, sc = f_to_d[j]
            for k in range(i):
                if k not in pairs and k not in emitted_d:
                    out.append((k, None, 0.0))
                    emitted_d.add(k)
            out.append((i, j, sc))
            emitted_d.add(i)
        else:
            out.append((None, j, 0.0))
    for k in range(len(draft)):
        if k not in pairs and k not in emitted_d:
            out.append((k, None, 0.0))
    return out


def paragraph_diff(dp: list[str], fp: list[str]) -> tuple[list[dict], dict]:
    sm = difflib.SequenceMatcher(None, [_key(p) for p in dp], [_key(p) for p in fp], autojunk=False)
    ops, st = [], Counter()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            st["paragraphs_unchanged"] += i2 - i1
            continue
        if tag == "replace":
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                ops.append({"op": "modified", "draft": dp[i1 + k], "final": fp[j1 + k],
                            "similarity": round(_sim(dp[i1 + k], fp[j1 + k]), 3)})
            st["paragraphs_modified"] += n
            for k in range(i1 + n, i2):
                ops.append({"op": "removed", "draft": dp[k], "final": None})
                st["paragraphs_removed"] += 1
            for k in range(j1 + n, j2):
                ops.append({"op": "added", "draft": None, "final": fp[k]})
                st["paragraphs_added"] += 1
        elif tag == "delete":
            for k in range(i1, i2):
                ops.append({"op": "removed", "draft": dp[k], "final": None})
            st["paragraphs_removed"] += i2 - i1
        elif tag == "insert":
            for k in range(j1, j2):
                ops.append({"op": "added", "draft": None, "final": fp[k]})
            st["paragraphs_added"] += j2 - j1
    return ops, dict(st)


def word_stats(a: str, b: str) -> dict:
    wa, wb = _words(a), _words(b)
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return {"words_draft": len(wa), "words_final": len(wb), "words_added": added,
            "words_removed": removed, "similarity": round(sm.ratio(), 3)}


def _best_match(par: str, pool: list[tuple[str, str, set]], min_ratio: float = 0.6):
    """Best (section_id, ratio) for a paragraph among (section_id, text, wordset) — Jaccard prefilter."""
    ws = set(_words(par))
    if len(ws) < 5:
        return None
    best = None
    for sid, text, pws in pool:
        if not pws or len(ws & pws) / len(ws | pws) < 0.35:
            continue
        r = _sim(par, text, cap=400)
        if r >= min_ratio and (best is None or r > best[1]):
            best = (sid, round(r, 3))
    return best


def _mark_moves(rows: list[dict], draft: list[dict], final: list[dict]) -> None:
    """Relabel added/removed paragraphs that reappear in another section as moves."""
    fpool = [(s["section_id"], p, set(_words(p))) for s in final for p in s["paragraphs"]]
    dpool = [(s["section_id"], p, set(_words(p))) for s in draft for p in s["paragraphs"]]
    for row in rows:
        for op in row.get("paragraph_changes", []):
            if op["op"] == "removed":
                m = _best_match(op["draft"], [x for x in fpool if x[0] != row["final_section_id"]])
                if m:
                    op.update(op="moved_out", moved_to_section=m[0], similarity=m[1])
            elif op["op"] == "added":
                m = _best_match(op["final"], [x for x in dpool if x[0] != row["draft_section_id"]])
                if m:
                    op.update(op="moved_in", moved_from_section=m[0], similarity=m[1])
        moves = [op for op in row.get("paragraph_changes", []) if op["op"].startswith("moved")]
        if moves:
            row["change_summary_stats"]["paragraphs_moved"] = len(moves)


def word_diff(a: str, b: str) -> list[list[str]]:
    """Word-level diff as runs: [["=", "kept words"], ["-", "deleted"], ["+", "inserted"], ...].

    Paragraph breaks are kept as the token PARA so a viewer can rebuild paragraphs. Words are
    compared case-sensitively with punctuation attached, so "cases"->"scenarios" or
    "the EHR"->"EHRs" show as small replacements rather than whole-sentence changes.
    """
    tok = lambda t: [w for p in re.split(r"\n{2,}", t or "") for w in (p.split() + [PARA])][:-1] if t else []
    ta, tb = tok(a), tok(b)
    runs: list[list[str]] = []

    def add(op, words):
        if not words:
            return
        if runs and runs[-1][0] == op:
            runs[-1][1] += " " + " ".join(words)
        else:
            runs.append([op, " ".join(words)])

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if tag == "equal":
            add("=", ta[i1:i2])
        else:
            add("-", ta[i1:i2])
            add("+", tb[j1:j2])
    return runs


def diff_sections(draft: list[dict], final: list[dict], include_text: bool = True) -> list[dict]:
    rows = []
    for i, j, score in align(draft, final):
        d = draft[i] if i is not None else None
        f = final[j] if j is not None else None
        dt, ft = (d or {}).get("text", ""), (f or {}).get("text", "")
        if d and f:
            status = "unchanged" if _key(dt) == _key(ft) else "modified"
        else:
            status = "added" if f else "removed"
        ops, pst = paragraph_diff((d or {}).get("paragraphs", []), (f or {}).get("paragraphs", []))
        stats = {**word_stats(dt, ft), **pst}
        row = {
            "section_id": (f or d)["section_id"],
            "draft_section_id": d["section_id"] if d else None,
            "final_section_id": f["section_id"] if f else None,
            "heading": (f or d)["heading"],
            "draft_heading": d["heading"] if d else None,
            "level": (f or d)["level"],
            "status": status,
            "alignment_score": round(score, 3) if d and f else None,
            "heading_changed": bool(d and f and _key(d["heading"]) != _key(f["heading"])),
            "change_summary_stats": stats,
        }
        row["draft_text"] = dt if d else None
        row["final_text"] = ft if f else None
        row["paragraph_changes"] = ops
        row["word_diff"] = word_diff(dt, ft)
        rows.append(row)
    _mark_moves(rows, draft, final)
    if not include_text:
        for row in rows:
            for k in ("draft_text", "final_text", "paragraph_changes", "word_diff"):
                row.pop(k)
    return rows
