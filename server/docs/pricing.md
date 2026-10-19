# Pricing and licensing

How Glyphh charges and how a licence is enforced (Chris, 2026-10-19). Free to adopt without friction on a developer's
own machines; the paid tiers are enforced by rrotor itself, offline, so Glyphh never takes on a customer's
infrastructure or compute. This is the strategy; where today's code differs is
[Against what is built](#against-what-is-built).

## The tiers

| | Community (Free) | Pro Team | Enterprise BYOC |
|---|---|---|---|
| Price | $0 | $199 a month | $12,000 a year |
| Runtime nodes | 1 (standalone) | Up to 3 active | Unlimited cluster nodes |
| Precedents per store | 5,000 | 50,000 | Unlimited |
| Multi-node sync | Off | On (gRPC cluster sync) | On, with high availability |
| Air-gapped | No | Optional | Supported |
| Verification | None: the default | Ed25519 signature | Ed25519 and a custom audit log |

- **Community is the default.** rrotor with no key runs as Community: one node, 5,000 precedents, sync off.
- **A key unlocks the rest, locally.** A signed key string (`GLYPHH_LICENSE_KEY`) raises the limits and turns on
  multi-node sync, verified on the node with no call to Glyphh.
- **Never per seat, per model or per install.**
- **Glyphh-run hosting is off** ([Managed cloud](#managed-cloud-off)). No relay, and no Glyphh DNS for customer
  runtimes: a self-hosted runtime is at its own address (`RROTOR_PUBLIC_HOST`).

## The key

- **Ed25519.** The public key is embedded in rrotor and the SDKs; the private key is only on the control plane
  (api.glyphh.ai) or a secure build pipeline.
- **Format:** `<BASE64URL_PAYLOAD>.<BASE64URL_SIGNATURE>`, the payload:

  ```json
  {
    "license_id": "…",
    "tier": "pro_team",
    "max_nodes": 3,
    "max_precedents": 50000,
    "cluster_sync_enabled": true,
    "issued_at": "…",
    "expires_at": "…",
    "customer_id": "…"
  }
  ```

## rrotor at start

1. Read `GLYPHH_LICENSE_KEY`, else `/etc/rrotor/license.key`.
2. **None:** Community (`max_nodes` 1, `max_precedents` 5,000, sync off).
3. **Present:** verified locally.
   - A bad signature stops the start: `FATAL: Invalid Glyphh License Key signature`.
   - Valid but expired: `[Glyphh Warning]: License key expired. Falling back to Community Tier limits.`, with 14 days'
     grace before the limits drop.
   - Valid: its limits apply.

## Enforcement in rrotor

- **(A) The precedent guard,** on `record()` and `live.learn()`: at `store.count >= max_precedents` it never crashes
  and does not index; it returns `{"status": "limit_exceeded", "message": "Precedent store capacity limit reached
  (5,000 max for Community Tier). Upgrade key to index further precedents.", "indexed": false}`.
- **(B) The cluster sync lock:** with sync off the cluster transport never starts, and rrotor logs
  `[Glyphh Node]: Cluster synchronization disabled under Community License.`
- **(C) The heartbeat:** non-blocking, every 24 hours, to `{api}/v1/telemetry/heartbeat` with the `license_id`, a
  hashed system GUID, the binary's version and the store's total size. It fails open: no answer changes nothing.

## The control plane

- **Issuing:** on Stripe's `invoice.payment_succeeded` or `checkout.session.completed`, the server builds the payload
  from the subscription's tier, signs it, keeps it in a `licenses` table and delivers the key on the dashboard and in
  Stripe's receipt email.
- **Revoking:** on `customer.subscription.deleted` the licence is marked revoked; a node learns it at its optional
  heartbeat.
- **Stripe, once per account:** `STRIPE_SECRET_KEY=sk_… uv run python scripts/stripe-setup.py` (idempotent, prices
  found by lookup key) makes the flat prices and prints their settings with a `fly secrets set` line. Its hosting meter
  and metered price are wanted only with hosting on.
- **Enterprise** is by contract: an annual invoice on its own Stripe subscription, recorded on the org on the server's
  machine (`fly ssh console -a glyphh-ai-server`) with
  `python -m glyphh_server.ops.enterprise grant --org <uuid> --until <YYYY-MM-DD> --subscription <sub_…>` and ended
  with `revoke --org <uuid>`; an air-gapped runtime's offline licence is issued on the platform. While the database is
  reset on every deploy ([architecture.md](architecture.md#starting-up-and-the-reset-on-deploy)), grants do not
  survive a deploy.

## Managed cloud (off)

Glyphh running rrotor on Fly for a customer (compute plus a margin) is built and switched off: `GLYPHH_HOSTING`, off
by default. Off, no hosted machine is made, started or restarted, every plan shows none, `GET /v1/rates` is
`E_UNAVAILABLE` `hosting_off` and Checkout sells no hosting. Its design, metering and meter are in
[architecture.md](architecture.md#billing-and-hosting).

## Against what is built

Facts only; none of this is changed yet.

| The spec | Today |
|---|---|
| Community $0, Pro Team $199 a month, Enterprise $12,000 a year | `db/seed.py` seeds Free $0, Pro $99 a month, Team $299 a month and Enterprise by contract (`price_cents` null), with hosted machines 0, 3, 10, unlimited and managed precedents 0, 100,000, 1,000,000, unlimited |
| One key string, `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key` | Licences reach rrotor three ways: in the link's `welcome` (24 hours), from the self-hosted heartbeat (24 hours), or as an offline token in `RROTOR_LICENCE` or `/data/licence.token` (Enterprise only, up to 365 days). On the server, `GLYPHH_LICENSE_KEY` is the Ed25519 private key that signs licences |
| `<payload>.<signature>`, both base64url | JSON `{payload, signature}`, the signature base64 over the payload's canonical JSON; the offline token is base64url of that JSON |
| Payload `license_id`, `tier`, `max_nodes`, `max_precedents`, `cluster_sync_enabled`, `issued_at`, `expires_at`, `customer_id` | `licence_id`, `plan`, `limits.machines`, `mods.ada.limits.precedents`, `features` (`sync`, `ha`, `offline`, `sso`), `expires_at`, `org_id`, `user_id`, `install_id`, `runtime_id`, `kind`, `grace_days`; no `issued_at` or `customer_id` |
| Community 5,000 precedents, Pro Team 50,000 | The cap applies only on a hosted runtime (the plan's managed bucket); local and self-hosted runtimes are unlimited on every plan |
| A `limit_exceeded` result, `indexed: false` | rrotor refuses a `record` past the cap with `E_LIMIT_PRECEDENTS` |
| `max_nodes`; gRPC cluster sync and HA | No node count (`limits.machines` counts hosted machines); no sync or HA: `sync` and `ha` are licence flags only |
| Air-gapped optional on Pro Team | Offline licences are Enterprise only (`POST /v1/runtimes/{id}/offline-licence`, else 403 `E_NOT_IN_PLAN` `offline`) |
| An audit log on Enterprise | No audit logs, SSO/SAML or RBAC |
| Heartbeat to `/v1/telemetry/heartbeat`: `license_id`, hashed GUID, version, store size; fail-open | `POST /v1/license/verify` with the runtime's token: `{machine, licence_id, version, active_runs}`, answered with a fresh licence; self-hosted runtimes only |
| Keys issued on `invoice.payment_succeeded` and `checkout.session.completed`, kept in `licenses`, emailed | No `licenses` table, no key issued or emailed; the webhook (`checkout.session.completed`, `customer.subscription.*`, `charge.refunded`) keeps the org's plan version and billing status |
| `customer.subscription.deleted` revokes the licence | It puts the org on Free; the next licence (within 24 hours) carries Free |
| Expired key: Community limits after 14 days' grace | A self-hosted runtime's licence is live until `expires_at` plus 14 days; past that rrotor refuses only what needs a licensed mod |
