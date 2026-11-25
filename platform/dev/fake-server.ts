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
 * It answers as the real server does: accounts, orgs, plans and billing, with Ada Cloud on (/v1/me says so and Ada's
 * API answers at /ada/v1: dev/fake-ada.ts; the platform's GLYPHH_ADA_URL=http://localhost:8080/ada). The org starts on
 * Free, each feature saying whether it is built. FAKE_ADA=off turns Ada Cloud off, as a server without
 * GLYPHH_ADA_CLOUD answers. The Marketplace is not the server's: the platform reads it from GitHub itself.
 *
 *   npm run fake-server   → http://localhost:8080
 */
process.loadEnvFile?.('.env');
const platform = process.env.PLATFORM_URL ?? 'http://localhost:3000';
const port = Number(process.env.FAKE_SERVER_PORT ?? 8080);
const adaCloud = process.env.FAKE_ADA !== 'off';
const data = { ...fixtures, ...fixtures.onFree };
const app = new Hono();
// With Ada Cloud on each plan carries its cloud limits, and /v1/me and /v1/billing the org's use of them (`cloud`).
if (adaCloud) data.plans = data.plans.map((plan) => ({ ...plan, cloud: fixtures.cloudLimits[plan.name] ?? null }));
const state = structuredClone(data);
state.me.ada_cloud = adaCloud;
if (adaCloud) state.me.plan = data.plans.find((plan) => plan.name === state.me.plan.name) ?? state.me.plan;
const cloudUsage = adaCloud ? mountAda(app, port, () => state.me.plan.name) : () => null;
// FAKE_LLM=on turns Glyphh's hosted models on, as GLYPHH_LLM=on does: each plan's tokens a month and the models' rates
// on /v1/plans, the month's tokens and the overage balance on /v1/billing, use by day, the balance's history, and a
// top-up that comes straight back as paid.
const llm = process.env.FAKE_LLM === 'on';
if (llm) {
  data.plans = data.plans.map((plan) => ({ ...plan, llm_tokens: fixtures.llmTokens[plan.name] ?? null }));
  state.me.plan = data.plans.find((plan) => plan.name === state.me.plan.name) ?? state.me.plan;
}
const tokens = structuredClone(fixtures.tokenUsage);
const ledger = structuredClone(fixtures.ledger);
const balanceMicros = () => ledger.reduce((sum, entry) => sum + (entry.amount_micros ?? Math.round(entry.amount_cents * 10_000)), 0);
const balance = () => {
  const micros = balanceMicros();
  return { cents: micros / 10_000, micros, low: micros < 5_000_000 };
};
if (llm) {
  app.get('/v1/llm/models', (c) => c.json({ models: fixtures.llmModels }));
  app.get('/v1/llm/usage', (c) => c.json({ days: fixtures.tokenDays }));
  app.get('/v1/billing/ledger', (c) => c.json({ entries: ledger.slice(0, Number(c.req.query('limit') ?? '50')) }));
  app.post('/v1/billing/topup', async (c) => {
    const { amount_cents: cents } = await c.req.json();
    if (!Number.isInteger(cents) || cents < 1_000 || cents > 100_000) return refuse(422, 'E_INVALID', 'Add between $10 and $1,000.', 'amount');
    ledger.unshift({ at: new Date().toISOString(), kind: 'topup', amount_cents: cents, amount_micros: cents * 10_000, model: null, note: null });
    return c.json({ url: `${platform}/settings/billing?topup=1` });
  });
  app.post('/v1/admin/orgs/:id/llm-grant', async (c) => {
    const { amount_cents: cents, note } = await c.req.json();
    ledger.unshift({ at: new Date().toISOString(), kind: 'grant', amount_cents: cents, amount_micros: cents * 10_000, model: null, note });
    return c.json({ message: `Granted $${(cents / 100).toFixed(2)} (fake server).` });
  });
}
// FAKE_STAFF=on signs in as Glyphh's staff (GLYPHH_STAFF_EMAILS): the staff view opens, its pages answered from the
// fixtures, its actions accepted and changing nothing.
if (process.env.FAKE_STAFF === 'on') {
  Object.assign(state.me, { email: staffMe.email, staff: true });
  for (const [path, answer] of Object.entries(staffAnswers)) app.get(`/v1${path}`, (c) => c.json(answer));
  app.post('/v1/admin/events/*', (c) => c.json({ acknowledged: 1 }));
  app.on(['POST', 'DELETE'], '/v1/admin/orgs/:id/:action', (c) => (c.req.param('action') === 'suspend' ? c.body(null, 204) : c.json({ message: 'Done (fake server).' })));
}

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
app.get('/v1/plans', (c) => c.json(llm ? { plans: data.plans, models: fixtures.llmModels } : data.plans));
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
  const { issuer, client_id, domains, enforced } = await c.req.json();
  sso = { ...fixtures.sso, issuer, client_id, domains, enforced, callback_url: `http://localhost:${port}/auth/sso/callback`, updated_at: new Date().toISOString() };
  return c.json(sso);
});
app.delete('/v1/org/sso', (c) => {
  sso = null;
  return c.body(null, 204);
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
  const { plan, org } = state.me;
  const hosted = llm ? { tokens: { ...tokens, max: plan.llm_tokens ?? null }, balance: balance() } : {};
  return c.json({ plan, billing_status: org.billing_status, renews_at: org.renews_at, plan_until: org.plan_until, cloud: cloudUsage(), ...hosted });
});
// The use by day for Home and Usage, and the admin's card on file and invoices.
app.get('/v1/billing/series', (c) => c.json({ days: fixtures.seriesDays(Number(c.req.query('days') ?? '30')) }));
app.get('/v1/billing/payment', (c) => c.json(fixtures.payment));
app.post('/v1/billing/portal', (c) => c.json({ url: `${platform}/billing?done=1` }));

// A change of plan applies at once.
const subscribed = () => !['none', 'canceled', 'incomplete_expired'].includes(state.me.org.billing_status);
const setPlan = (name: string) => {
  const plan = data.plans.find((p) => p.name === name);
  if (!plan) return refuse(422, 'E_INVALID', `${name} isn't sold through Stripe.`, 'not_sold');
  if (!plan.self_serve) return refuse(422, 'E_INVALID', `${name} is by contract: talk to us at sales@glyphh.ai.`, 'not_self_serve');
  if (!state.me.plan.self_serve) return refuse(409, 'E_CONFLICT', `Your ${state.me.plan.name} plan is by contract: talk to us at sales@glyphh.ai.`, 'contract');
  state.me.plan = plan;
  state.org.plan = plan;
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
