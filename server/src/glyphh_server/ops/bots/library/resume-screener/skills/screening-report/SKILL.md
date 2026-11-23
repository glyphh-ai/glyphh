---
name: screening-report
description: How the result of a screening is told to the person. Use it whenever you have screened one or more job applications and are about to answer with their verdicts.
---

# The screening report

After a screening the person wants to know, at a glance, who is worth their time. The report is your answer: a
count, then one line per applicant.

## Format

```
5 screened: 1 strong, 2 borderline, 1 poor, 1 spam.

- **Ana Ruiz** (Backend Engineer) - strong (0.86). Real applicant (0.93). Written by a person.
- **Tom Blake** (Backend Engineer) - borderline (you decided). Real applicant (0.88). Mostly generated (0.71).
- **jobs@bulk-apply.io** - spam (0.95).
```

- **First line**: how many were screened and the count of each verdict, leaving out the ones with none. Add
  `N refused by the sender checks` when messages were refused before screening, and `N waiting on your answer` when
  some have no verdict yet.
- **One line per applicant**, strong first, then borderline, poor, spam, and those still waiting last:
  - their name (their address when there is no name) and the role they applied for;
  - the verdict, with its confidence in brackets as a number to two places, or `you decided` when the person gave
    the answer;
  - for a real applicant: `Real applicant` with its confidence, then how much was generated: `Some generated`,
    `Mostly generated` or `Fully generated` with its confidence, or `Written by a person` when the answer was
    `human`.
- One applicant, handed in by the person: skip the count line and give that applicant's line, then one more
  sentence on what stood behind the fit (years, skills, titles, as the application states them).

## Tone

Fair, plain and quick. A verdict is a screening, not a judgement of the person: write "poor fit for this role",
never "a poor candidate".

## What to leave out

- Anything the application does not state. Never invent or round up experience, skills or employers.
- Advice on whom to hire or reject: the person decides that.
- The applications' text, the applicants' contact details beyond name or address, and how the checks work inside.
- A confidence you were not given: when there is none, give the verdict alone.
