# Glyphh-hosted models: tokens and the overage balance

**Status:** built in the server behind `GLYPHH_LLM` (off by default), not deployed on; prices and allowances are TBD
placeholders for Chris to set. The platform's side is glyphh-ai/platform#51.

**Supersedes** section 4 of `docs/specs/memory.md` ("no new plan") for the hosted model: the hosted model is billed by
tokens, as below. (memory.md is not yet in this repository; this pointer lives here until it is.)

## Rulings (Chris, 2026-11-10)

1. **Like Anthropic.** A plan includes a monthly token allowance; hosted models draw it down first.
2. **Dollars, never credits.** Past the allowance, input and output tokens are charged in dollars per million tokens
   against a prepaid overage balance the org tops up in dollars. The price on the page and the charge on the bill are
   the same number.
3. **Allowances** (TBD): Free 250,000 tokens a month, Basic 5,000,000, Pro 25,000,000, Team 100,000,000, Enterprise by
   contract. Calendar month, UTC, as Ada Cloud's reads. Free may buy a balance.
4. **First model** `adal-34b-1-0` ("adaL 34B 1.0"), ids `adal-<size>-<major>-<minor>[-beta]`; rates (TBD) $0.60 per
   million input tokens, $2.40 per million output, context 32,768, allowance weight 1.0.
5. **Top-ups** $10 to $1,000 through Stripe Checkout (one payment), presets $10, $25, $50, $100; credited only when
   Stripe says the session is paid. Staff may grant a balance.
6. **A request may take the balance a little below 0** (charged after its reply); one is let in only while the
   allowance has tokens left or the balance is above 0.

## What is built

- **Models:** `src/glyphh_server/llm/models.json` (checked at start, `llm/registry.py`): `id, name, status
  (beta|stable|deprecated), context_tokens, input_cents_per_mtok, output_cents_per_mtok, allowance_weight, released,
  summary`.
- **Plans:** `plan_versions.llm_tokens` (null = by contract), seeded in `db/seed.py` and carried by `_carry` as the
  cloud limits are (a change of the allowance alone is a new version taking the price and the orgs).
- **Money** is in microdollars (1 = $0.000001), so no request's charge rounds to nothing. `llm_ledger` (kind
  `topup|charge|grant|refund`, `amount_micros` signed, `stripe_ref`, `model`, `period`, `note`) is every movement;
  `llm_balances` (one row an org) holds the sum and the month's allowance used, updated in the same transaction.
  Every table has the tenant policy (row-level security), proved as `glyphh_app`.
- **Accounting** (`llm/meter.py`), after each reply, on the org's balance row locked: weighed tokens = (input + output)
  x weight drawn from the allowance; the share past it charged at the model's rates, `ceil` to the microdollar (a
  request crossing the allowance's edge is split); the model's day in `llm_usage_days`.
- **Inference** at the Ada hosts (`api/inference.py`, `llm/proxy.py`): `POST /v1/chat/completions` (OpenAI's body,
  `model` a registry id) proxied to `GLYPHH_INFERENCE_URL` (vLLM, serving each model under its registry id with
  `--served-model-name`; `GLYPHH_INFERENCE_KEY` sent as a bearer when set; `GLYPHH_INFERENCE_TIMEOUT`, 300 s).
  `stream: true` is passed on as server-sent events with `stream_options.include_usage` forced on and charged from
  the last chunk. Auth is the Ada API's: API keys or a sign-in. Limited to the plan's calls a second (its own bucket,
  `llm:rate:<org>`).
- **Refusals:** past the allowance with the balance at or below 0, **402 `E_BALANCE`** `{reason: "tokens", used, max,
  balance_cents, topup}` (`topup` the platform's `/settings/billing`); the server's 4xx, 400 `E_INVALID` with its
  message; the server down or failing, 503 `E_UNAVAILABLE` `reason: inference` (`inference_off` with no URL set); an
  unknown model, 404 `E_MODEL_MISSING`. None of these is charged.
- **Connector:** `usage` and `plan` say the tokens and the balance, `plans` the allowances and rates, and `topup`
  (admin) answers the Checkout link, while hosted models are on.
- **Staff:** `POST /v1/admin/orgs/{id}/llm-grant {amount_cents 1..100000, note}` adds a `grant`, audited;
  `GET /v1/admin/orgs/{id}` shows `balance`.

## The API (what the platform reads)

- `GET /v1/me` gains `llm: bool` (hosted models on: show their pages).
- `GET /v1/billing` gains `tokens`, `balance` and `bots`, whether hosted models are on or not (the bots' Claude
  tokens are on the same meter; the connector's usage only while on):
  `tokens: {month, resets_at, used, max|null, over_used, models: [{id, name, kind (hosted|bot), input_tokens,
  output_tokens, requests, charged_cents, charged_micros}]}`, `balance: {cents, micros, low}` (`low`: under $5, TBD),
  `bots: [{slug, name, runs, input_tokens, output_tokens, charged_cents, charged_micros}]` (this month's, the
  costliest first).
- `GET /v1/llm/usage?days=30` (1..90) -> `{days: [{day, model, input_tokens, output_tokens, requests, charged_cents,
  charged_micros}]}`, oldest first.
- `GET /v1/billing/ledger?limit=50` (1..200) -> `{entries: [{at, kind, amount_cents, amount_micros, model|null,
  note|null}]}`, newest first, charges negative; a charge's note is its day, a top-up's its Checkout session.
- `GET /v1/plans` stays a list; each plan gains `llm_tokens` (null = by contract).
- `GET /v1/llm/models` -> `{models: [{id, name, status, context_tokens, input_cents_per_mtok, output_cents_per_mtok,
  allowance_weight, released, summary}]}`, on the account API (no sign-in needed, as `/v1/plans`) and the Ada hosts.
- `POST /v1/billing/topup {amount_cents}` (admin, 1000..100000) -> `{url}`; Stripe returns to the platform's
  `/settings/billing?topup=1` (cancel: `/settings/billing`). Open while hosted models are off too: the bots draw on
  the balance.
- Stripe's webhook credits `checkout.session.completed` or `checkout.session.async_payment_succeeded` with
  `mode=payment`, `payment_status=paid`, `currency=usd` and `metadata.kind=llm_topup`, once per session id.

## Where it differs from the contract

- **No Redis counter for the allowance.** The month's tokens live on `llm_balances` beside the money and are written
  in the request's accounting transaction, so allowance and charge can never disagree; a hosted request takes
  seconds, so one locked row update each is cheap. Redis keeps only the rate bucket.
- **One charge entry a model a UTC day,** each request's charge added to it, so the ledger stays readable; the
  per-request detail is in `llm_usage_days`.
- **`/v1/plans` stays a list** (a top-level object would break every client); the rates are `GET /v1/llm/models`.
- **Served at the Ada hosts,** so `GLYPHH_LLM` takes effect only with `GLYPHH_ADA_CLOUD` on too.
- **A stream cut off before its usage chunk** is charged from an estimate (messages' characters / 4 in, content's
  characters / 4 out); an answer without `usage` likewise.
- **Stripe success goes straight to the platform** (`/settings/billing?topup=1`), not through a server redirect.
- Money fields carry `*_micros` beside `*_cents` everywhere (cents are fractional).

## Not built

- Refunds of a top-up (`charge.refunded`) are not handled yet: the `refund` kind exists for them.
- Per-API-key split of usage.
