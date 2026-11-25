"""Files made for the file checks' tests (screener/filefacts.py): a PDF with the content stream and the document
information a test gives it (so its text can be drawn invisibly, in white or tiny, and its metadata edited), saved
over as many times as asked; and a Word document with the body, the core properties and the application a test
gives it (so it can carry hidden runs and tracked changes)."""

import io
import zipfile

W: str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CORE: str = (
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">{inner}</cp:coreProperties>'
)
APP: str = (
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
    "<Application>{name}</Application></Properties>"
)


def pdf(stream: str, info: str = "", saves: int = 1, font: str = "/ABCDEF+Helvetica") -> bytes:
    """A one-page PDF whose page content is `stream` and whose information dictionary holds `info`."""
    body = stream.encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> "
            b"/Contents 4 0 R >>", b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont %s >>" % font.encode(), b"<< %s >>" % info.encode()]  # fmt: skip
    out, offsets = io.BytesIO(b"%PDF-1.4\n"), []
    out.seek(0, 2)
    for i, obj in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    out.write(b"".join(b"%010d 00000 n \n" % o for o in offsets))
    out.write(b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue() + b"%%EOF\n" * (saves - 1)


def docx(body: str, core: str | None = None, app: str | None = None) -> bytes:
    """A Word document whose body is `body` (WordprocessingML), with the core properties and application given."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')
        if core is not None:
            z.writestr("docProps/core.xml", CORE.format(inner=core))
        if app is not None:
            z.writestr("docProps/app.xml", APP.format(name=app))
    return out.getvalue()


def run(text: str, props: str = "") -> str:
    """One run of text, with the run properties given (`<w:vanish/>`, a colour, a size, a font)."""
    return (
        f"<w:p><w:r><w:rPr>{props}</w:rPr><w:t>{text}</w:t></w:r></w:p>"
        if props
        else f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
    )
