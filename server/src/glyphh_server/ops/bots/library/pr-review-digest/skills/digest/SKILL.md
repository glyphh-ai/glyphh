---
name: digest
description: How a review digest is written. Use it whenever you write up the pull requests that need the person's review, before you post the digest to Slack or give it as your answer.
---

# The review digest

A digest tells one engineer which pull requests need them today and where to start on each. They read it in Slack,
between other things: it has to be useful in ten seconds.

## Format

One line per pull request, nothing above the first line:

```
<link|title> - who asked, how long it has waited, what to look at first
```

- **Link and title**: the pull request's own URL and title, as Slack writes a link: `<https://github.com/acme/api/pull/42|Fix the retry loop>`.
- **Who asked**: the author's login.
- **How long it has waited**: from when it was opened or last updated, in plain words ("2 days", "since Monday").
- **What to look at first**: one short phrase taken from the title, the labels or the description ("the migration",
  "the new retry limit"). When they say nothing useful, write "start with the description".

End with one line saying how many were left for later: `3 more left for later.` Leave that line out when none were.

## Order

Blocking work first: a pull request that blocks a release, then one that blocks another person, then the oldest.

## Length and tone

- At most ten pull requests. When more need review today, list the ten most blocking and count the rest in the last
  line.
- Direct and useful. No greeting, no sign-off, no headings, no summary of the summary.

## What to leave out

- Any opinion of the code: you have not read it. Say where to look, never whether it is good.
- Pull requests decided for later: they are only counted.
- Anything the search did not return: no guessed sizes, reviewers or deadlines.

## Example

```
<https://github.com/acme/api/pull/42|Fix the retry loop> - maria, 2 days, the new retry limit (blocks the 3.2 release)
<https://github.com/acme/web/pull/310|Move billing to the new client> - sam, since Monday, the migration
2 more left for later.
```
