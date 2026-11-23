---
name: report
description: How the weekly report is written. Use it whenever you turn a week of merged pull requests into the team's report, before it is decided whether to file it in Notion.
---

# The weekly report

The report turns a week of merged pull requests into something the whole company can read: what shipped, why it
matters, what is next. Its readers are not all engineers.

## What you write

Three things:

| Part | What it holds |
|---|---|
| `title` | `Week of <that week's Monday, YYYY-MM-DD>` |
| `highlights` | One line: the two or three changes that mattered most, in customer words |
| `body` | The report itself, in the three sections below |

The title and the highlights are what the decision to file it reads, so write them with the same care as the body.

## The body

```
## Shipped
- Customers can now export invoices as CSV (billing).
- Sign-in is twice as fast on slow connections.

## Fixed
11 fixes this week. The two that mattered most:
- Exports no longer drop the last row.
- Password reset emails arrive again for Outlook addresses.

## Next
The open work points to team invoices and a faster dashboard.
```

- **Shipped**: the five most important changes, one line each, customer words first ("Customers can now ...", not
  "Refactored the exporter").
- **Fixed**: how many fixes merged, then the two that mattered most.
- **Next**: one or two lines on what the open work points to, only from what the pull requests show.

## Length and tone

- Under 300 words. Clear and confident, never hype: no "exciting", no "huge".
- Group small changes into one line ("Six small improvements to the settings pages").

## What to leave out

- A line per pull request or per commit: this is a report, not a changelog.
- Any impact the pull requests do not show: no numbers, customers or dates you were not given.
- Internal-only work (refactors, dependency bumps, CI) unless it changes what a customer sees; count it at most.
- Authors' names and pull request numbers.
