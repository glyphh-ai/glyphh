# Pricing

How Glyphh charges, every rule in one place (Chris, 2026-10-18). An open-core model, like PostHog, GitLab, HashiCorp
and Kong: free to adopt without limit on a developer's own machines; paid for managed precedent volume, the managed
hosting option and enterprise control. The code holds the numbers (`db/seed.py`, the `fly_rates` table); this file
holds the rules they follow.

## The rules

1. **Never per seat.** Ada runs in code, not through human logins. Members are unlimited on every plan.
2. **Never per model.** Charging per model punishes organising data cleanly. Models are unlimited on every plan.
3. **Never a cap on local installs.** Capping local developer installs on Free kills adoption. Installs are unlimited
   on every plan.
4. **Ada is in every plan.** The full Ada math, every feature, unlimited local queries. No add-on.
5. **Self-hosting is free and unlimited** on every plan, Free included: a self-hosted or local rrotor is never
   capped on precedents and never charged for infrastructure. What a paid plan adds is syncing many instances.
6. **What Glyphh charges for:** managed precedent volume, the managed hosting option, and enterprise control.
7. **Hosting is passed through at Fly's cost plus a markup**, per second. The person never sees the markup; Glyphh
   publishes its rates (the markup included) on the site and in the platform.
8. **Enterprise is per customer:** its price, its markup and its term are set in each contract. No Enterprise rate is
   ever published: "Set in your contract."

## The plans

| | Free | Pro | Team | Enterprise |
|---|---|---|---|---|
| Price | $0, forever | $99 a month, flat | $299 a month, flat | From $10k a year, flat, by contract |
| How | Sign up | Stripe Checkout | Stripe Checkout | Talk to us (`sales@glyphh.ai`) |
| Managed precedents | none (local and self-hosted unlimited) | 100,000 | 1,000,000 | Unlimited |
| Hosted machines | 0 | 3 | 10 | Unlimited |
| Hosting markup | n/a | 30% | 30% | Per contract |
| Precedent-store sync across instances | No | Yes | Yes | Yes |
| Offline (air-gapped) licences, HA, SSO/SAML, RBAC, audit logs | No | No | No | Yes |
| Members, installs, models, self-hosted runtimes | Unlimited | Unlimited | Unlimited | Unlimited |

Marked TBD in the code until Chris sets them: the markups and the hosted machine counts.

**Who it is for.** Free: a developer proving Ada on their own machine (no card). Pro and Team: teams running Ada
across several services or workers, or who want Glyphh to host it. Enterprise: companies that need it in their own
VPC, air-gapped, highly available, with SSO and an SLA.

## Precedent limits

- The bucket is a **total**: every precedent across all of a runtime's Ada models.
- It applies **only on a hosted runtime** (Pro 100,000; Team 1,000,000; Enterprise none). On a local or self-hosted
  runtime the licence carries no limit.
- rrotor enforces it: a `record` that would take the runtime's total past the licence's `mods.ada.precedents` is
  refused (`E_LIMIT_PRECEDENTS`). Runs of different models at the same time each see the others' total as it was when
  they started, so together they can pass the cap by what they record meanwhile; each one's next run is refused.
- rrotor reports its total up the link (`usage.precedents`); the server keeps each runtime's latest, and
  `GET /v1/billing` (and `/v1/me`) gives the org's hosted runtimes' sum against the bucket, `precedents: {used,
  limit}`, which the platform's Usage page shows.

## Licence features

Every licence carries the plan's `features`, signed: `sync`, `ha`, `offline`, `sso`. rrotor shows them in
`/v1/licence` and its health. Only `offline` is acted on today (below); sync, HA and SSO are not built yet.

**Offline licences are Enterprise only.** `POST /v1/runtimes/{id}/offline-licence` answers 403 `E_NOT_IN_PLAN`
(`reason: offline`) on every other plan. Licences by the link and by the daily heartbeat work on every plan, each with
14 days' grace for a self-hosted runtime.

## Hosted machines: what they cost

**Fly's rates** (`iad`, read 2026-10-18 from https://docs.fly.io/about/pricing; a 30-day month):

| Size | Fly preset | Fly $ a month |
|---|---|---|
| small | shared-cpu-1x, 1 GB | 6.70 |
| medium | shared-cpu-2x 2 GB ($13.39) plus 2 GB at $6.00 | 25.39 |
| large | performance-2x 4 GB ($66.00) plus 4 GB at $6.00 | 90.00 |
| Volume | per GB | 0.15 |

- The rates live in the `fly_rates` table, dated (`effective_from`) with their source. A change at Fly is a new row;
  the rate in force is the newest one not in the future. Per second = the 30-day rate ÷ 2,592,000.
- **Metering:** every minute, each hosted machine's month gains its started seconds × its size's rate, and its
  volume's GB × seconds × the volume rate (started or stopped: the disk is kept either way). Cost is kept in
  micro-dollars per machine per month.
- **Billing:** the marked-up amount, cost × (1 + markup), goes to Stripe as meter events on the Billing Meter
  `glyphh_hosting` (one unit, one US cent): once a day and as the billing period ends (ten minutes before the
  subscription renews), per org, only what has not been reported, the fraction of a cent carried; and at once when
  the org goes down to Free. Each report is written before it is sent, its id the event's identifier, so a retry is
  counted once. The markup is the org's own when set (Enterprise's, from its grant), else its plan's; each minute's
  charge uses the markup in force that minute.
- **What the org sees:** `GET /v1/billing` gives `hosting: {month, month_to_date_cents, machines: [{id, name, size,
  cents}]}`, all in, a machine deleted this month included; the connector's `usage` tool says the same.
- **Published rates:** `GET /v1/rates` gives Fly's rates and each self-serve plan's rate (Fly's × (1 + markup), to the
  cent a month and per second), never the markup itself and never an Enterprise rate. The site's `/pricing` and the
  platform read it.
- **Reconciling** (a process, not built): each month, compare what Glyphh metered (`machine_months.cost_micros`)
  with Fly's invoice for the runtimes app (`GLYPHH_FLY_APP`, `glyphh-runtimes`); a gap means a rate row is out of
  date.

## Changing plan

- Free to Pro or Team: `POST /v1/billing/checkout {plan}`, Stripe Checkout (the flat price and the metered hosting
  price on one subscription). Enterprise is never checked out: 422 `E_INVALID`, `reason: not_self_serve`.
- Between Pro and Team: `POST /v1/billing/plan {plan}`; Stripe prorates.
- Down to Free: `POST /v1/billing/plan {"plan": "Free"}`, refused while the org has hosted machines (409
  `E_CONFLICT`, `reason: machines`, "Delete your hosted machines first."); otherwise the hosting due is reported and
  the subscription cancelled at once, invoiced now and prorated.
- An Enterprise org changes its plan with Glyphh, not here: 409 `E_CONFLICT`, `reason: contract`.
- Making a machine past the plan's count (Free has none): 403 `E_LIMIT`, `reason: machines`.
- No plan pauses or limits by hours any more.

## Stripe: once per account

```bash
STRIPE_SECRET_KEY=sk_test_… uv run python scripts/stripe-setup.py
```

Run in the server's repo with the account's secret key (test mode, then live). Idempotent: the products have
Glyphh's own ids (`glyphh_pro`, `glyphh_team`, `glyphh_hosting`), the prices are found by lookup key
(`glyphh_pro_month_9900`, `glyphh_team_month_29900`, `glyphh_hosting_cent`) and the meter by its event name, so a
second run makes nothing. It makes the Pro and Team flat monthly prices (from `db/seed.py`), the Billing Meter
`glyphh_hosting` (summed; the customer from the event's `stripe_customer_id`, the cents from its `value`) and its
metered price (a cent a unit, monthly), and prints the server's settings, `GLYPHH_STRIPE_PRICE_PRO`,
`GLYPHH_STRIPE_PRICE_TEAM`, `GLYPHH_STRIPE_PRICE_HOSTING` and `GLYPHH_STRIPE_METER_HOSTING` (`glyphh_hosting`), with
the `fly secrets set` line for `glyphh-ai-server`. `GLYPHH_STRIPE_WEBHOOK_SECRET` comes from the webhook endpoint
(`{server}/v1/stripe/webhook`). A plan's new amount in the seed is a new price under a new lookup key.

## Enterprise: setting up a customer

Each Enterprise customer is on their own Stripe subscription, made by hand, and their deal is recorded on their org.

1. **They sign up** on the platform (`https://platform.glyphh.ai`), which makes their org. Get its id (Settings →
   General, or `GET /v1/org`).
2. **In Stripe:** the customer (or the one the platform made if they ever checked out; a Pro or Team subscription
   they have is cancelled first, or the grant is refused, `E_CONFLICT` `subscribed`); a price for the contract
   (their product, the agreed amount, **yearly**); a subscription for the customer with two items, the contract
   price and the shared metered hosting price (`GLYPHH_STRIPE_PRICE_HOSTING`), collection method **send invoice**
   with the agreed terms. Note its id, `sub_…`.
3. **On the server**, record the deal:

   ```bash
   fly ssh console -a glyphh-ai-server -C "python -m glyphh_server.ops.enterprise grant \
     --org <org uuid> --until <YYYY-MM-DD> --markup <percent> --subscription <sub_...>"
   ```

   The command reads the subscription from Stripe (the server's `GLYPHH_STRIPE_SECRET_KEY`) and records its customer.
   The org is on Enterprise through the end of the `--until` day (UTC); its hosting is metered at `--markup` (a
   percent, 0 or more) and reported to that subscription's customer; its licences carry Enterprise's limits and
   features from their next renewal (within 24 hours, or at once on a runtime's next link). It prints what it
   recorded, or `Refused: …` and exits non-zero.
4. **Air-gapped:** they register each self-hosted runtime on the platform and issue its offline licence there (up
   to 365 days, 14 days' grace).

**Renewing:** `grant` again with the new `--until` (a new `--markup` or `--subscription` if the deal changed: the new
subscription replaces the old one on the org), and update Stripe to match. **Lapsing:** when the `--until` day has
passed, the server's minute tick puts the org back on Free (hosted machines left are logged for staff). **A new markup
mid-contract:** `grant` with it; it applies from then on. **Ending:** `python -m glyphh_server.ops.enterprise revoke
--org <org uuid>` puts the org back on Free (refused while it has hosted machines: `Refused: Its hosted machines are
deleted first.`); cancel the subscription in Stripe. A deal's subscription that ends in Stripe also puts the org back
on Free. Self-hosted runtimes keep running; offline licences run to their expiry and grace.

## Not built yet

What Pro, Team and Enterprise are sold on but does not exist yet: precedent-store sync across instances (`sync`),
background re-indexing, multi-node HA, SSO/SAML, RBAC, audit logs, an SLA. Only their licence flags ship.

## While the database is reset on every deploy

Until `GLYPHH_RESET_DATABASE` comes out of the server's `fly.toml`, every deploy drops every org: subscriptions in
Stripe outlive it, Glyphh's record of them does not. Take paid customers, and make Enterprise grants, only after the
reset is turned off.
