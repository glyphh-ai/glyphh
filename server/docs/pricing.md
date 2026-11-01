# Pricing and licensing

How Glyphh charges and how a licence is enforced. Free to adopt without friction on a developer's own machines; the
paid plans are enforced by rrotor itself, offline, so Glyphh never takes on a customer's infrastructure or compute:
rrotor runs on the customer's machines and the server only grants its licence. Where today's code differs from this
is [Against what is built](#against-what-is-built).

## The plans

| | Free | Basic | Pro | Team | Enterprise |
|---|---|---|---|---|---|
| Price | $0 | $20 a month | $99 a month | $299 a month | By contract, from $10k a year |
| Runtime nodes | 1 | 1 (no key: as Free) | 3 | 10 | Unlimited |
| Precedents per node, across all its models | 5,000 | 5,000 (as Free) | 50,000 | 500,000 (TBD) | Unlimited |
| Multi-node sync | No | No | Yes | Yes | Yes, with high availability |
| Air-gapped | No | No | Optional | Optional | Yes |
| Audit log | No | No | No | No | Yes |
| Ada Cloud precedents, the org's | 1,000 | 10,000 | 100,000 | 1,000,000 | By contract |
| Ada Cloud reads a month | 5,000, then refused | 50,000, then $1 per 10,000 | 1,000,000, then $1 per 10,000 | 5,000,000, then $1 per 10,000 | By contract |
| Ada Cloud calls a second | 5 | 10 | 50 | 200 | By contract |

- **Basic is an Ada Cloud plan,** between Free and Pro: self-serve, its Stripe price `GLYPHH_STRIPE_PRICE_BASIC`. It
  has no licence key (rrotor's tiers are free, pro, team and enterprise), so a node on Basic runs as Free. Ada
  Cloud's caps are in [specs/ada-cloud.md](specs/ada-cloud.md#7-plans-and-metering).
- **Free's Ada Cloud caps** are 1,000 precedents and 5,000 reads a month, 5 calls a second, refused at its caps. An
  org already holding more keeps every precedent, and only new ones are refused (`E_LIMIT` `precedents`) until it is
  under the cap or upgrades.
- **Free is the default.** rrotor with no key runs as Free (Community mode): one node, 5,000 precedents, no sync.
- **A key unlocks the rest, locally,** verified on the node with no call to Glyphh.
- **A runtime node** is every rrotor node the server hears from for the org, local or self-hosted.
- **Never per seat, per model or per install.**
- **Glyphh runs no runtime.** No relay, and no Glyphh DNS for customer runtimes: a self-hosted runtime is at its own
  address (`RROTOR_PUBLIC_HOST`), a local one on the person's machine.

## The key

- **Ed25519.** The public key is embedded in rrotor and the SDKs; the private key is only on the control plane
  (api.glyphh.ai) or a secure build pipeline.
- **Format:** `<BASE64URL_PAYLOAD>.<BASE64URL_SIGNATURE>`, the payload
  `{license_id, tier, max_nodes, max_precedents, cluster_sync_enabled, issued_at, expires_at, customer_id}`.
- **It expires at the end of the paid month.** A fresh key is issued on every `invoice.payment_succeeded` and rrotor
  picks it up at its link's `welcome` or its heartbeat. An Enterprise air-gapped key runs the contract's term and is
  delivered out of band.
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

With sync on, one node is elected **head**: it holds the cluster's aggregate state and runs the cluster's log drain;
the rest follow it. When the head is lost another is elected (high availability, Enterprise). Free is a single node,
with no head.

## Telemetry, audit and log drains

- **The data stays on the rrotor:** its logs, metrics, traces and audit events never go to Glyphh.
- **Log drains.** Each rrotor (in a cluster, the head) streams OpenTelemetry (logs, metrics, traces, audit events) to
  the customer's own collector, never through Glyphh.

## The control plane

- **Issuing:** on Stripe's `invoice.payment_succeeded` or `checkout.session.completed`, the server builds the payload
  from the subscription's plan, signs it, keeps it in a `licenses` table and delivers the key on the dashboard, in
  every runtime's link `welcome` and at the next heartbeat.
- **Revoking:** on `customer.subscription.deleted` the licence is marked revoked; no fresh key follows, so the node
  drops to Free when its key's month and grace end.
- **Stripe, once per account:** `STRIPE_SECRET_KEY=sk_… uv run python scripts/stripe-setup.py` (idempotent, prices
  found by lookup key) makes the flat prices and Ada Cloud's metered reads' price and meter, and prints their settings
  with a `fly secrets set` line.
- **Enterprise** is by contract: an annual invoice on its own Stripe subscription, recorded on the org on the server's
  machine (`fly ssh console -a glyphh-ai-server`) with
  `python -m glyphh_server.ops.enterprise grant --org <uuid> --until <YYYY-MM-DD> --subscription <sub_…>` and ended
  with `revoke --org <uuid>`. Grants survive deploys: production keeps its data
  ([architecture.md](architecture.md#starting-up-and-migrations)).

## Against what is built

Facts only.

| The strategy | Today |
|---|---|
| Runtime nodes: every rrotor node, local or self-hosted | `max_machines` (`limits.machines`: Free 1, Pro 3, Team 10, Enterprise unlimited) is signed into the key as `max_nodes` and enforced by rrotor. The server counts every node, softly: each node's heartbeat or `hello` (`node_id`, `cluster_id`, `role`) is kept in `nodes`, and `GET /v1/license/nodes` and the connector's `usage` show "4 of 3, over", never refusing; a runtime that says no node is one while it is seen |
| Precedents per node: 5,000, 50,000, 500,000, unlimited | `db/seed.py` seeds 5,000, 50,000, 500,000 (TBD) and unlimited, signed into the key as `max_precedents`; the old licence says unlimited. The usage shown is the fullest runtime's, as it last said |
| One key string, `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key` | The server signs it and sends it as `license_key` in every runtime's `welcome` and in the heartbeat's answer, beside the old licence, and shows it at `GET /v1/license/keys` and, masked, in the connector's `plan` and `usage`. Where rrotor reads it is rrotor's. On the server the signing key is `GLYPHH_LICENSE_SIGNING_KEY` (`GLYPHH_LICENSE_KEY`, its old name, still read) |
| `<payload>.<signature>`, both base64url | As specified: base64url without padding, Ed25519 over the payload's exact bytes (`ops/license_keys.py`). The old licence, JSON `{payload, signature}` over canonical JSON, is still sent beside it, and the Enterprise offline token is still that licence |
| Payload `license_id`, `tier`, `max_nodes`, `max_precedents`, `cluster_sync_enabled`, `issued_at`, `expires_at`, `customer_id` | Exactly these, in this order, times RFC 3339 UTC; `customer_id` is the org's id. The old licence keeps `licence_id`, `plan`, `limits`, `mods`, `features`, `runtime_id`, `kind`, `grace_days` |
| A key per paid month, issued on `invoice.payment_succeeded`, kept in `licenses`, emailed | Issued on `checkout.session.completed` and `invoice.payment_succeeded` for the org's own active subscription, expiring at its period's end, kept in `licenses` (the same terms to the same end are the same key); an Enterprise grant issues one through its `--until`; Free and Basic get none. Not emailed: no key is in Stripe's receipt yet; the platform shows it |
| `customer.subscription.deleted` revokes the licence | Every key of the org's is revoked (no longer delivered) and the org is on Free; so is an Enterprise grant's on revoke or lapse. A node keeps its key to `expires_at` and rrotor's grace |
| A bad signature: Free mode, logged | rrotor's own behaviour; not set by the server |
| A `limit_exceeded` result, `indexed: false` | rrotor refuses a `record` past the cap with `E_LIMIT_PRECEDENTS` |
| Sync, HA, the head node | Not built: `sync` and `ha` are licence flags and `cluster_sync_enabled` a key field; no cluster transport or head election. The server keeps each node's `role` and `cluster_id` as said |
| Air-gapped optional on Pro and Team | Offline licences are Enterprise only (`POST /v1/runtimes/{id}/offline-licence`, else 403 `E_NOT_IN_PLAN` `offline`); a Pro or Team operator can copy the key from `GET /v1/license/keys` into `/etc/rrotor/license.key` each month |
| Audit log, log drains | Both rrotor's; the server receives no runtime's logs. No SSO/SAML or RBAC. `sub` (the person's user id) is in `/v1/runtime/introspect`'s answer for rrotor's audit |
| Heartbeat to `/v1/telemetry/heartbeat`: `license_id`, hashed GUID, version, store size; fail-open | `POST /v1/license/verify` with the runtime's token: `{machine, licence_id, version, active_runs}` and, optional, `{node_id, cluster_id, role, precedents}`, answered with the licence and `license_key`; self-hosted runtimes only. A local runtime takes its key in its link's `welcome` |
| Expired key: Free limits after 14 days' grace | A self-hosted runtime's old licence is live until `expires_at` plus 14 days; past that rrotor refuses only what needs a licensed mod. The server stops delivering a key past its `expires_at` |
