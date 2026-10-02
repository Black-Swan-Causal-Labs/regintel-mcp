"""Text extraction from downloaded files. Text layer only; no OCR in v1.

A PDF whose text layer is empty or near-empty is flagged `needs_ocr` rather
than returned as silent empty text.
"""
from __future__ import annotations

import html
import io
import re
from collections import Counter
import zipfile
from dataclasses import dataclass, field

import pdfplumber

MAGIC = [
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "zip"),            # docx / xlsx containers
    (b"\xd0\xcf\x11\xe0", "ole"),      # legacy .doc / .xls
    (b"{\\rtf", "rtf"),
]

# Fewer extracted characters per page than this means "probably scanned".
OCR_CHARS_PER_PAGE = 100


def sniff(data: bytes) -> str:
    for sig, kind in MAGIC:
        if data.startswith(sig):
            return kind
    head = data[:512].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<body" in head:
        return "html"
    return "unknown"


@dataclass
class Extraction:
    text: str = ""
    method: str = "failed"
    page_count: int | None = None
    ok: bool = False
    needs_ocr: bool = False
    error: str | None = None
    lines: list = field(default_factory=list)  # PDF only: [{"text","page","gap_before","size"}]


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def _pdf(data: bytes, keep_lines: bool) -> Extraction:
    out = Extraction(method="pdf_text")
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            out.page_count = len(pdf.pages)
            pages, lines = [], []
            body = 0.0
            if keep_lines:
                # Body type size = the most common char size across the document.
                sizes = Counter(round(c["size"], 1) for p in pdf.pages for c in p.chars if c.get("text", "").strip())
                body = sizes.most_common(1)[0][0] if sizes else 0.0
            for pno, page in enumerate(pdf.pages, 1):
                if keep_lines:
                    # Keep body-size text only: drops footnotes, superscript markers,
                    # running headers set in smaller type, and boilerplate boxes.
                    fp = page.filter(lambda o: o.get("object_type") != "char"
                                     or o.get("size", body) >= 0.95 * body) if body else page
                    prev_bottom = None
                    for ln in fp.extract_text_lines(return_chars=True):
                        chars = [c for c in ln["chars"] if c["text"].strip() and not c["text"].isdigit()]
                        n = len(chars) or 1
                        bold = sum("Bold" in c.get("fontname", "") for c in chars) / n if chars else 0.0
                        italic = sum(any(k in c.get("fontname", "") for k in ("Italic", "Oblique"))
                                     for c in chars) / n if chars else 0.0
                        gap = None if prev_bottom is None else ln["top"] - prev_bottom
                        lines.append({"text": ln["text"], "page": pno, "gap_before": gap,
                                      "height": ln["bottom"] - ln["top"], "x0": ln["x0"], "bold": round(bold, 2),
                                      "italic": round(italic, 2)})
                        prev_bottom = ln["bottom"]
                pages.append(page.extract_text() or "")
            out.text = re.sub(r"\(cid:\d+\)", "", "\n\n".join(p.strip() for p in pages)).strip()
            out.lines = lines
    except Exception as e:  # corrupt or encrypted PDF
        out.method, out.error = "failed", f"{type(e).__name__}: {e}"
        return out
    n = len(re.sub(r"\s", "", out.text))
    if out.page_count and n < OCR_CHARS_PER_PAGE * out.page_count * 0.5 and n < 2000:
        out.needs_ocr = True
        out.ok = False
        out.error = f"text layer near-empty ({n} chars over {out.page_count} pages)"
    else:
        out.ok = n > 0
    return out


def _xlsx(z: zipfile.ZipFile) -> Extraction:
    """Spreadsheet submissions (e.g. a comment matrix): one line per row, cells tab-separated."""
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        sx = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        shared = [html.unescape(re.sub(r"<[^>]+>", "", si)) for si in re.findall(r"<si>(.*?)</si>", sx, re.S)]
    lines = []
    for name in sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
        sx = z.read(name).decode("utf-8", "replace")
        for row in re.findall(r"<row[^>]*>(.*?)</row>", sx, re.S):
            cells = []
            for attrs, body in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
                v = re.search(r"<v>(.*?)</v>", body, re.S)
                if 't="s"' in attrs and v:
                    cells.append(shared[int(v.group(1))])
                elif 't="inlineStr"' in attrs:
                    cells.append(html.unescape(re.sub(r"<[^>]+>", "", body)))
                elif v:
                    cells.append(html.unescape(v.group(1)))
            if any(c.strip() for c in cells):
                lines.append("\t".join(c.strip() for c in cells))
    text = "\n".join(lines).strip()
    return Extraction(text=text, method="xlsx", ok=bool(text))


def _docx(data: bytes) -> Extraction:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "xl/workbook.xml" in z.namelist():
                return _xlsx(z)
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:
        return Extraction(method="failed", error=f"unreadable office file: {type(e).__name__}: {e}")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    text = html.unescape(re.sub(r"<[^>]+>", "", xml)).strip()
    return Extraction(text=text, method="docx", ok=bool(text))


def extract(data: bytes, declared_format: str = "", keep_lines: bool = False) -> tuple[Extraction, str]:
    """Returns (extraction, sniffed_type). Dispatches on content, not on the declared extension."""
    kind = sniff(data)
    if kind == "pdf":
        return _pdf(data, keep_lines), kind
    if kind == "zip":
        return _docx(data), kind
    if kind == "html":
        t = html_to_text(data.decode("utf-8", "replace"))
        return Extraction(text=t, method="html", ok=bool(t)), kind
    if kind == "unknown" and declared_format.lower() in ("txt", "text", "htm", "html"):
        t = html_to_text(data.decode("utf-8", "replace"))
        return Extraction(text=t, method="text", ok=bool(t)), kind
    return Extraction(method="unsupported", error=f"unsupported file type ({kind}, declared {declared_format})"), kind
