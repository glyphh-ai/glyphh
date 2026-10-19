# Pricing

How Glyphh charges, every rule in one place. Free to adopt without limit on a developer's own machines; paid for
managed precedent volume, the managed hosting option and enterprise control. The code holds the numbers
(`db/seed.py`, the `fly_rates` table); this file holds the rules they follow. How billing works in the server
(the API, metering, the meter, the minute tick) is in [architecture.md](architecture.md#billing-and-hosting).

## The rules

1. **Never per seat.** Ada runs in code, not through human logins. Members are unlimited on every plan.
2. **Never per model.** Charging per model punishes organising data cleanly. Models are unlimited on every plan.
3. **Never a cap on installs.** Installs are unlimited on every plan.
4. **Ada is in every plan:** the full Ada math, every feature, unlimited local queries. No add-on.
5. **Self-hosting is free and unlimited** on every plan, Free included: a self-hosted or local runtime is never
   capped on precedents and never charged for infrastructure.
6. **What Glyphh charges for:** managed precedent volume, the managed hosting option and enterprise control.
7. **Hosting is passed through at Fly's cost plus a markup**, per second. The markup is never shown; Glyphh
   publishes its rates (the markup included) on the site and in the platform (`GET /v1/rates`).
8. **Enterprise is per customer:** its price, markup and term are set in each contract. No Enterprise rate is ever
   published: "Set in your contract."

## The plans

| | Free | Pro | Team | Enterprise |
|---|---|---|---|---|
| Price | $0 | $99 a month, flat | $299 a month, flat | From $10k a year, flat, by contract |
| How | Sign up | Stripe Checkout | Stripe Checkout | Talk to us (`sales@glyphh.ai`); granted by staff |
| Managed precedents | none | 100,000 | 1,000,000 | Unlimited |
| Hosted machines, the org's together | 0 | 3 | 10 | Unlimited |
| Hosting markup (never shown) | n/a | 30% | 30% | Per contract (the org's own) |
| Licence features | none | `sync` | `sync` | `sync`, `ha`, `offline`, `sso` |
| Members, installs, models, local and self-hosted runtimes and their precedents | Unlimited | Unlimited | Unlimited | Unlimited |

- The markups and the hosted machine counts are placeholders marked TBD in `db/seed.py` until Chris sets them.
- Plans are versioned: an org stays on the version it signed up on; a new price or limit is a new version with its
  own Stripe price.
- Of the features only `offline` is acted on: offline licences, Enterprise only (`POST
  /v1/runtimes/{id}/offline-licence` is 403 `E_NOT_IN_PLAN`, `reason: offline`, on every other plan). Licences by the
  link and by the daily heartbeat work on every plan, each with 14 days' grace for a self-hosted runtime. The other
  flags are signed into every licence and shown by rrotor; what they stand for is not built yet
  ([architecture.md](architecture.md#not-built-yet)).

## Precedent limits

- The bucket is a **total**: every precedent across all of a runtime's Ada models.
- It applies **only on a hosted runtime**. A local or self-hosted runtime's licence carries no limit.
- rrotor enforces it: a `record` that would take the runtime's total past the licence's `mods.ada.precedents` is
  refused (`E_LIMIT_PRECEDENTS`). Runs of different models at the same time each see the others' total as it was
  when they started, so together they can pass the cap by what they record meanwhile; each one's next run is refused.
- rrotor reports its total up the link; `GET /v1/billing` (and `/v1/me`) gives the org's hosted runtimes' sum against
  the bucket, `precedents: {used, limit}`, shown on the platform's Usage page.

## Hosted machines: what they cost

**Fly's rates** (`iad`, read 2026-10-18 from https://docs.fly.io/about/pricing; a 30-day month):

| Size | Fly preset | Fly $ a month |
|---|---|---|
| small | shared-cpu-1x, 1 GB | 6.70 |
| medium | shared-cpu-2x 2 GB ($13.39) plus 2 GB at $6.00 | 25.39 |
| large | performance-2x 4 GB ($66.00) plus 4 GB at $6.00 | 90.00 |
| Volume | per GB | 0.15 |

- A change at Fly is a new dated row in `fly_rates`; the rate in force is the newest not in the future. Per second
  is the 30-day rate ÷ 2,592,000.
- A machine is charged per second while its link is online, its volume always (the disk is kept either way). The
  charge is the cost × (1 + markup): the org's own markup when set (Enterprise's), else its plan's.
- The charge goes to Stripe's Billing Meter `glyphh_hosting` in whole cents: once a day, as the period ends, and
  before every plan change, each second counted once.
- The org sees its month so far, machine by machine, in `GET /v1/billing` and the connector's `usage`. The published
  rates (`GET /v1/rates`) give each size at Fly's rate × (1 + markup) for Pro and Team, never Fly's own rate or the
  markup.

## Changing plan

- **Free to Pro or Team:** Stripe Checkout, the flat price and the metered hosting price on one subscription.
- **Between Pro and Team:** Stripe prorates.
- **Down to Free:** the hosting due is reported and the subscription cancelled at once, invoiced and prorated.
- **Never below the machines held:** a change to a plan that allows fewer hosted machines than the org holds is
  refused ("Delete your hosted machines first."). An org that lands there anyway (a cancel in Stripe's portal, an
  Enterprise grant ending) keeps its oldest machines up to the plan's running; the newer ones are stopped and held,
  keeping their disks, until it deletes enough or moves up.
- **Enterprise** is never checked out, and changes only with Glyphh.

The calls, their refusals and holding machines past the plan are in
[architecture.md](architecture.md#billing-and-hosting).

## Stripe: once per account

```bash
STRIPE_SECRET_KEY=sk_test_… uv run python scripts/stripe-setup.py
```

Run in the server's repo with the account's secret key (`STRIPE_SECRET_KEY` or `GLYPHH_STRIPE_SECRET_KEY`; test
mode, then live). Idempotent: the products have Glyphh's own ids (`glyphh_pro`, `glyphh_team`, `glyphh_hosting`), the
prices are found by lookup key (`glyphh_pro_month_9900`, `glyphh_team_month_29900`, `glyphh_hosting_cent`) and the
meter by its event name. It makes the Pro and Team flat monthly prices (from `db/seed.py`), the Billing Meter
`glyphh_hosting` (summed; the customer from the event's `stripe_customer_id`, the cents from its `value`) and its
metered price (a cent a unit, monthly), and prints `GLYPHH_STRIPE_PRICE_PRO`, `GLYPHH_STRIPE_PRICE_TEAM`,
`GLYPHH_STRIPE_PRICE_HOSTING` and `GLYPHH_STRIPE_METER_HOSTING` with a `fly secrets set` line (run it in this repo,
whose `fly.toml` names `glyphh-ai-server`). `GLYPHH_STRIPE_WEBHOOK_SECRET` comes from the webhook endpoint
(`{server}/v1/stripe/webhook`). A new amount in the seed is a new price under a new lookup key.

## Enterprise: setting up a customer

Each Enterprise customer is on their own Stripe subscription, made by hand, and their deal is recorded on their org.

1. **They sign up** on the platform (https://platform.glyphh.ai), which makes their org. Get its id (Settings →
   General, or `GET /v1/org`).
2. **In Stripe:** the customer (the one the platform made if they ever checked out; a Pro or Team subscription they
   have is cancelled first, or the grant is refused, `E_CONFLICT` `subscribed`); a price for the contract (their
   product, the agreed amount, **yearly**); a subscription for the customer with two items, the contract price and
   the shared metered hosting price (`GLYPHH_STRIPE_PRICE_HOSTING`), collection method **send invoice** with the
   agreed terms. Note its id, `sub_…`.
3. **On the server**, record the deal:

   ```bash
   fly ssh console -a glyphh-ai-server -C "python -m glyphh_server.ops.enterprise grant \
     --org <org uuid> --until <YYYY-MM-DD> --markup <percent> --subscription <sub_...>"
   ```

   It reads the subscription from Stripe and records its customer. The org is on Enterprise through the end of the
   `--until` day (UTC); its hosting is metered at `--markup` (a percent, 0 or more) and reported to that
   subscription's customer; its licences carry Enterprise's limits and features from their next renewal (within 24
   hours, or at once on a runtime's next link). It prints what it recorded, or `Refused: …` and exits 1; a bad
   argument (a negative `--markup`, say) is a usage error, exit 2.
4. **Air-gapped:** they register each self-hosted runtime on the platform and issue its offline licence there (up
   to 365 days, 14 days' grace).

- **Renewing or changing the deal:** `grant` again with the new `--until`, `--markup` (from then on) or
  `--subscription` (replacing the old one on the org), and update Stripe to match.
- **Lapsing:** once the `--until` day has passed, the minute tick reports the hosting due to the deal's
  subscription, puts the org on Free and holds its hosted machines.
- **Ending:** `python -m glyphh_server.ops.enterprise revoke --org <org uuid>` does the same at once (it checks no
  plan: any org goes to Free) and prints how many machines it stopped; then cancel the subscription in Stripe. A
  deal's subscription that ends in Stripe also puts the org on Free.
- Self-hosted runtimes keep running; offline licences run to their expiry and grace.

**While the database is reset on every deploy** (`GLYPHH_RESET_DATABASE` in `fly.toml`,
[architecture.md](architecture.md#starting-up-and-the-reset-on-deploy)), every deploy drops every org and grant;
subscriptions in Stripe outlive it. Take paid customers and make grants only after the reset is turned off.
