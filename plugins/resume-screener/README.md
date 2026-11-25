# Resume Screener

A Glyphh template as a plain Claude plugin. It screens a job application with **your own Ada models**:

1. **Is this a real person?** Answered from independent signals, each its own Ada model:
   - **the email's timestamps**: the `Date` header against each `Received` hop, their order, the gaps, a date in
     the future, an odd hour on the sender's clock, a burst of applications arriving together;
   - **the files themselves**: hidden, white or tiny text, characters never seen, tracked changes, marks of
     pasting from a chat, the program and author the file names;
   - **this application against the others seen**: the same work history under another name, the same phrasing,
     a shared phone or address, a burst of near-identical applications;
   - **Greenhouse signals**, when you have a Greenhouse connector in Claude (unproven, see below);
   - voice recording: **not built** ([docs/voice.md](docs/voice.md)).
2. **How well do they fit the role?** Strong, borderline or poor, from the resume read section by section.
3. One line: how much of the text reads as generated.

Code reads and measures. Ada decides, from precedents. When Ada is unsure, Claude asks you, and your answer becomes
a precedent.

**Nothing here is proven on real applicants or real fraud.** Every number we have was measured on generated
applications and on cases made for the purpose. Read [docs/checks.md](docs/checks.md) before you rely on it.

## Install

```
/plugin marketplace add glyphh-ai/plugins
/plugin install resume-screener@glyphh-plugins
```

You also need:

- an Ada Cloud account, and the Glyphh connector in Claude (its `ada_*` tools). Without the connector the skill
  uses the `glyphh` SDK instead (`pip install glyphh`, then `glyphh login`);
- Python 3.11 or later with `pypdf` (`pip install pypdf`).

## Set up your models

Ask Claude to "set up the Resume Screener", or run it yourself:

```
pip install glyphh pypdf
glyphh login
python plugins/resume-screener/skills/screen-application/scripts/seed.py
```

It makes six models in your account, loads the examples that ship with the plugin, and runs Ada's learning. It
takes a few minutes and can be run again safely.

The models, all in your own account:

| Model | Decides | Starts with |
|---|---|---|
| `screener-timing` | fine or suspect, from the email's timestamps | nothing: learns from your answers |
| `screener-files` | fine or suspect, from what the files themselves say | nothing: learns from your answers |
| `screener-others` | holds every application seen; Ada's nearest ones are compared | the 1,980 examples |
| `screener-greenhouse` | fine or suspect, from the candidate's Greenhouse record | nothing: learns from your answers |
| `screener-fit` | strong, borderline or poor | the 1,980 examples |
| `screener-made` | how much reads as generated: some, mostly, fully | the 1,980 examples |

Their specs, with weights, are in [`skills/screen-application/models`](skills/screen-application/models), and the
examples beside them in `models/examples`: each model's cases with their outcomes, one a line.

**Every example is a generated, fictional application.** A program wrote them; no real person is in them. They
are the train split of the corpus the checks used; its test split is not here.

## Use

In Claude, with the application's files at hand:

> Screen this application: application.eml

> Screen this applicant for Backend Engineer: (the email's text), resume.pdf, cover_letter.docx

Claude runs the steps in [the skill](skills/screen-application/SKILL.md) and answers with the verdict: real person,
suspect or unsure, with what each signal found; then the fit; then one line on how it was written.

When the Glyphh connector offers its `screener_verdict` tool, the verdict is also shown as a card, and you can
answer on the card when Ada is unsure of a signal.

Give it the email as an `.eml` file when you can. The timestamps are in the email's headers; a pasted email
without them cannot be checked for timing, and the verdict says so.

## What it keeps

Each screened application is recorded in your `screener-others` model (its work history, phrasing, contact details
and arrival time), so the next one can be compared with it. Tell Claude not to keep an application and it is not
recorded. The scripts' work folder holds the application's text during a screening and is deleted after.

## Greenhouse

The plugin ships no Greenhouse connection. If you have a Greenhouse connector in Claude, the skill reads the
candidate and the application through it and the `screener-greenhouse` model decides on what Greenhouse's Harvest
v3 API returns: the source, whether it was referred, the screening answers, the contact details on the record.
Harvest gives no IP address, no browser and no time taken to fill in the form, so none of those is used.
**Unproven:** written from Greenhouse's API reference, never run against a real Greenhouse account.

## The code

Everything deterministic is in
[`skills/screen-application/scripts/screener`](skills/screen-application/scripts/screener): plain Python, no model
of any kind. Tests: `pip install pytest pypdf && pytest plugins/resume-screener/tests`.

## Licence

MIT.
