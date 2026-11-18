# Wind-down: cancelling every subscription

Glyphh's products were retired on 2026-11-18. This is the procedure for ending every paid subscription in Stripe.
**Nothing here was run, and nothing in the repository calls Stripe for it:** there is no script, on purpose. It is a
few minutes in Stripe's Dashboard, or the two commands below, by someone with the account. Refunds are Chris's to
decide and are not part of this.

## What exists in Stripe

Made by `scripts/stripe-setup.py` and by the server (`ops/billing/`):

| Object | What | How to recognise it |
|---|---|---|
| Products | `Glyphh Basic`, `Glyphh Pro`, `Glyphh Team`, and Ada Cloud's metered reads | Product ids `glyphh_basic`, `glyphh_pro`, `glyphh_team`; the reads' product is the one the metered price belongs to |
| Prices | One flat monthly price per plan (Basic $20, Pro $99, Team $299) and one metered price ($1 per 10,000 reads) | Lookup keys `glyphh_<plan>_month_<cents>`; their ids are the app's `GLYPHH_STRIPE_PRICE_BASIC`, `_PRO`, `_TEAM`, `_ADA` |
| Billing meter | `Ada Cloud reads`, event name `ada_requests` | The app's `GLYPHH_STRIPE_METER_ADA` |
| Customers | One per org that ever opened Checkout | `metadata.org_id` |
| Subscriptions | One per paying org: the plan's flat price, and for most the metered reads' price as a second item | `metadata.org_id`; made by Checkout in `subscription` mode |
| Webhook endpoint | `https://api.glyphh.ai/v1/stripe/webhook` | Signed with the app's `GLYPHH_STRIPE_WEBHOOK_SECRET` |
| Customer portal | Stripe's own, where a customer can cancel | No object of ours |

Enterprise was by contract: its subscriptions or invoices, if any, were made by hand in the Dashboard and carry no
price of the four above. Look for them by customer.

**The Stripe account is shared with the games.** Free Fall Frank and Bams & Brags charge through it with their own
copies of the key: one-off Checkout payments tagged `metadata.app` (`free-fall-frank`, `bams-and-brags`), and Bams &
Brags pays leagues through Connect (Express accounts, transfers). The games have no subscriptions and no webhook.
So: cancel **subscriptions on Glyphh's four prices only**; never close the account, roll its keys, touch connected
accounts or transfers, or delete the products' payment history.

## Listing them without the secret key in hand

- **Stripe Dashboard** → Billing → Subscriptions, filter Status: Active (then Trialing, Past due, Unpaid, Paused);
  Export gives a CSV. This is the authoritative list.
- **The staff view** (platform → `/admin` → Organisations, filter by plan; Dashboard → paying orgs and the plan mix),
  from the server's database alone: `orgs.billing_status`, `stripe_subscription_id`. It shows what the webhook last
  recorded, so compare it with the Dashboard.
- `scripts/wind-down/row-counts.sql` prints orgs by billing status.

There is no route that lists subscriptions from Stripe, and none should be added for this.

## The server must be listening

`POST /v1/stripe/webhook` stays open while wound down (it is one of the few routes that does), and each
`customer.subscription.deleted` it hears puts the org on Free, clears its subscription id, sets `billing_status`
`canceled` and revokes its licence keys. So cancel while `glyphh-ai-server` is up, and do not delete the webhook
endpoint in Stripe or the `GLYPHH_STRIPE_*` secrets until the last final invoice is paid or written off. Keep the
endpoint subscribed to `customer.subscription.*`, `invoice.payment_succeeded` and `checkout.session.completed`.

## Two ways to cancel

| | A. Now | B. At the period's end |
|---|---|---|
| What Stripe does | Ends the subscription at once | Marks it to end when the paid month is over; no renewal |
| Money | Nothing more is charged for the plan. Stripe's default is **no refund and no credit** for the unused days; metered reads already reported are on a final invoice only if you ask for one | The customer keeps what they paid for; reads past the month already reported are on the last invoice as usual |
| The service | Off already (the switch), so the customer has paid for days they cannot use | Off already too: the same |
| Record | `customer.subscription.deleted` now: the org is `canceled` today | `customer.subscription.updated` now (`renews_at` cleared), `deleted` at the period's end, up to a month away: the webhook and its secrets must stay until then |
| What the customer sees | Stripe's cancellation email if it is on (Settings → Billing → Customer emails) | The same, with the end date |

**Recommended: A, cancel now, and refund the unused part of the month by hand.** The products are already off, so B
has people's subscriptions "active" for weeks on a service that answers 410, and keeps the wind-down open for a
month. With A everything is closed today; the refund is the fair half of it. Stripe can work the unused time out
itself if a subscription is cancelled with proration and its credit refunded, but **what to refund is a decision,
not a default**: nothing here invents an amount. Decide per customer in the Dashboard (Payments → the last invoice
→ Refund), or tell them none is due. A refund is never automatic on cancel.

In either case, do not use "Invoice now" for unbilled metered reads unless Chris wants the last overage charged: the
server stops reporting reads when it is wound down, so the last minutes before the switch are not billed either way.

## Doing it

**In the Dashboard** (a handful of subscriptions): Billing → Subscriptions → each → Cancel subscription → choose
"Immediately" (A) or "At end of period" (B), "No refund" (decide refunds separately, above).

**With Stripe's CLI**, signed in to the account (`stripe login`; live mode asks to confirm), one subscription at a
time, after reading the list:

    stripe subscriptions list --status active --limit 100            # read first; repeat for trialing, past_due
    stripe subscriptions cancel <sub_id>                              # A: now, no proration, no final invoice
    stripe subscriptions update <sub_id> --cancel-at-period-end=true  # B: at the period's end

Check each id against the four prices before cancelling it. There is deliberately no loop here.

## What customers are told

Before cancelling, one email from support@glyphh.ai to each paying customer (the Dashboard's export has the
addresses): that Glyphh's products were retired on 18 November 2026, that their subscription is cancelled and when,
that they will not be charged again, what happens to the unused part of the month (the decision above), that their
data is deleted and by when, and that questions go to support@glyphh.ai. The words are Chris's to approve; nothing
sends it.

## After

1. Subscriptions → Active, Trialing, Past due: none on Glyphh's prices.
2. The staff view → Organisations: no org with a paid plan and `active`.
3. Archive the four prices and the products (Product catalogue → Archive), so nothing can be bought; archived, their
   history stays. Deactivate the meter. Leave the customers.
4. Only when the last invoice is settled: delete the webhook endpoint in Stripe and the server's `GLYPHH_STRIPE_*`
   secrets. **Not the account's key itself**: the games use the same account.
