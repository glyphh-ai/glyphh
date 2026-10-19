import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { feature } from '../src/api/plans.js';
import * as fixtures from '../src/test/fixtures.js';

/**
 * A stand-in Glyphh server for working on the platform without the real one: the OAuth steps (which
 * approve at once), the browser steps and /v1 with the shared fixtures. Not for tests of the server itself.
 *
 * It answers as the real server does by default: hosting off (the hosted machine routes and the rates refused with
 * 503 E_UNAVAILABLE reason hosting_off), each plan's runtime nodes as they are, and each feature saying whether it is
 * built. FAKE_HOSTING=on turns hosting back on, as GLYPHH_HOSTING=on does.
 *
 *   npm run fake-server   → http://localhost:8080
 */
process.loadEnvFile?.('.env');
const platform = process.env.PLATFORM_URL ?? 'http://localhost:3000';
const port = Number(process.env.FAKE_SERVER_PORT ?? 8080);
const hosting = process.env.FAKE_HOSTING === 'on';
const data = hosting ? { ...fixtures } : { ...fixtures, ...fixtures.hostingOff };
const app = new Hono();
const state = structuredClone(data);
let nextKey = 10;
let nextSelf = 10;
let nextMachine = 10;
const selfToken = () => `glyphh_rt_${crypto.randomUUID().replaceAll('-', '')}`;

app.use('/auth/consent', cors({ origin: platform, credentials: true }));

// OAuth: the platform's own client, approved without asking.
app.get('/oauth/authorize', (c) => {
  const q = c.req.query();
  const oauth = Buffer.from(JSON.stringify({ redirect: q.redirect_uri, state: q.state })).toString('base64url');
  return c.redirect(`${platform}/authorize?oauth=${oauth}&client=Glyphh`);
});
app.get('/auth/providers', (c) => c.json({ providers: ['github', 'google'] }));
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
app.get('/v1/me', (c) => c.json(state.me));
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
app.get('/v1/runtime', (c) => c.json(state.runtime));
app.post('/v1/runtime/start', (c) => hostingOff() ?? c.json(Object.assign(state.runtime, { state: 'online' })));
app.post('/v1/runtime/stop', (c) => c.json(Object.assign(state.runtime, { state: 'stopped' })));
app.get('/v1/runtime/keys', (c) => c.json(state.runtimeKeys));
app.post('/v1/runtime/keys', async (c) => {
  const { name, expires_in_days: days } = await c.req.json();
  const created = new Date();
  const expires = days ? new Date(created.getTime() + days * 86_400_000).toISOString() : null;
  const key = { id: `k-${nextKey++}`, name, created_at: created.toISOString(), expires_at: expires, revoked_at: null, calls: 0, last_used_at: null };
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
// Hosted machines, as many runtime nodes as the plan allows (none on Free). The old /v1/runtime above stands for the first.
const refuse = (status: number, code: string, message: string, reason: string) =>
  Response.json({ error: { code, message, trace_id: 'dev-trace', reason } }, { status });
// With hosting off no hosted machine is made or started.
const hostingOff = () => (hosting ? undefined : refuse(503, 'E_UNAVAILABLE', 'Glyphh is not hosting machines now. Run rrotor yourself.', 'hosting_off'));
const machine = (id: string) => state.machines.find((m) => m.id === id);
const setMachine = (id: string, to: 'online' | 'stopped') => {
  const found = machine(id);
  if (!found) return refuse(404, 'E_NOT_FOUND', 'No such machine.', 'runtime');
  // A machine past what the plan allows stays stopped.
  const allowed = state.me.plan.limits.machines;
  if (to === 'online' && !hosting) return hostingOff()!;
  if (to === 'online' && allowed !== null && state.machines.indexOf(found) >= allowed) {
    return refuse(403, 'E_LIMIT', `${state.me.plan.name} allows ${allowed} machines.`, 'machines');
  }
  return Response.json(Object.assign(found, { state: to }));
};
app.get('/v1/runtimes', (c) => c.json(state.machines));
app.post('/v1/runtimes', async (c) => {
  const off = hostingOff();
  if (off) return off;
  const { name, size } = await c.req.json();
  const { name: plan, limits, price_cents } = state.me.plan;
  // Hosted machines are on the paid plans; each counts as one of the plan's runtime nodes, as a self-hosted one does.
  if (price_cents === 0) return refuse(403, 'E_LIMIT', 'Hosted machines are on Pro and Team.', 'machines');
  if (limits.machines !== null && state.machines.length + state.selfRuntimes.length >= limits.machines) {
    return refuse(403, 'E_LIMIT', `${plan} allows ${limits.machines} runtime nodes.`, 'machines');
  }
  const id = `rt-${nextMachine++}`;
  const made = { id, name, size, state: 'online' as const, address: `https://chris-${id.slice(3)}.glyphh.app`, month_seconds: 0, created_at: new Date().toISOString() };
  state.machines.push(made);
  return c.json(made, 201);
});
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
app.delete('/v1/runtimes/self/:id', (c) => {
  state.selfRuntimes = state.selfRuntimes.filter((r) => r.id !== c.req.param('id'));
  return c.body(null, 204);
});
app.get('/v1/runtimes/:id', (c) => {
  const found = machine(c.req.param('id'));
  return found ? c.json(found) : refuse(404, 'E_NOT_FOUND', 'No such machine.', 'runtime');
});
app.post('/v1/runtimes/:id/start', (c) => setMachine(c.req.param('id'), 'online'));
app.post('/v1/runtimes/:id/stop', (c) => setMachine(c.req.param('id'), 'stopped'));
app.post('/v1/runtimes/:id/restart', (c) => setMachine(c.req.param('id'), 'online'));
app.delete('/v1/runtimes/:id', (c) => {
  const found = machine(c.req.param('id'));
  if (!found) return refuse(404, 'E_NOT_FOUND', 'No such machine.', 'runtime');
  if (c.req.query('confirm') !== found.name) return refuse(422, 'E_INVALID', 'Type the machine’s name to delete it.', 'confirm');
  state.machines = state.machines.filter((m) => m !== found);
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
app.get('/v1/models', (c) => c.json(state.models));
app.delete('/v1/models/:id', (c) => {
  state.models = state.models.filter((m) => m.id !== c.req.param('id'));
  return c.body(null, 204);
});
// The licence key: one for the paid month, none on Free (rrotor runs as Community). The runtime nodes, counted softly.
app.get('/v1/license/keys', (c) => c.json(state.licenceKeys));
app.get('/v1/license/nodes', (c) => c.json(state.nodes));
app.get('/v1/plans', (c) => c.json(data.plans));
app.get('/v1/rates', (c) => hostingOff() ?? c.json(data.rates));
app.get('/v1/org', (c) => c.json(state.org));
app.patch('/v1/org', async (c) => {
  const name = (await c.req.json()).name;
  state.me.org.name = name;
  return c.json(Object.assign(state.org, { name }));
});
app.get('/v1/org/members', (c) => c.json(state.members));
app.get('/v1/org/invites', (c) => c.json(state.invites));
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
  const { plan, org, precedents, hosting } = state.me;
  return c.json({ plan, billing_status: org.billing_status, renews_at: org.renews_at, plan_until: org.plan_until, precedents, hosting });
});
app.post('/v1/billing/portal', (c) => c.json({ url: `${platform}/billing?done=1` }));
// A paid plan's key expires at the end of the paid month; a new plan revokes the old keys and issues one. Free has none.
const licenceFor = (plan: (typeof data.plans)[number]) => {
  const now = new Date();
  for (const key of state.licenceKeys.keys) if (key.state === 'live') Object.assign(key, { state: 'revoked', revoked_at: now.toISOString() });
  state.nodes.max_nodes = plan.limits.machines;
  state.nodes.over = plan.limits.machines !== null && state.nodes.count > plan.limits.machines;
  if (plan.price_cents === 0) {
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

// A change of plan applies at once; down to Free, the hosted machines must go first.
const subscribed = () => !['none', 'canceled', 'incomplete_expired'].includes(state.me.org.billing_status);
const setPlan = (name: string) => {
  const plan = data.plans.find((p) => p.name === name);
  if (!plan) return refuse(422, 'E_INVALID', `${name} isn't sold through Stripe.`, 'not_sold');
  if (!plan.self_serve) return refuse(422, 'E_INVALID', `${name} is by contract: talk to us at sales@glyphh.ai.`, 'not_self_serve');
  if (!state.me.plan.self_serve) return refuse(409, 'E_CONFLICT', `Your ${state.me.plan.name} plan is by contract: talk to us at sales@glyphh.ai.`, 'contract');
  if (plan.price_cents === 0 && state.machines.length > 0) return refuse(409, 'E_CONFLICT', 'Delete your hosted machines first.', 'machines');
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
