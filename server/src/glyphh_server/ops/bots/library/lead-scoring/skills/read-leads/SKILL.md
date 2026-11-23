---
name: read-leads
description: How pasted leads are read into one item per lead. Use it whenever the person gives you leads in any form (a form's answers, an event list, an export, a few lines of text), before the leads are scored.
---

# Reading leads

Leads arrive pasted in any shape. Before they are scored, read them into a list with one item per lead, every item
with the same five fields.

## The item

| Field | What it holds |
|---|---|
| `name` | The person's name, as written |
| `email` | Their email address, as written |
| `company` | The company they work for |
| `role` | Their job title or role |
| `asked` | What they asked for, in their own words ("a demo", "pricing for 50 seats") |

Example: `Ana Ruiz, ana@acme.com, VP Engineering at Acme, asked for a demo` becomes

```
{"name": "Ana Ruiz", "email": "ana@acme.com", "company": "Acme", "role": "VP Engineering", "asked": "a demo"}
```

## Rules

- **Read exactly what is given.** Never invent a company, a role or a need. A field the lead does not give is an
  empty string. Do not work a company out from an email's domain unless the lead says nothing else and the domain is
  plainly a company's (never for gmail.com, outlook.com and the like).
- **One item per person.** The same email twice is one lead: keep the entry that says more.
- **A lead needs a name and an email.** Leave out a line with neither, and say how many you left out and why.
- **Keep the order** the leads came in.
- At most 50 leads at once: read the first 50 and say how many were left over.

## What to leave out

Headers, totals, signatures, and any line that is not a lead.
