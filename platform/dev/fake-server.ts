import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { feature } from '../src/api/plans.js';
import { staffAnswers, staffMe } from '../src/test/adminData.js';
import * as fixtures from '../src/test/fixtures.js';
import { mountAda } from './fake-ada.js';

/**
 * A stand-in Glyphh server for working on the platform without the real one: the OAuth steps (which
 * approve at once), the browser steps and /v1 with the shared fixtures. Not for tests of the server itself.
 *
 * It answers as the real server does: it only grants licences to the rrotors a person runs, and hosts none (no hosted
 * runtimes, rates or telemetry). The org starts on Free, each plan's runtime nodes as they are and each feature saying
 * whether it is built. FAKE_ADA=on turns Ada Cloud on, as GLYPHH_ADA_CLOUD=on does: /v1/me says so and Ada's API
 * answers at /ada/v1 (dev/fake-ada.ts; the platform's GLYPHH_ADA_URL=http://localhost:8080/ada).
 *
 *   npm run fake-server   → http://localhost:8080
 */
process.loadEnvFile?.('.env');
const platform = process.env.PLATFORM_URL ?? 'http://localhost:3000';
const port = Number(process.env.FAKE_SERVER_PORT ?? 8080);
const adaCloud = process.env.FAKE_ADA === 'on';
const data = { ...fixtures, ...fixtures.onFree };
const app = new Hono();
// With Ada Cloud on each plan carries its cloud limits, and /v1/me and /v1/billing the org's use of them (`cloud`).
if (adaCloud) data.plans = data.plans.map((plan) => ({ ...plan, cloud: fixtures.cloudLimits[plan.name] ?? null }));
const state = structuredClone(data);
state.me.ada_cloud = adaCloud;
if (adaCloud) state.me.plan = data.plans.find((plan) => plan.name === state.me.plan.name) ?? state.me.plan;
const cloudUsage = adaCloud ? mountAda(app, port, () => state.me.plan.name) : () => null;
// FAKE_STAFF=on signs in as Glyphh's staff (GLYPHH_STAFF_EMAILS): the staff view opens, its pages answered from the
// fixtures, its actions accepted and changing nothing.
if (process.env.FAKE_STAFF === 'on') {
  Object.assign(state.me, { email: staffMe.email, staff: true });
  for (const [path, answer] of Object.entries(staffAnswers)) app.get(`/v1${path}`, (c) => c.json(answer));
  app.post('/v1/admin/events/*', (c) => c.json({ acknowledged: 1 }));
  app.on(['POST', 'DELETE'], '/v1/admin/orgs/:id/:action', (c) => (c.req.param('action') === 'suspend' ? c.body(null, 204) : c.json({ message: 'Done (fake server).' })));
}
let nextKey = 10;
let nextSelf = 10;
const selfToken = () => `glyphh_rt_${crypto.randomUUID().replaceAll('-', '')}`;

app.use('/auth/consent', cors({ origin: platform, credentials: true }));

// OAuth: the platform's own client, approved without asking.
app.get('/oauth/authorize', (c) => {
  const q = c.req.query();
  const oauth = Buffer.from(JSON.stringify({ redirect: q.redirect_uri, state: q.state })).toString('base64url');
  return c.redirect(`${platform}/authorize?oauth=${oauth}&client=Glyphh`);
});
app.get('/auth/providers', (c) => c.json({ providers: ['github', 'google'], sso: true }));
app.get('/auth/:provider/start', (c) => {
  const oauth = c.req.query('oauth');
  if (oauth) return c.redirect(`${platform}/allow?consent=${oauth}`);
  const code = c.req.query('code');
  if (code) return c.redirect(`${platform}/device/approve?consent=device.${code}`);
  return c.redirect(`${platform}/settings/profile?linked=${c.req.param('provider')}`);
});
app.get('/auth/consent', (c) => {
  const consent = c.req.query('consent') ?? '';
  if (consent.startsWith('device.')) {
    return c.json({ kind: 'device', code: consent.slice(7), name: 'studio-mac', surface: 'Claude Code', email: data.me.email });
  }
  return c.json({ kind: 'oauth', client: 'Glyphh', returns_to: new URL(platform).host, resource: `http://localhost:${port}/mcp`, email: data.me.email });
});
app.get('/auth/oauth/allow', (c) => {
  const { redirect, state: s } = JSON.parse(Buffer.from(c.req.query('consent') ?? '', 'base64url').toString()) as { redirect: string; state: string };
  return c.redirect(c.req.query('decision') === 'allow' ? `${redirect}?code=dev-code&state=${s}` : `${redirect}?error=access_denied&state=${s}`);
});
app.get('/auth/approve', (c) => c.redirect(`${platform}/device/done?result=${c.req.query('decision') === 'approve' ? 'approved' : 'denied'}`));
app.post('/oauth/token', (c) => c.json({ access_token: 'dev-access', token_type: 'Bearer', expires_in: 3600, refresh_token: `dev-refresh-${Date.now()}`, scope: 'account' }));
app.post('/oauth/revoke', (c) => c.body(null, 200));

// /v1
app.get('/v1/me', (c) => c.json({ ...state.me, cloud: cloudUsage() }));
app.patch('/v1/me', async (c) => c.json(Object.assign(state.me, { name: (await c.req.json()).name })));
app.post('/v1/me/identities', async (c) => c.json({ url: `http://localhost:${port}/auth/${(await c.req.json()).provider}/start?link=1` }));
app.delete('/v1/me/identities/:provider', (c) => {
  state.me.providers = state.me.providers.filter((p) => p !== c.req.param('provider'));
  return c.body(null, 204);
});
app.get('/v1/installs', (c) => c.json(state.installs));
app.delete('/v1/installs/:id', (c) => {
  state.installs = state.installs.filter((i) => i.id !== c.req.param('id'));
  return c.body(null, 204);
});
const refuse = (status: number, code: string, message: string, reason: string) =>
  Response.json({ error: { code, message, trace_id: 'dev-trace', reason } }, { status });
app.get('/v1/runtime/keys', (c) => c.json(state.runtimeKeys));
// A key calls one of the person's self-hosted runtimes; anything else is not found.
app.post('/v1/runtime/keys', async (c) => {
  const { name, runtime_id, expires_in_days: days } = await c.req.json();
  if (!state.selfRuntimes.some((r) => r.id === runtime_id)) return refuse(404, 'E_NOT_FOUND', 'No such self-hosted runtime of yours.', 'runtime');
  const created = new Date();
  const expires = days ? new Date(created.getTime() + days * 86_400_000).toISOString() : null;
  const key = { id: `k-${nextKey++}`, runtime_id, name, created_at: created.toISOString(), expires_at: expires, revoked_at: null, calls: 0, last_used_at: null };
  state.runtimeKeys.push(key);
  return c.json({ ...key, key: `glyphh_rk_${crypto.randomUUID().replaceAll('-', '')}` }, 201);
});
app.delete('/v1/runtime/keys/:id', (c) => {
  const key = state.runtimeKeys.find((k) => k.id === c.req.param('id'))!;
  key.revoked_at = new Date().toISOString();
  return c.json(key);
});
app.delete('/v1/runtime/keys/:id/record', (c) => {
  state.runtimeKeys = state.runtimeKeys.filter((k) => k.id !== c.req.param('id'));
  return c.body(null, 204);
});
// The runtimes a person runs at their own address: registered, their token rotated, deleted. Glyphh hosts none.
app.get('/v1/runtimes/self', (c) => c.json(state.selfRuntimes));
app.post('/v1/runtimes/self', async (c) => {
  const { name, public_url } = await c.req.json();
  const runtime = { id: `rt-self-${nextSelf++}`, name, public_url, state: 'stopped' as const, version: null, last_seen_at: null, last_heartbeat_at: null };
  state.selfRuntimes.push(runtime);
  const token = selfToken();
  const env = {
    RROTOR_MODE: 'self',
    RROTOR_SERVER: `http://localhost:${port}`,
    RROTOR_RUNTIME_ID: runtime.id,
    RROTOR_RUNTIME_TOKEN: token,
    RROTOR_PUBLIC_HOST: new URL(public_url).host,
  };
  return c.json({ id: runtime.id, name, public_url, token, env }, 201);
});
app.post('/v1/runtimes/self/:id/token', (c) => c.json({ token: selfToken() }));
// Its record, keys and nodes go; its own volume is untouched.
app.delete('/v1/runtimes/self/:id', (c) => {
  const id = c.req.param('id');
  state.selfRuntimes = state.selfRuntimes.filter((r) => r.id !== id);
  state.runtimeKeys = state.runtimeKeys.filter((k) => k.runtime_id !== id);
  state.nodes.nodes = state.nodes.nodes.filter((n) => n.runtime_id !== id);
  state.nodes.count = state.nodes.nodes.length;
  state.nodes.over = state.nodes.max_nodes !== null && state.nodes.count > state.nodes.max_nodes;
  return c.body(null, 204);
});
app.post('/v1/runtimes/:id/offline-licence', async (c) => {
  if (!feature(state.me.plan, 'offline').included) return refuse(403, 'E_NOT_IN_PLAN', 'Offline licences are on Enterprise.', 'offline');
  const { days } = await c.req.json();
  const expires_at = new Date(Date.now() + days * 86_400_000).toISOString();
  const payload = { runtime_id: c.req.param('id'), licence_id: crypto.randomUUID(), kind: 'offline', expires_at, grace_days: 14 };
  const token = Buffer.from(JSON.stringify({ payload, signature: 'dev-signature' })).toString('base64url');
  return c.json({ token, expires_at });
});
// The licence key: one for the paid month, none on Free (rrotor runs as Community). The runtime nodes, counted softly.
app.get('/v1/license/keys', (c) => c.json(state.licenceKeys));
app.get('/v1/license/nodes', (c) => c.json(state.nodes));
app.get('/v1/plans', (c) => c.json(data.plans));
app.get('/v1/org', (c) => c.json(state.org));
app.patch('/v1/org', async (c) => {
  const name = (await c.req.json()).name;
  state.me.org.name = name;
  return c.json(Object.assign(state.org, { name }));
});
app.get('/v1/org/members', (c) => c.json(state.members));
app.get('/v1/org/invites', (c) => c.json(state.invites));
// Single sign-on (Enterprise): set, read and removed; the secret is never shown back.
let sso: typeof fixtures.sso | null = null;
app.get('/v1/org/sso', (c) => c.json(sso));
app.put('/v1/org/sso', async (c) => {
  if (!feature(state.me.plan, 'sso').included) return refuse(403, 'E_NOT_IN_PLAN', 'Single sign-on is on Enterprise, not Free: talk to us at sales@glyphh.ai.', 'sso');
  const { issuer, client_id, domains, enforced, reviewers = [] } = await c.req.json();
  sso = { ...fixtures.sso, issuer, client_id, domains, enforced, reviewers, callback_url: `http://localhost:${port}/auth/sso/callback`, updated_at: new Date().toISOString() };
  return c.json(sso);
});
app.delete('/v1/org/sso', (c) => {
  sso = null;
  return c.body(null, 204);
});
// The catalogue of artifacts (the pages Claude published to the org's rrotors): listed by state, searched, paged;
// a review changes the state. The person is the admin, so a reviewer.
const artifacts = structuredClone(fixtures.artifacts);
app.get('/v1/artifacts', (c) => {
  const state = c.req.query('state') ?? 'approved';
  const q = (c.req.query('q') ?? '').toLowerCase();
  const page = Math.max(1, Number(c.req.query('page') ?? '1'));
  const perPage = Math.min(100, Math.max(1, Number(c.req.query('per_page') ?? '24')));
  if (state !== 'approved' && state.me.role !== 'admin') return refuse(403, 'E_FORBIDDEN', 'Only a reviewer sees artifacts awaiting review.', 'reviewer');
  const found = artifacts.filter((a) => a.state === state && (!q || [a.title, a.description, a.name].some((s) => s.toLowerCase().includes(q))));
  return c.json({ artifacts: found.slice((page - 1) * perPage, page * perPage), page, per_page: perPage, total: found.length });
});
app.get('/v1/artifacts/:id', (c) => {
  const found = artifacts.find((a) => a.id === c.req.param('id'));
  return found ? c.json(found) : refuse(404, 'E_NOT_FOUND', 'No such artifact.', 'artifact');
});
app.post('/v1/artifacts/:id/:action', async (c) => {
  const found = artifacts.find((a) => a.id === c.req.param('id'));
  if (!found) return refuse(404, 'E_NOT_FOUND', 'No such artifact.', 'artifact');
  const action = c.req.param('action');
  const reviewed = { reviewed_by: { id: state.me.id, name: state.me.name, email: state.me.email }, reviewed_at: new Date().toISOString() };
  if (action === 'approve') {
    if (found.state === 'approved' || found.state === 'retired') return refuse(409, 'E_CONFLICT', `${found.title} is ${found.state} already.`, 'state');
    Object.assign(found, { state: 'approved', reason: null }, reviewed);
  } else if (action === 'reject') {
    const { reason } = await c.req.json();
    Object.assign(found, { state: 'rejected', reason }, reviewed);
  } else if (action === 'retire') {
    Object.assign(found, { state: 'retired' }, reviewed);
  } else return refuse(404, 'E_NOT_FOUND', 'No such action.', 'action');
  return c.json(found);
});
// Members are unlimited on every plan.
app.post('/v1/org/invites', async (c) => {
  const created = new Date();
  const invite = { id: crypto.randomUUID(), email: (await c.req.json()).email, expires_at: new Date(created.getTime() + 7 * 86_400_000).toISOString(), created_at: created.toISOString() };
  state.invites.push(invite);
  return c.json({ invite, link: `${platform}/join?invite=${invite.id}` }, 201);
});
app.delete('/v1/org/invites/:id', (c) => {
  state.invites = state.invites.filter((i) => i.id !== c.req.param('id'));
  return c.body(null, 204);
});
app.get('/v1/billing', (c) => {
  const { plan, org, precedents } = state.me;
  return c.json({ plan, billing_status: org.billing_status, renews_at: org.renews_at, plan_until: org.plan_until, precedents, cloud: cloudUsage() });
});
app.post('/v1/billing/portal', (c) => c.json({ url: `${platform}/billing?done=1` }));
// A paid plan's key expires at the end of the paid month; a new plan revokes the old keys and issues one. Free and
// Basic have none (rrotor has no basic tier: a node on Basic runs as Free's).
const licenceFor = (plan: (typeof data.plans)[number]) => {
  const now = new Date();
  for (const key of state.licenceKeys.keys) if (key.state === 'live') Object.assign(key, { state: 'revoked', revoked_at: now.toISOString() });
  state.nodes.max_nodes = plan.limits.machines;
  state.nodes.over = plan.limits.machines !== null && state.nodes.count > plan.limits.machines;
  if (plan.price_cents === 0 || plan.name === 'Basic') {
    state.licenceKeys.license_key = null;
    return;
  }
  const terms = {
    license_id: crypto.randomUUID(),
    tier: plan.name.toLowerCase(),
    max_nodes: plan.limits.machines,
    max_precedents: plan.limits.precedents,
    cluster_sync_enabled: feature(plan, 'sync').included,
    issued_at: now.toISOString(),
    expires_at: new Date(now.getTime() + 31 * 86_400_000).toISOString(),
  };
  const payload = Buffer.from(JSON.stringify({ ...terms, customer_id: state.org.id })).toString('base64url');
  const key = `${payload}.${Buffer.from('dev-signature').toString('base64url')}`;
  state.licenceKeys.keys.unshift({ ...terms, revoked_at: null, state: 'live', key });
  state.licenceKeys.license_key = key;
};

// A change of plan applies at once.
const subscribed = () => !['none', 'canceled', 'incomplete_expired'].includes(state.me.org.billing_status);
const setPlan = (name: string) => {
  const plan = data.plans.find((p) => p.name === name);
  if (!plan) return refuse(422, 'E_INVALID', `${name} isn't sold through Stripe.`, 'not_sold');
  if (!plan.self_serve) return refuse(422, 'E_INVALID', `${name} is by contract: talk to us at sales@glyphh.ai.`, 'not_self_serve');
  if (!state.me.plan.self_serve) return refuse(409, 'E_CONFLICT', `Your ${state.me.plan.name} plan is by contract: talk to us at sales@glyphh.ai.`, 'contract');
  state.me.plan = plan;
  state.org.plan = plan;
  state.me.precedents.limit = plan.limits.precedents;
  licenceFor(plan);
  return Response.json(state.org);
};
app.post('/v1/billing/plan', async (c) =>
  subscribed() ? setPlan((await c.req.json()).plan) : refuse(409, 'E_CONFLICT', 'Your org isn’t subscribed: start with checkout.', 'not_subscribed'),
);
// Checkout comes straight back as paid.
app.post('/v1/billing/checkout', async (c) => {
  if (subscribed()) return refuse(409, 'E_CONFLICT', 'Your org is already subscribed: change plan instead.', 'subscribed');
  const refused = setPlan((await c.req.json()).plan);
  if (!refused.ok) return refused;
  state.me.org.billing_status = 'active';
  return c.json({ url: `${platform}/billing?done=1` });
});

serve({ fetch: app.fetch, port }, () => console.log(`Fake Glyphh server on http://localhost:${port}`));
