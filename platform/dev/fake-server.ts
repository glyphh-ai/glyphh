import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import * as data from '../src/test/fixtures.js';

/**
 * A stand-in Glyphh server for working on the platform without the real one: the OAuth steps (which
 * approve at once), the browser steps and /v1 with the shared fixtures. Not for tests of the server itself.
 *
 *   npm run fake-server   → http://localhost:8080
 */
process.loadEnvFile?.('.env');
const platform = process.env.PLATFORM_URL ?? 'http://localhost:3000';
const port = Number(process.env.FAKE_SERVER_PORT ?? 8080);
const app = new Hono();
const state = structuredClone({ ...data });
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
app.post('/v1/runtime/start', (c) => c.json(Object.assign(state.runtime, { state: 'online' })));
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
app.get('/v1/runtimes/self', (c) => c.json(state.selfRuntimes));
app.post('/v1/runtimes/self', async (c) => {
  const { name, public_url } = await c.req.json();
  const runtime = { id: `rt-self-${nextSelf++}`, name, public_url, state: 'pending' as const, version: null, last_seen_at: null, last_heartbeat_at: null };
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
app.post('/v1/runtimes/:id/offline-licence', async (c) => {
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
app.get('/v1/plans', (c) => c.json(data.plans));
app.get('/v1/addons', (c) => c.json(state.addons));
app.get('/v1/org', (c) => c.json(state.org));
app.patch('/v1/org', async (c) => {
  const name = (await c.req.json()).name;
  state.me.org.name = name;
  return c.json(Object.assign(state.org, { name }));
});
app.get('/v1/org/members', (c) => c.json(state.members));
app.get('/v1/org/invites', (c) => c.json(state.invites));
app.post('/v1/org/invites', () =>
  Response.json(
    { error: { code: 'E_LIMIT', message: 'Pro allows 1 member. Upgrade to Team to invite more.', trace_id: 'dev-trace', limit: 'members', used: 1, max: 1, plan: 'Team' } },
    { status: 403 },
  ),
);
app.post('/v1/billing/addons/preview', async (c) => {
  const { mod, action } = await c.req.json();
  return c.json({ mod, action, prorated_cents: action === 'add' ? 207 : -207, currency: 'usd', monthly_cents: 400, proration_date: Math.floor(Date.now() / 1000) });
});
app.post('/v1/billing/addons', (c) => c.json(state.addons.map((a) => Object.assign(a, { added: true }))));
app.delete('/v1/billing/addons/:mod', (c) => c.json(state.addons.map((a) => Object.assign(a, { added: false }))));
app.post('/v1/billing/portal', (c) => c.json({ url: `${platform}/billing?done=1` }));
app.post('/v1/billing/plan', (c) => c.json(state.org));
app.post('/v1/billing/seats', async (c) => {
  const seats = (await c.req.json()).seats;
  state.me.org.seats = seats;
  return c.json(Object.assign(state.org, { seats }));
});
app.post('/v1/billing/checkout', (c) => c.json({ url: `${platform}/billing?done=1` }));

serve({ fetch: app.fetch, port }, () => console.log(`Fake Glyphh server on http://localhost:${port}`));
