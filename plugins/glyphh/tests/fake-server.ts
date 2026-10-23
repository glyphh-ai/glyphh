// A fake Glyphh server in memory, to the API in server/docs/architecture.md:
// no network. Each call is recorded with its bearer.
import type { HttpInit, HttpResponse } from 'claude-code'

type Json = Record<string, unknown>
export type Call = { method: string; path: string; body: Json; bearer?: string }

const TOKEN = 'tok-secret-1'

const version = (name: string, status: string, models: number, more: Json = {}) => ({
  name,
  kernel: name === 'ada-1-0' ? '3.12.2' : '3.13.0',
  status,
  beta: name.endsWith('-beta'),
  open: true,
  released: '2026-10-20',
  deprecated: null,
  ends: null,
  changes_answers: name !== 'ada-1-0',
  aliases: [],
  summary: '',
  notes: '',
  models,
  ...more,
})

/** GET /v1/ada for the org, as contract 5's fixture `the Ada versions`. */
export const ADA = { latest_stable: 'ada-1-0', contract: 5, versions: [version('ada-1-1-beta', 'beta', 1), version('ada-1-0', 'stable', 2)] }
/** A later registry: ada-1-1 stable, ada-1-0 deprecated, ada-0-9 retired. */
export const ADA_LATER = {
  latest_stable: 'ada-1-1',
  contract: 5,
  versions: [
    version('ada-1-1', 'stable', 1, { aliases: ['ada-1-1-beta'] }),
    version('ada-1-0', 'deprecated', 2, { deprecated: '2026-10-21', ends: '2027-04-21' }),
    version('ada-0-9', 'retired', 0, { deprecated: '2026-04-01', ends: '2026-10-01' }),
  ],
}

function newState() {
  return {
    calls: [] as Call[],
    polls: ['authorization_pending', 'slow_down', 'ok'] as string[],
    members: [
      { user_id: 'u1', name: 'Chris', email: 'chris@example.com', role: 'admin' },
      { user_id: 'u2', name: 'Sam', email: 'sam@example.com', role: 'member' },
    ] as Json[],
    invites: [] as Json[],
    installs: [{ id: 'i1', name: 'mac', surface: 'desktop' }, { id: 'i2', name: 'laptop', surface: 'cli' }] as Json[],
    role: 'admin',
    providers: ['google'] as string[],
    name: 'Chris',
    orgName: 'Glyphh',
    plan: 'Free',
    billingStatus: 'none',
    /** Reads made this month, the org's. */
    reads: 1234,
    /** /v1/me's `cloud.ada`: the Ada host's GET /v1/ada for the org (null: a server without it). */
    ada: ADA as Json | null,
  }
}

type State = ReturnType<typeof newState>

// GET /v1/plans as the server lists them, each with its Ada Cloud caps
// (glyphh_server.ops.plans.CloudLimits): Enterprise's price and caps are each
// contract's own, so null; it is never checked out.
const plan = (name: string, price_cents: number | null, interval: string | null, precedents: number | null, reads: number | null, rps: number | null) => {
  const overage = price_cents !== null && price_cents > 0
  return {
    name,
    version: 1,
    price_cents,
    interval,
    self_serve: price_cents !== null,
    cloud: { precedents, requests_per_month: reads, requests_per_second: rps, overage, overage_cents_per_10k: overage ? 100 : null },
  }
}

export const PLANS = [
  plan('Free', 0, null, 1000, 5000, 5),
  plan('Basic', 2000, 'month', 10000, 50000, 10),
  plan('Pro', 9900, 'month', 100000, 1000000, 50),
  plan('Team', 29900, 'month', 1000000, 5000000, 200),
  plan('Enterprise', null, 'year', null, null, null),
]

const meOf = (s: State) => {
  const p = PLANS.find(x => x.name === s.plan) ?? PLANS[0]!
  const max = p.cloud.requests_per_month
  return {
    id: 'u1',
    email: 'chris@example.com',
    name: s.name,
    role: s.role,
    providers: [...s.providers],
    org: { id: 'o1', name: s.orgName, billing_status: s.billingStatus, renews_at: null, plan_until: s.plan === 'Enterprise' ? '2027-10-18T23:59:59Z' : null },
    plan: p,
    // glyphh_ada.usage.CloudUsage
    cloud: {
      plan: p.name,
      month: '2026-10',
      resets_at: '2026-11-01',
      models: 2,
      precedents: { used: 432, max: p.cloud.precedents },
      requests: { used: s.reads, max, over: max !== null && p.cloud.overage ? Math.max(0, s.reads - max) : 0, overage: p.cloud.overage },
      requests_per_second: p.cloud.requests_per_second,
      ...(s.ada ? { ada: s.ada } : {}),
    },
  }
}

const refuse = (status: number, code: string, message: string, detail: Json = {}) => ({
  status,
  body: { error: { code, message, trace_id: 'tr-1', ...detail } },
})


async function route(s: State, c: Call): Promise<{ status: number; body: unknown }> {
  const ok = (body: unknown = {}) => ({ status: 200, body })
  const open = ['/v1/device/code', '/v1/device/token', '/v1/plans']
  if (!open.includes(c.path) && c.bearer !== TOKEN) return refuse(401, 'E_UNAUTHORIZED', 'Bad token.')
  const key = `${c.method} ${c.path.replace(/\/v1\/(installs|org\/members|org\/invites|me\/identities)\/[^/]+$/, '/v1/$1/:id')}`
  const id = decodeURIComponent(c.path.split('/').pop() ?? '')
  switch (key) {
    case 'POST /v1/device/code':
      return ok({ device_code: 'dc-1', user_code: 'ABCD-EFGH', verification_uri: 'https://glyphh.test/v1/device', verification_uri_complete: 'https://glyphh.test/v1/device?code=ABCD-EFGH', interval: 5, expires_in: 600 })
    case 'POST /v1/device/token': {
      const next = s.polls.shift() ?? 'ok'
      return next === 'ok' ? ok({ access_token: TOKEN, install_id: 'i1' }) : { status: 400, body: { error: next } }
    }
    case 'GET /v1/me': return ok(meOf(s))
    case 'PATCH /v1/me': s.name = String(c.body.name); return ok(meOf(s))
    case 'POST /v1/me/identities': {
      const p = String(c.body.provider)
      if (s.providers.includes(p)) return refuse(409, 'E_CONFLICT', `${p} is already linked.`)
      return ok({ url: `https://accounts.${p}.test/auth?link=1` })
    }
    case 'DELETE /v1/me/identities/:id':
      if (s.providers.length <= 1) return refuse(409, 'E_CONFLICT', 'You need at least one way to sign in.')
      s.providers = s.providers.filter(p => p !== id); return { status: 204, body: '' }
    case 'GET /v1/installs': return ok({ installs: s.installs })
    case 'DELETE /v1/installs/:id': s.installs = s.installs.filter(i => i.id !== id); return ok()
    case 'POST /v1/sign-out': return ok()
    default: return adminRoute(s, c, key, id, ok)
  }
}


function adminRoute(s: State, c: Call, key: string, id: string, ok: (b?: unknown) => { status: number; body: unknown }) {
  const isWrite = c.method !== 'GET'
  if (isWrite && s.role !== 'admin' && key.includes('/org')) return refuse(403, 'E_FORBIDDEN', 'Admins only.')
  switch (key) {
    case 'GET /v1/org': return ok({ id: 'o1', name: s.orgName })
    case 'PATCH /v1/org': s.orgName = String(c.body.name); return ok()
    case 'GET /v1/org/members': return ok({ members: s.members })
    case 'DELETE /v1/org/members/:id': s.members = s.members.filter(m => m.user_id !== id); return ok()
    case 'GET /v1/org/invites': return ok({ invites: s.invites })
    case 'POST /v1/org/invites': {
      s.invites.push({ id: `inv-${s.invites.length + 1}`, email: c.body.email })
      return ok({ id: 'inv-1', link: 'https://glyphh.test/join?t=abc' })
    }
    case 'DELETE /v1/org/invites/:id': s.invites = s.invites.filter(i => i.id !== id); return ok()
    case 'GET /v1/plans': return ok(PLANS)
    case 'POST /v1/billing/checkout': return checkout(s, c, ok)
    case 'POST /v1/billing/portal': return ok({ url: 'https://billing.stripe.test/p1' })
    case 'POST /v1/billing/plan': return changePlan(s, c, ok)
    default: return refuse(404, 'E_NOT_FOUND', `No route ${key}`)
  }
}


// The server's refusals: Enterprise is never checked out, a subscribed org
// changes plan instead, an Enterprise org's plan is its contract's.
function checkout(s: State, c: Call, ok: (b?: unknown) => { status: number; body: unknown }) {
  const p = PLANS.find(x => x.name === c.body.plan)
  if (p && !p.self_serve) return refuse(422, 'E_INVALID', 'Enterprise is by contract: talk to us at sales@glyphh.ai.', { reason: 'not_self_serve' })
  if (s.billingStatus === 'active') return refuse(409, 'E_CONFLICT', 'Your org is already subscribed: change plan instead.', { reason: 'subscribed' })
  return ok({ url: 'https://checkout.stripe.test/c1' })
}

function changePlan(s: State, c: Call, ok: (b?: unknown) => { status: number; body: unknown }) {
  if (s.plan === 'Enterprise') return refuse(409, 'E_CONFLICT', 'Your Enterprise plan is by contract: talk to us at sales@glyphh.ai.', { reason: 'contract' })
  if (s.billingStatus !== 'active') return refuse(409, 'E_CONFLICT', "Your org isn't subscribed: start with checkout.", { reason: 'not_subscribed' })
  s.plan = String(c.body.plan)
  return ok({ id: 'o1', name: s.orgName })
}


export function fakeServer() {
  const s = newState()
  async function fetch(url: string, init: HttpInit = {}): Promise<HttpResponse> {
    const u = new URL(url)
    const bearer = init.headers?.Authorization?.replace(/^Bearer /, '')
    const call: Call = { method: init.method ?? 'GET', path: u.pathname, body: init.body ? (JSON.parse(init.body) as Json) : {}, bearer }
    s.calls.push(call)
    const r = await route(s, call)
    return { status: r.status, ok: r.status < 300, headers: {}, text: r.status === 204 ? "" : JSON.stringify(r.body) }
  }

  return { s, fetch, TOKEN }
}
