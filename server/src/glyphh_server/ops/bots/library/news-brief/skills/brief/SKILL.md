---
name: brief
description: How the news brief is written. Use it whenever you write up the front-page stories the person would read, before you give the brief as your answer.
---

# The news brief

A brief is five minutes of tech news for one reader: only the stories they would read, each with what happened and
why it matters to them.

## Format

One entry per story, a blank line between entries, nothing above the first:

```
**[The story's title](its link)**
What happened, in one line.
Why it matters, in one line.
```

- **Title and link**: the story's own title, linked to its `url`. A story with no `url` (a discussion on Hacker
  News itself) links to `https://news.ycombinator.com/item?id=<its objectID>`.
- **What happened**: the news itself, in plain words, from the title and what the story's data says.
- **Why it matters**: what it changes for someone who builds software, not a restatement of the title.

## Order

The most important first: what changes how people work, then what is new, then what is merely interesting.

## Length and tone

- At most eight stories. When more would be read, keep the eight that matter most.
- Two lines per story. No intro, no outro, no "today on Hacker News".
- Curious and to the point.

## What to leave out

- Stories decided as not worth reading: never list or count them.
- Padding on a slow day: three good stories are a brief; do not stretch them.
- Anything the story's data does not support. You have the title, the link, the points and the comment count, not
  the article: when the title alone does not say what happened, say what it is about and no more.
- Points and comment counts, unless they are the news.
