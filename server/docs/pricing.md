# Pricing

How Glyphh charges for Ada Cloud. A plan sells the org's precedents, its reads a month and its calls a second;
**never per seat, per model or per key.** The numbers are `db/seed.py`'s, and callers read them from `GET /v1/plans`
(`ops/plans.py`).

## The plans

| | Free | Basic | Pro | Team | Enterprise |
|---|---|---|---|---|---|
| Price | $0 | $20 a month | $99 a month | $299 a month | By contract, a year at a time |
| Precedents, the org's across its models | 1,000 | 10,000 | 100,000 | 1,000,000 | By contract |
| Reads a month | 5,000, then refused | 50,000, then $1 per 10,000 | 1,000,000, then $1 per 10,000 | 5,000,000, then $1 per 10,000 | By contract |
| Calls a second | 5 | 10 | 50 | 200 | By contract |
| Hosted-model tokens a month (TBD) | 250,000 | 5,000,000 | 25,000,000 | 100,000,000 | By contract |
| Past the tokens | Charged to a prepaid balance | Charged to a prepaid balance | Charged to a prepaid balance | Charged to a prepaid balance | By contract |
| Single sign-on (OpenID Connect) | No | No | No | No | Yes |
| Members, installs, models, keys | Unlimited | Unlimited | Unlimited | Unlimited | Unlimited |

- **A read** is a `decide`, `query`, `probabilities` or `facts`: a decide once per output, a beam once per hop
  reached. Writes, learns, backtests, imports and exports are not reads. The month is the calendar month, UTC.
- **Past the month's reads,** a Free org is refused until the month turns (403 `E_LIMIT` `requests`, naming the plan
  that reads more); a Basic, Pro or Team org goes on, and each read past it is metered on Stripe's `ada_requests`
  Billing Meter, $1 per 10,000, on the same subscription as the plan's flat price.
- **The precedent cap** counts the new ids a write would add. An org already holding more than its plan's keeps
  every precedent, and only new ones are refused (`E_LIMIT` `precedents`) until it is under the cap or upgrades.
- **Calls a second** are the org's together, every call counted (writes and job polls too): past them, 429 `E_RATE`
  with `Retry-After`.
- **Basic, Pro and Team are bought** through Stripe Checkout (`GLYPHH_STRIPE_PRICE_BASIC`, `_PRO`, `_TEAM`); Free
  needs no card. **Enterprise is by contract,** granted by Glyphh's staff and never bought: its limits are each
  contract's (none in the code), and it alone has single sign-on.
- **A plan version never changes its price or limits.** A new price or new limits are a new version; an org stays on
  the version it subscribed to, except that a change of only the Ada Cloud limits or the token allowance moves every
  org on the plan to the new version at the next start ([architecture.md](architecture.md#data-model)).
- The whole of Ada Cloud's plans and metering is in [specs/ada-cloud.md](specs/ada-cloud.md#7-plans-and-metering).

## Glyphh-hosted models

Off unless `GLYPHH_LLM` is on ([specs/tokens.md](specs/tokens.md)). A plan's tokens a month draw down first; past
them, input and output tokens are charged in dollars, never credits, against a prepaid balance the org's admin tops
up ($10 to $1,000 at a time). With no tokens and no balance left a request is refused, 402 `E_BALANCE`. Free may buy
a balance too. Every allowance and rate is a placeholder until Chris sets it.

Rates, in dollars per million tokens past the plan's month; the price on the page is the charge on the bill:

| Model | Id | Context | Input | Output |
|---|---|---|---|---|
| adaL 34B 1.0 | `adal-34b-1-0` | 32,768 tokens | $0.60 | $2.40 |

## Setting up

- **Stripe, once per account:** `STRIPE_SECRET_KEY=sk_… uv run python scripts/stripe-setup.py` (safe to run again,
  prices found by lookup key) makes the flat prices and Ada Cloud's metered reads' price and meter, and prints their
  settings.
- **Enterprise** is an annual invoice on its own Stripe subscription, recorded on the org from the staff view
  (`POST /v1/admin/orgs/{id}/enterprise`) or on the server's machine (`fly ssh console -a glyphh-ai-server`) with
  `python -m glyphh_server.ops.enterprise grant --org <uuid> --until <YYYY-MM-DD> --subscription <sub_…>`, and ended
  with `revoke --org <uuid>`. When the date passes the org is back on Free. Grants survive deploys: production keeps
  its data ([architecture.md](architecture.md#starting-up-and-migrations)).
