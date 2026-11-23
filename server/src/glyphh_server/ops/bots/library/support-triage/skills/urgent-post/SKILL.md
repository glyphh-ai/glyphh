---
name: urgent-post
description: How the Slack post about urgent support tickets is written. Use it whenever you write up the urgent tickets for the team, before you post them to Slack or give them as your answer.
---

# The urgent-ticket post

The post tells the support team, in their Slack channel, which tickets cannot wait: who wrote, what is broken, how
bad it is, and a first reply someone could send now.

## Format

One block per ticket, a blank line between blocks, nothing above the first:

```
*Customer* - what is broken, in one line.
How many people it stops.
> "A suggested first reply."
```

- **Customer**: the company or the person's name in bold (Slack bold is `*name*`), else their address.
- **What is broken**: one line, in the customer's terms, not ours.
- **How many people it stops**: what the email says ("their whole team", "one user", "checkout for every buyer").
  When it does not say, write `Does not say how many are affected.`
- **Suggested first reply**: one or two sentences in quotes that acknowledge the problem and say what happens next.

## Order

Most urgent first: an outage, data loss or a payment failure before anything else, then by how many people are
stopped.

## Length and tone

- Three lines per ticket, at most ten tickets. When more are urgent, post the ten worst and end with
  `and N more urgent.`
- Calm, short and exact. No greeting, no sign-off, no exclamation marks.

## What to leave out

- Tickets sorted as normal or spam: never list them in the post.
- Any promise of a fix or a date, in the post or in the suggested reply: the team decides that.
- A diagnosis: say what the customer reports, never what you think caused it.

## Example

```
*Acme Co* - nobody on their team can sign in since 9:10.
Stops their whole team (about 40 people).
> "Thanks for telling us. We can see the sign-in failures on your account and an engineer is looking now; we will write again as soon as we know more."
```
