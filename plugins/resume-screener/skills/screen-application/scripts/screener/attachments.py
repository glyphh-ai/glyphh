"""Which of an application's attachments is the resume and which the cover letter (applicants.py), in
whatever order they were attached. A file's name says it when it names one and not the other (resume, CV; cover,
letter); else its words do: a resume has section headings on lines of their own (Experience, Education, Skills), a
letter greets and signs off. The resume is the file that leans most to a resume, the first of them when several lean
alike, so a single file, or files that say nothing, are read as before: the first is the resume. A file that leans to
a letter, of those left, is the cover letter; any other file is not read as either."""

import re

Read = tuple[str, str, str]  # a readable attachment: its name, kind and text

RESUME_NAME: re.Pattern[str] = re.compile(r"resume|résumé|(?<![a-z])cv(?![a-z])|curriculum|vitae", re.I)
LETTER_NAME: re.Pattern[str] = re.compile(r"(?<![a-z])cover|letter|motivation", re.I)
HEADING: re.Pattern[str] = re.compile(
    r"^\s*(?:work |professional |technical )?(?:experience|employment|education|skills|summary|projects|"
    r"certifications)\s*(?::.*)?$",
    re.I | re.M,
)
LETTER: re.Pattern[str] = re.compile(r"^\s*dear\b|\b(?:sincerely|regards|yours truly|yours faithfully)\b", re.I | re.M)
NAMED: int = 100  # a name that says which outweighs any words


def leaning(name: str, text: str) -> int:
    """Above zero: a resume; below: a cover letter; zero: nothing says."""
    by_name = bool(RESUME_NAME.search(name)) - bool(LETTER_NAME.search(name))
    return by_name * NAMED if by_name else len(HEADING.findall(text)) - len(LETTER.findall(text))


def pick(files: list[Read]) -> tuple[int | None, list[int]]:
    """Which of the readable attachments is the resume (None: there are none), and which are cover letters."""
    if not files:
        return None, []
    leans = [leaning(name, text) for name, _, text in files]
    at = leans.index(max(leans))
    return at, [i for i in range(len(files)) if i != at and leans[i] < 0]


def split(files: list[Read]) -> tuple[str, str, str]:
    """(the resume's text, its kind, the cover letter's text) of an application's readable attachments."""
    at, letters = pick(files)
    if at is None:
        return "", "none", ""
    return files[at][2], files[at][1], "\n\n".join(files[i][2] for i in letters)
