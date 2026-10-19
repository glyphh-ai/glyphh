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
by default. On, it is Pro's and Team's (and Enterprise's): Free is refused, `E_NOT_IN_PLAN` `hosting`, its one node
being self-hosted. Off, no hosted machine is made, started or restarted, `GET /v1/rates` is `E_UNAVAILABLE` `hosting_off` and
Checkout sells no hosting. Its design, metering and meter are in [architecture.md](architecture.md#billing-and-hosting).

## Against what is built

Facts only.

| The strategy | Today |
|---|---|
| Runtime nodes: every linked runtime, hosted or self-hosted | `max_machines` (`limits.machines`: Free 1, Pro 3, Team 10, Enterprise unlimited) is refused only on hosted machines. Every hosted and self-hosted runtime node is counted, softly: each node's heartbeat or `hello` (`node_id`, `cluster_id`, `role`) is kept in `nodes`, and `GET /v1/license/nodes` and the connector's `usage` show "4 of 3, over", never refusing; a runtime that says no node is one; local runtimes are not counted |
| Precedents per node: 5,000, 50,000, 500,000, unlimited | `db/seed.py` seeds 5,000, 50,000, 500,000 (TBD) and unlimited, signed into the key as `max_precedents`; a hosted runtime's old licence carries the same as its cap, a self-hosted one's says unlimited. The usage shown is the fullest hosted or self-hosted runtime's |
| One key string, `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key` | The server signs it and sends it as `license_key` in every runtime's `welcome` and in the heartbeat's answer, beside the old licence (rrotor's release N), and shows it at `GET /v1/license/keys` and, masked, in the connector's `plan` and `usage`. Where rrotor reads it is rrotor's. On the server the signing key is `GLYPHH_LICENSE_SIGNING_KEY` (`GLYPHH_LICENSE_KEY`, its old name, still read) |
| `<payload>.<signature>`, both base64url | As specified: base64url without padding, Ed25519 over the payload's exact bytes (`ops/license_keys.py`). The old licence, JSON `{payload, signature}` over canonical JSON, is still sent beside it, and the Enterprise offline token is still that licence |
| Payload `license_id`, `tier`, `max_nodes`, `max_precedents`, `cluster_sync_enabled`, `issued_at`, `expires_at`, `customer_id` | Exactly these, in this order, times RFC 3339 UTC; `customer_id` is the org's id. The old licence keeps `licence_id`, `plan`, `limits`, `mods`, `features`, `runtime_id`, `kind`, `grace_days` |
| A key per paid month, issued on `invoice.payment_succeeded`, kept in `licenses`, emailed | Issued on `checkout.session.completed` and `invoice.payment_succeeded` for the org's own active subscription, expiring at its period's end, kept in `licenses` (the same terms to the same end are the same key); an Enterprise grant issues one through its `--until`; Free gets none. Not emailed: no key is in Stripe's receipt yet; the platform shows it |
| `customer.subscription.deleted` revokes the licence | Every key of the org's is revoked (no longer delivered) and the org is on Free; so is an Enterprise grant's on revoke or lapse. A node keeps its key to `expires_at` and rrotor's grace |
| A bad signature: Free mode, logged | rrotor's own behaviour; not set by the server |
| A `limit_exceeded` result, `indexed: false` | rrotor refuses a `record` past the cap with `E_LIMIT_PRECEDENTS` |
| Sync, HA, the head node | Not built: `sync` and `ha` are licence flags and `cluster_sync_enabled` a key field; no cluster transport or head election. The server keeps each node's `role` and `cluster_id` as said |
| Air-gapped optional on Pro and Team | Offline licences are Enterprise only (`POST /v1/runtimes/{id}/offline-licence`, else 403 `E_NOT_IN_PLAN` `offline`); a Pro or Team operator can copy the key from `GET /v1/license/keys` into `/etc/rrotor/license.key` each month |
| Audit log, log drains, opt-in server-side logging | Not built; no audit logs, SSO/SAML or RBAC either. `sub` (the person's user id) is in `/v1/runtime/introspect`'s answer for rrotor's audit |
| Heartbeat to `/v1/telemetry/heartbeat`: `license_id`, hashed GUID, version, store size; fail-open | `POST /v1/license/verify` with the runtime's token: `{machine, licence_id, version, active_runs}` and, optional, `{node_id, cluster_id, role, precedents}`, answered with the licence and `license_key`; self-hosted runtimes only |
| Expired key: Free limits after 14 days' grace | A self-hosted runtime's old licence is live until `expires_at` plus 14 days; past that rrotor refuses only what needs a licensed mod. The server stops delivering a key past its `expires_at` |
