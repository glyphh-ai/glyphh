# Pricing and licensing

How Glyphh charges and how a licence is enforced (Chris, 2026-10-19). Free to adopt without friction on a developer's
own machines; the paid plans are enforced by rrotor itself, offline, so Glyphh never takes on a customer's
infrastructure or compute. This is the strategy; where today's code differs is
[Against what is built](#against-what-is-built).

## The plans

| | Free | Pro | Team | Enterprise |
|---|---|---|---|---|
| Price | $0 | $99 a month | $299 a month | By contract, from $10k a year |
| Runtime nodes | 1 | 3 | 10 | Unlimited |
| Precedents per node, across all its models | 5,000 | 50,000 | 500,000 (TBD) | Unlimited |
| Multi-node sync | No | Yes | Yes | Yes, with high availability |
| Air-gapped | No | Optional | Optional | Yes |
| Audit log | No | No | No | Yes |

- **Free is the default.** rrotor with no key runs as Free (Community mode): one node, 5,000 precedents, no sync.
- **A key unlocks the rest, locally,** verified on the node with no call to Glyphh.
- **A runtime node** is every runtime the server sees linked for the org, hosted or self-hosted.
- **Never per seat, per model or per install.**
- **Glyphh-run hosting is off** ([Managed cloud](#managed-cloud-off)). No relay, and no Glyphh DNS for customer
  runtimes: a self-hosted runtime is at its own address (`RROTOR_PUBLIC_HOST`).

## The key

- **Ed25519.** The public key is embedded in rrotor and the SDKs; the private key is only on the control plane
  (api.glyphh.ai) or a secure build pipeline.
- **Format:** `<BASE64URL_PAYLOAD>.<BASE64URL_SIGNATURE>`, the payload
  `{license_id, tier, max_nodes, max_precedents, cluster_sync_enabled, issued_at, expires_at, customer_id}`.
- **It expires at the end of the paid month.** A fresh key is issued on every `invoice.payment_succeeded` and rrotor
  picks it up at its heartbeat. An Enterprise air-gapped key runs the contract's term and is delivered out of band.
- **Where rrotor reads it:** `GLYPHH_LICENSE_KEY`, else `/etc/rrotor/license.key`; `RROTOR_LICENCE` and
  `/data/licence.token` are accepted as aliases.

## rrotor at start

1. **No key:** Free (`max_nodes` 1, `max_precedents` 5,000, sync off).
2. **A bad signature:** logged loudly, and the node starts in Free (Community) mode. Never fatal.
3. **Valid but expired:** `[Glyphh Warning]: License key expired. Falling back to Community Tier limits.`, with 14
   days' grace before the limits drop.
4. **Valid:** its limits apply.

## Enforcement in rrotor

- **(A) The precedent guard,** on `record()` and `live.learn()`: at `store.count >= max_precedents` it never crashes
  and does not index; it returns `{"status": "limit_exceeded", "message": "Precedent store capacity limit reached
  (5,000 max for Community Tier). Upgrade key to index further precedents.", "indexed": false}`.
- **(B) The cluster sync lock:** with sync off the cluster transport never starts, and rrotor logs
  `[Glyphh Node]: Cluster synchronization disabled under Community License.`
- **(C) The heartbeat:** non-blocking, every 24 hours, to `{api}/v1/telemetry/heartbeat` with the `license_id`, a
  hashed system GUID, the binary's version and the store's total size; it answers with the newest key. It fails open:
  no answer changes nothing.

## Clusters: the head node

With sync on, one node is elected **head**: it holds the cluster's aggregate state, runs the cluster's log drain, and
is where Programs and the gateway will be scheduled from. The rest follow it. When the head is lost another is elected
(high availability, Enterprise). Free is a single node, with no head.

## Telemetry, audit and log drains

- **By default the data stays on the rrotor** (isolated): its logs, metrics, traces and audit events never leave it.
- **Recommended: log drains.** Each rrotor (in a cluster, the head) streams OpenTelemetry (logs, metrics, traces,
  audit events) to the customer's own collector, never through Glyphh.
- **Opt-in server-side logging:** a flag that sends them to Glyphh so the platform can show them. Turning it on says
  plainly that the data then leaves the rrotor.

## The control plane

- **Issuing:** on Stripe's `invoice.payment_succeeded` or `checkout.session.completed`, the server builds the payload
  from the subscription's plan, signs it, keeps it in a `licenses` table and delivers the key on the dashboard, in
  Stripe's receipt email and at the next heartbeat.
- **Revoking:** on `customer.subscription.deleted` the licence is marked revoked; no fresh key follows, so the node
  drops to Free when its key's month and grace end.
- **Stripe, once per account:** `STRIPE_SECRET_KEY=sk_… uv run python scripts/stripe-setup.py` (idempotent, prices
  found by lookup key) makes the flat prices and prints their settings with a `fly secrets set` line. Its hosting meter
  and metered price are wanted only with hosting on.
- **Enterprise** is by contract: an annual invoice on its own Stripe subscription, recorded on the org on the server's
  machine (`fly ssh console -a glyphh-ai-server`) with
  `python -m glyphh_server.ops.enterprise grant --org <uuid> --until <YYYY-MM-DD> --subscription <sub_…>` and ended
  with `revoke --org <uuid>`. While the database is reset on every deploy
  ([architecture.md](architecture.md#starting-up-and-the-reset-on-deploy)), grants do not survive a deploy.

## Managed cloud (off)

Glyphh running rrotor on Fly for a customer (compute plus a margin) is built and switched off: `GLYPHH_HOSTING`, off
by default. Off, no hosted machine is made, started or restarted, `GET /v1/rates` is `E_UNAVAILABLE` `hosting_off` and
Checkout sells no hosting. Its design, metering and meter are in [architecture.md](architecture.md#billing-and-hosting).

## Against what is built

Facts only; none of this is changed yet.

| The strategy | Today |
|---|---|
| Runtime nodes: every linked runtime, hosted or self-hosted | `max_machines` (`limits.machines`: Free 1, Pro 3, Team 10, Enterprise unlimited) is enforced only on hosted machines; self-hosted and local runtimes are not counted |
| Precedents per node: 5,000, 50,000, 500,000, unlimited | `db/seed.py` seeds managed precedents 0, 100,000, 1,000,000, unlimited, applied only on a hosted runtime; local and self-hosted runtimes are unlimited on every plan |
| One key string, `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key` | Licences reach rrotor in the link's `welcome` (24 hours), from the self-hosted heartbeat (24 hours), or as an offline token in `RROTOR_LICENCE` or `/data/licence.token` (Enterprise only, up to 365 days). On the server, `GLYPHH_LICENSE_KEY` is the Ed25519 private key that signs licences |
| `<payload>.<signature>`, both base64url | JSON `{payload, signature}`, the signature base64 over the payload's canonical JSON; the offline token is base64url of that JSON |
| Payload `license_id`, `tier`, `max_nodes`, `max_precedents`, `cluster_sync_enabled`, `issued_at`, `expires_at`, `customer_id` | `licence_id`, `plan`, `limits.machines`, `mods.ada.limits.precedents`, `features` (`sync`, `ha`, `offline`, `sso`), `expires_at`, `org_id`, `user_id`, `install_id`, `runtime_id`, `kind`, `grace_days` |
| A key per paid month, issued on `invoice.payment_succeeded`, kept in `licenses`, emailed | No `licenses` table and no key issued or emailed; licences last 24 hours and are re-signed on each link and heartbeat. The webhook (`checkout.session.completed`, `customer.subscription.*`, `charge.refunded`) keeps the org's plan version and billing status |
| `customer.subscription.deleted` revokes the licence | It puts the org on Free; the next licence carries Free |
| A bad signature: Free mode, logged | rrotor's own behaviour; not set by the server |
| A `limit_exceeded` result, `indexed: false` | rrotor refuses a `record` past the cap with `E_LIMIT_PRECEDENTS` |
| Sync, HA, the head node | Not built: `sync` and `ha` are licence flags only; no cluster transport or head election |
| Air-gapped optional on Pro and Team | Offline licences are Enterprise only (`POST /v1/runtimes/{id}/offline-licence`, else 403 `E_NOT_IN_PLAN` `offline`) |
| Audit log, log drains, opt-in server-side logging | Not built; no audit logs, SSO/SAML or RBAC either |
| Heartbeat to `/v1/telemetry/heartbeat`: `license_id`, hashed GUID, version, store size; fail-open | `POST /v1/license/verify` with the runtime's token: `{machine, licence_id, version, active_runs}`, answered with a fresh licence; self-hosted runtimes only |
| Expired key: Free limits after 14 days' grace | A self-hosted runtime's licence is live until `expires_at` plus 14 days; past that rrotor refuses only what needs a licensed mod |
