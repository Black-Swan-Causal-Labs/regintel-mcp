"""Offline tests for sectioning and section-aligned diff (synthetic lines, no network)."""
from regintel_mcp import guidance as g


def L(text, bold=0.0, italic=0.0, gap=1.8, page=1, x0=72):
    return {"text": text, "bold": bold, "italic": italic, "gap_before": gap, "height": 12, "page": page, "x0": x0}


def doc(validation_paras, extra_section=True):
    lines = [
        L("TABLE OF CONTENTS", bold=1),
        L("I. INTRODUCTION ........................ 1", bold=1),
        L("I. INTRODUCTION", bold=1),
        L("This guidance describes data sources."),
        L("It applies to drugs.", gap=14),
        L("II. DATA SOURCES", bold=1),
        L("A. Relevance of the Data Source", bold=1),
        L("Sponsors should justify each data source for the question."),
        L("1. Enrollment and Capture", italic=1),
        L("Enrollment should be described."),
        L("B. Validation", bold=1),
    ] + [L(p, gap=14) for p in validation_paras]
    if extra_section:
        lines += [L("III. GLOSSARY", bold=1), L("Terms are defined here.")]
    return lines


def test_sections_and_toc_skipped():
    secs = g.sectionize(doc(["Validate outcomes with chart review."]))
    ids = [s["section_id"] for s in secs]
    assert ids == ["front", "I", "II", "II.A", "II.A.1", "II.B", "III"]
    intro = secs[1]
    assert intro["paragraphs"] == ["This guidance describes data sources.", "It applies to drugs."]


def test_list_item_not_a_heading_outside_lettered_section():
    lines = [L("I. INTRODUCTION", bold=1), L("1. An emphasised list item", italic=1), L("text")]
    assert [s["section_id"] for s in g.sectionize(lines)] == ["front", "I"]


def test_line_numbers_and_running_headers_removed():
    lines = []
    for p in range(1, 6):
        lines += [L("Contains Nonbinding Recommendations", page=p),
                  L(f"{p * 10} I. INTRODUCTION" if p == 1 else f"{p * 10} Body text page {p}.", bold=1 if p == 1 else 0, page=p, x0=42),
                  L(f"{p * 10 + 1}", page=p, x0=42),
                  L(f"{p}", page=p, x0=300)]
    cleaned = g.clean_lines(lines, page_count=5)
    texts = [ln["text"] for ln in cleaned]
    assert "Contains Nonbinding Recommendations" not in texts
    assert texts[0] == "I. INTRODUCTION" and "" in texts          # margin number -> paragraph break
    assert not any(t.isdigit() for t in texts)                     # page numbers dropped


def test_diff_statuses_and_moves():
    moved = "Choose a reference standard appropriate to the study question and level of certainty needed."
    draft = g.sectionize(doc(["Validate outcomes with chart review.", moved]))
    final_lines = doc(["Validate outcomes with chart review and quantitative bias analysis."], extra_section=False)
    final_lines += [L("C. Reference Standards", bold=1), L(moved)]
    final = g.sectionize(final_lines)
    rows = {r["section_id"]: r for r in g.diff_sections(draft, final)}
    assert rows["I"]["status"] == "unchanged"
    assert rows["II.B"]["status"] == "modified"
    assert rows["II.C"]["status"] == "added"
    assert rows["III"]["status"] == "removed"
    ops = rows["II.B"]["paragraph_changes"]
    assert any(op["op"] == "moved_out" and op["moved_to_section"] == "II.C" for op in ops)


def test_diff_is_deterministic():
    a = g.sectionize(doc(["x y z validation text here"]))
    b = g.sectionize(doc(["x y z validation text changed here"], extra_section=False))
    assert g.diff_sections(a, b) == g.diff_sections(a, b)
