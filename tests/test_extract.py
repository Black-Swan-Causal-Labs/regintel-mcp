import io
import zipfile

from regintel_mcp.extract import extract, html_to_text, sniff


def test_sniff():
    assert sniff(b"%PDF-1.7 ...") == "pdf"
    assert sniff(b"PK\x03\x04....") == "zip"
    assert sniff(b"<!DOCTYPE html><html>") == "html"


def test_html_to_text():
    assert html_to_text("See attached<br/>file(s) &amp; more") == "See attached\nfile(s) & more"


def test_xlsx_comment_matrix():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/sharedStrings.xml", "<sst><si><t>Section</t></si><si><t>Please define RWD</t></si></sst>")
        z.writestr("xl/worksheets/sheet1.xml",
                   '<worksheet><sheetData><row><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>'
                   '<row><c><v>42</v></c></row></sheetData></worksheet>')
    ex, kind = extract(buf.getvalue(), "xlsx")
    assert kind == "zip" and ex.method == "xlsx" and ex.ok
    assert ex.text == "Section\tPlease define RWD\n42"


def test_unsupported_is_flagged_not_silent():
    ex, _ = extract(b"\x00\x01garbage", "bin")
    assert not ex.ok and ex.error
