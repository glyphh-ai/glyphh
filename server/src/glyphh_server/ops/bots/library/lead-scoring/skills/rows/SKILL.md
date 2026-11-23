---
name: rows
description: How a hot lead becomes a row of the leads sheet. Use it whenever you write the rows for the hot leads, before you add them to the Google Sheet.
---

# A lead as a sheet row

Each hot lead becomes one row of the sheet. A row is a list of six strings, in this order:

| # | Cell | What it holds |
|---|---|---|
| 1 | Date | Today, as `YYYY-MM-DD` |
| 2 | Name | The lead's name |
| 3 | Company | Their company |
| 4 | Role | Their role |
| 5 | Asked | What they asked for |
| 6 | First line | A suggested first line for the call |

Example:

```
["2026-11-23", "Ana Ruiz", "Acme", "VP Engineering", "a demo", "You asked for a demo: which team would use it first?"]
```

## Rules

- One row per hot lead, in the order the leads came in. Warm and cold leads get no row.
- A cell with nothing to say is an empty string, never `n/a` or a dash. Every row has all six cells.
- Copy name, company, role and what they asked for as the lead gave them. Never fill a gap with a guess.

## The first line

One honest sentence the person could open the call with, built only on what the lead said: what they asked for,
their role, their company. Under 20 words. A question is best.

Leave out flattery, anything you could not know about them or their company, and any claim about the product.
