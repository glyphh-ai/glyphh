---
name: screen-application
description: Screen a job application with the person's own Ada models - first whether it comes from a real person (the email's timestamps, the files themselves, the application against the others seen, Greenhouse signals when there are any), then how well it fits the role. Use when the person asks to screen, check or vet a job application, a resume, a cover letter or an applicant's email, asks whether an applicant is real, or asks to set up or seed the Resume Screener.
---

# Screen a job application

You run fixed steps, in a fixed order. Code reads and measures the application; Ada models decide; the person is
asked when Ada is unsure, and their answer becomes a precedent. You never judge the application yourself and you
never change a case before it is decided.

The first question is always **is this a real person**, answered from independent signals, each its own Ada model.
How well they fit the role is second. Whether the text reads as AI-written is one line at the end and never changes
anything.

## What you need

- The Glyphh connector's `ada_*` tools. If they are not there, use `scripts/run.py` instead (it asks Ada through
  the Glyphh SDK with the person's own key: `pip install glyphh pypdf`, then `glyphh login`), and tell the person
  that is what you did.
- Python 3.11 or later with `pypdf` (`pip install pypdf`) to read PDF files.
- The scripts are in this skill's folder: `${CLAUDE_PLUGIN_ROOT}/skills/screen-application/scripts`.

## Before the first screening: the models

Call `ada_models`. The screener's six models are named `screener-fit`, `screener-files`, `screener-timing`,
`screener-others`, `screener-made` and `screener-greenhouse`. If any is missing, set the screener up:

```
pip install glyphh pypdf
glyphh login          # once; or set GLYPHH_API_KEY
python scripts/seed.py
```

It makes the six models in the person's own account, loads the examples that ship with the plugin (1,980
generated, fictional applications) into `screener-fit`, `screener-made` and `screener-others`, and runs Ada's
learning. It takes a few minutes and can be run again safely. `screener-files`, `screener-timing` and
`screener-greenhouse` start empty and learn from the person alone. Tell the person what it did.

## The steps

Use one new empty work folder per application (for example `mktemp -d`).

**1. Read.** Get the application as files on disk: the email as an `.eml` file when you can (it carries the
timestamps), else its words in a text file, with the headers above them if the person has them; and the resume and
cover letter (PDF or DOCX), in any order.

```
python scripts/screen.py read --work <dir> --eml application.eml
python scripts/screen.py read --work <dir> --email email.txt --file resume.pdf --file cover_letter.docx --role "Backend Engineer"
```

If it prints `refused`, stop: tell the person why (for example, the sender's domain did not vouch for the
message). Otherwise it prints `asks`.

**2. Ask Ada which applications it holds are nearest.** For each of `asks`, call `ada_facts` with `name`
(`screener-others`), `data` and `top` exactly as given. Write the answers to a file as
`{"<part>": <the tool's answer>, ...}`.

**3. Compare and check.**

```
python scripts/screen.py compare --work <dir> --facts facts.json
```

It prints `found` (what each check found, in sentences) and `cases`.

**4. Ask Ada to decide.** For each of `cases`, call `ada_decide` with `name` (its `model`) and `data` exactly as
given. Write the answers to a file as `{"<signal>": <the tool's answer>, ...}`.

**5. The verdict.**

```
python scripts/screen.py verdict --work <dir> --answers answers.json
```

It prints the verdict: `person` (`real person`, `suspect` or `unsure`, and each signal with what it says and what
it found), `fit`, `made`, and `keep`.

**6. Show the card, and ask the person when asked to.** If the connector has the tool `screener_verdict`, call it
with the verdict from step 5 (without `keep`): it shows the verdict as a card, and for a signal Ada was unsure of
the person can answer on the card, which records the answer itself and tells you. Without the card, or when the
person answers in the chat: for each signal in `person.ask`, tell the person what that signal found and ask: is
this fine, or suspect? Record each answer with `ada_record`: the signal's `teach.args` (`name` and `data`) and
`outcome` `fine` or `suspect`. Never record the same answer twice. Then run step 5 again with
`--told <signal>=<answer>` for each answer given.
For the `others` signal there is no case to record: only pass `--told others=<answer>`.
If `fit.ask` is true, ask the person how well the applicant fits (strong, borderline or poor) and record it in
`screener-fit` the same way. Never record your own guess: only what the person said.

**7. Keep.** Call `ada_record` with `keep`'s `name` (its `model`), `data` and `outcome`, so the next application
is compared with this one. If the person told you the application repeats another, record `repeat` instead of
`alone`. Skip this step if the person asked you not to keep the application.

**8. Tell the person**, in this order and in plain words:

1. Real person, suspect or unsure, and for each signal what it found and who said so (Ada, with its confidence;
   the rule, when Ada had no close precedent; or the person).
2. The fit: strong, borderline or poor, with Ada's confidence, and what stood behind it.
3. One line: how much of the text reads as generated (`made`), or that Ada is unsure.

Then delete the work folder.

## Greenhouse

This plugin ships no Greenhouse connection. When the person has a Greenhouse connector in Claude and the applicant
is a Greenhouse candidate, read the candidate and the application with that connector (Harvest v3:
`GET /v3/candidates` and `GET /v3/applications` filtered to the candidate), write them to a file as
`{"candidate": {...}, "application": {...}}` exactly as returned, and pass `--greenhouse <file>` in step 1. The
verdict then has a `greenhouse` signal. This part is unproven: it was written from Greenhouse's API reference and
has never been run against a real Greenhouse account. Say so when you report it.

## Voice

Not built. Checking a voice recording is an open question (where the recording comes from, and what is judged).
There is no step for it; do not improvise one.

## Rules

- A verdict is a screening, not a judgement of the person. Never say a person is fake: say what was found.
- Nothing here has been proven on real applicants or real fraud. If the person asks how reliable it is, point them
  to `docs/checks.md` in the plugin and say plainly what was and was not measured.
- Say only what the application states. Never invent experience, skills or employers.
- Do not advise whom to hire or reject.
