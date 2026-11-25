"""The Resume Screener's file checks on files made for the purpose (screener/filefacts.py; crafted.py):
the corpus cannot score them (one renderer made every file of it), so what they catch is proven here: text drawn
invisibly, in white and tiny in a PDF and in a Word document, edited metadata, a file saved over, another's name as
author, an AI tool's name, characters never seen, marks of pasting from a chat, tracked changes; a clean file
raises nothing; and a file that cannot be walked is still read for its words' own marks."""

from crafted import docx, pdf, run
from screener import applicants, checks, filefacts, filefacts_docx, filefacts_pdf
from screener import mail as gmail

SEEN: str = "BT /F1 11 Tf 50 750 Td (Ann Lee) Tj 0 -14 Td (Skills: sql) Tj ET"
UNSEEN: str = (
    "BT /F1 11 Tf 50 750 Td (Ann Lee) Tj "
    "3 Tr (python kubernetes) Tj 0 Tr "
    "1 1 1 rg [(aws) -20 (gcp)] TJ 0 0 0 rg 1 g (rust) ' 0 g 0 0 0 0 k (go) Tj 0 0 0 1 k "
    "/F1 1 Tf (ten years) Tj /F1 11 Tf (seen) Tj ET"
)
INFO: str = "/Producer (Microsoft Word 16.0) /Creator (Word) /Author (Ann Lee) /CreationDate (D:20260101120000Z) {mod}"


def test_a_clean_pdf_raises_nothing_and_says_what_made_it() -> None:
    got = filefacts.of("pdf", pdf(SEEN, INFO.format(mod="/ModDate (D:20260101120010Z)")), "Ann Lee\nSkills: sql")
    assert (got["hidden"], got["white"], got["tiny"], got["unseen"], got["pasted"], got["saves"]) == (0, 0, 0, 0, [], 1)
    assert (got["producer"], got["author"], got["fonts"]) == ("Microsoft Word 16.0", "Ann Lee", ["Helvetica"])
    file = checks.filed({"file": filefacts.whole(got, filefacts.NONE, "Ann Lee")})
    assert file["file"]["flags"] == ["none"] and file["found"]["files"] == ["nothing unusual in the pdf file"]
    assert (file["file"]["tool"], file["file"]["author"], file["file"]["edited"]) == (
        "microsoft word",
        "applicant",
        "never",
    )
    assert file["file"]["same_tool"] == "one" and "tools_said" not in file["file"]


def test_text_a_reader_cannot_see_in_a_pdf_is_counted() -> None:
    got = filefacts_pdf.facts(pdf(UNSEEN))
    assert got["hidden"] == len("python kubernetes")  # drawn with text rendering mode 3
    assert got["white"] == len("awsgcp") + len("rust") + len("go")  # white in RGB, grey and CMYK
    assert got["tiny"] == len("ten years")  # one point high
    file = filefacts.whole(filefacts.NONE | got | filefacts.marks("") | {"kind": "pdf"}, filefacts.NONE, "Ann Lee")
    assert filefacts.flags(file) == ["hidden_text", "white_text", "tiny_text"]
    assert filefacts.found(file | {"flags": filefacts.flags(file)})[0].startswith("text a reader cannot see")
    assert filefacts_pdf.unseen([([], b"Tj")]) == {"hidden": 0, "white": 0, "tiny": 0}  # an operator with nothing


def test_edited_metadata_a_resaved_file_and_another_author_are_said() -> None:
    later = INFO.format(mod="/ModDate (D:20260103120000Z)").replace("Ann Lee", "Bob Stone")
    got = filefacts.of("pdf", pdf(SEEN, later.replace("Microsoft Word 16.0", "ChatGPT"), saves=3), "")
    file = filefacts.whole(got, filefacts.of("pdf", pdf(SEEN, "/Producer (Skia/PDF m120)"), ""), "Ann Lee")
    assert (file["edited"], file["saves"], file["author"], file["same_tool"]) == ("days", 3, "other", "no")
    assert filefacts.flags(file, file["tools_said"]) == ["other_author", "ai_tool"]
    assert filefacts._gap("2026-01-01T12:00:00", "2026-01-01T12:20:00") == "minutes"
    assert filefacts._gap("2026-01-01T12:00:00", "2026-01-01T15:00:00") == "hours"
    assert filefacts._gap("", "2026-01-01T15:00:00") == "unknown" and filefacts_pdf.stamp("soon") == ""
    assert filefacts._author("anonymous", "Ann Lee") == "none" == filefacts._author("", "Ann Lee")
    assert filefacts.tool("") == "none" and filefacts.tool("LibreOffice 7.4 (x64) Writer") == "libreoffice writer"


def test_a_word_file_says_its_hidden_runs_tracked_changes_and_who_saved_it() -> None:
    body = (
        run("Ann Lee") + run("python kubernetes", "<w:vanish/>") + run("aws", '<w:color w:val="ffffff"/>')
        + run("ten years", '<w:sz w:val="2"/><w:rFonts w:ascii="Arial"/>') + run("big", '<w:sz w:val="22"/>')
        + run("plain", '<w:rFonts w:hAnsi="Calibri"/>') + "<w:ins><w:r><w:t>added</w:t></w:r></w:ins><w:del/>"
    )  # fmt: skip
    core = (
        "<dc:creator>Ann Lee</dc:creator><cp:lastModifiedBy>Bob Stone</cp:lastModifiedBy><cp:revision>7</cp:revision>"
        "<dcterms:created>2026-01-01T12:00:00Z</dcterms:created><dcterms:modified>2026-01-01T12:30:00Z</dcterms:modified>"
    )
    got = filefacts_docx.facts(docx(body, core, "Microsoft Office Word"))
    assert (got["hidden"], got["white"], got["tiny"], got["tracked"]) == (len("python kubernetes"), 3, 9, 2)
    assert (got["producer"], got["author"], got["saves"], got["fonts"]) == (
        "Microsoft Office Word",
        "Ann Lee Bob Stone",
        7,
        ["Arial"],
    )
    file = filefacts.whole(
        filefacts.of("docx", docx(body, core, "Microsoft Office Word"), ""), filefacts.NONE, "Ann Lee"
    )
    assert filefacts.flags(file) == ["hidden_text", "white_text", "tiny_text", "tracked_changes"]
    assert (file["edited"], file["author"], file["kind"]) == ("minutes", "applicant", "docx")
    bare = filefacts_docx.facts(docx(run("Ann Lee"), "<cp:revision>draft</cp:revision>"))
    assert (bare["saves"], bare["producer"], bare["author"], bare["created"]) == (1, "", "", "")


def test_the_words_own_marks_are_found_in_any_file_even_one_that_cannot_be_walked() -> None:
    said = "Ann​ Lee\n**Summary**\nDear [Hiring Manager],\nHere is a polished cover letter for the role."
    got = filefacts.of("pdf", b"not a pdf at all", said)
    assert (got["kind"], got["unseen"], got["pasted"], got["producer"]) == (
        "pdf",
        1,
        ["chat", "markdown", "placeholder"],
        "",
    )
    assert filefacts.of("docx", b"PK not a zip", "")["tracked"] == 0
    assert filefacts.of("text", b"", "plain words")["pasted"] == []
    file = filefacts.whole(got, filefacts.NONE, "Ann Lee")
    assert filefacts.flags(file) == ["unseen_characters", "pasted"]
    try:
        filefacts_docx.facts(docx("").replace(b"word/document.xml", b"word/documexx.xml"))
    except ValueError as err:
        assert "no document" in str(err)
    else:  # pragma: no cover
        raise AssertionError("a zip with no document in it was read")


def test_an_application_from_the_inbox_carries_its_files_facts() -> None:
    heads = {"from": "Ann Lee <ann@b.co>", "subject": "Data Analyst", "received-spf": "pass (ok)"}
    files = [("letter.pdf", "pdf", pdf("BT /F1 11 Tf (Dear team, sincerely) Tj ET")), ("cv.pdf", "pdf", pdf(UNSEEN))]
    got, _ = applicants.of_mail(gmail.Mail("m", heads, "Hello", files))
    assert got is not None and got["file"]["flags"] == ["hidden_text", "white_text", "tiny_text"]
    assert got["file"]["same_tool"] == "yes" and got["found"]["files"][0].startswith("text a reader cannot see")
    none, _ = applicants.of_mail(gmail.Mail("m", heads, "Hello, I would like the job.", []))
    assert none is not None and none["file"]["kind"] == "none" and none["found"]["files"] == ["no file"]
    assert checks.filed({})["file"]["flags"] == ["none"]
