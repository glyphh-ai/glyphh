// A fake Glyphh server in memory, to the API in server/docs/architecture.md:
// no network. Each call is recorded with its bearer.
import type { HttpInit, HttpResponse } from 'claude-code'

type Json = Record<string, unknown>
export type Call = { method: string; path: string; body: Json; bearer?: string; query: Record<string, string> }

const TOKEN = 'tok-secret-1'
/** The local rrotor's token (~/.glyphh/rrotor/token), as the rrotor skill keeps it. */
export const RROTOR_TOKEN = 'rt-local-1'

/** The six types, in the order the fixtures take them: app 1 is a page, app 2 a dashboard, … */
export const TYPES = ['page', 'dashboard', 'doc', 'diagram', 'deck', 'design']

/** One of the organisation's apps, as GET /v1/apps lists them. */
export const app = (n: number, state = 'approved', more: Json = {}): Json => ({
  id: `a${n}`,
  runtime_id: 'rt-1',
  runtime_name: 'acme-prod',
  runtime_url: 'https://rrotor.acme.test',
  name: `app-${n}`,
  title: `App ${n}`,
  description: `The ${n}th app.`,
  type: TYPES[(n - 1) % TYPES.length],
  version: 1,
  commit_sha: 'c'.repeat(40),
  roles: n % 2 ? [] : ['sre'],
  state,
  submitted_by: { id: 'u1', name: 'Chris', email: 'chris@example.com' },
  submitted_at: '2026-11-01T10:00:00Z',
  reviewed_by: null,
  reviewed_at: null,
  reason: state === 'rejected' ? 'Not yet.' : null,
  url: `https://rrotor.acme.test/apps/app-${n}/`,
  ...more,
})

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
    /** /v1/me's `reviewer`: the admin, or a member of a reviewer group. */
    reviewer: true,
    groups: ['sre'] as string[],
    /** The catalogue: three published (a page, a dashboard, a doc), one awaiting review, one rejected. */
    apps: [app(1), app(2), app(3), app(4, 'draft'), app(5, 'rejected')] as Json[],
    /** The local rrotor: what was published to it (POST /v1/apps); `rrotorDown` makes its address unreachable. */
    published: [] as Json[],
    rrotorDown: false,
    /** A rrotor before 0.2.0: no /v1/apps, only Not Found. */
    rrotorOld: false,
    /** The local rrotor's link (its /v1/health): the runtime id and token it holds, and the link's state;
     *  `linkStalls` keeps it `connecting` after a token; `tokens` is what PUT /v1/runtime/token received. */
    rrotor: { runtime_id: null as string | null, link: 'no_token', version: '0.2.0' },
    linkStalls: false,
    /** The link's state once a token lands (not stalling): online, or a stop such as `refused`. */
    linkOutcome: 'online',
    tokens: [] as Json[],
    /** POST /v1/runtime/local: the runtime ids and tokens the server issued (each call rotates the token). */
    issued: 0,
    /** The install's token is a connector's, which the server refuses a local runtime for. */
    noInstall: false,
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
    reviewer: s.reviewer,
    groups: [...s.groups],
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
  const key = `${c.method} ${c.path
    .replace(/\/v1\/(installs|org\/members|org\/invites|me\/identities)\/[^/]+$/, '/v1/$1/:id')
    .replace(/\/v1\/apps\/[^/]+\/(approve|reject|retire)$/, '/v1/apps/:id/$1')}`
  const id = decodeURIComponent(c.path.split('/').pop() ?? '')
  if (key.startsWith('GET /v1/apps') || key.startsWith('POST /v1/apps/')) return appsRoute(s, c, key, ok)
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
    case 'POST /v1/runtime/local':
      if (s.noInstall) return refuse(422, 'E_INVALID', 'A local runtime belongs to an install: link it from Claude Code.', { reason: 'no_install' })
      s.issued += 1
      return ok({ runtime_id: 'rt-local-1', token: `rtok-${s.issued}` })
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


// The catalogue (server/docs/specs/apps.md, 3.3): a page of the state asked,
// searched by title, description and name, one type or every type; a review
// changes a state and is a reviewer's; a member asking for drafts is refused.
function appsRoute(s: State, c: Call, key: string, ok: (b?: unknown) => { status: number; body: unknown }) {
  if (key === 'GET /v1/apps') {
    const state = c.query.state ?? 'approved'
    if (state !== 'approved' && !s.reviewer) return refuse(403, 'E_FORBIDDEN', 'Reviewers see the drafts.')
    const type = c.query.type ?? ''
    if (type && !TYPES.includes(type)) return refuse(422, 'E_INVALID', 'type is one of page, dashboard, doc, diagram, deck, design.')
    const q = (c.query.q ?? '').toLowerCase()
    const page = Number(c.query.page ?? '1')
    const per = Number(c.query.per_page ?? '24')
    const found = s.apps.filter(
      a => a.state === state && (!type || a.type === type) && (!q || [a.title, a.description, a.name].some(t => String(t).toLowerCase().includes(q))),
    )
    return ok({ apps: found.slice((page - 1) * per, page * per), page, per_page: per, total: found.length })
  }
  const id = c.path.split('/')[3] ?? ''
  const verb = key.split('/').pop()
  const a = s.apps.find(x => x.id === id)
  if (!a) return refuse(404, 'E_NOT_FOUND', 'No such app.')
  if (!s.reviewer) return refuse(403, 'E_FORBIDDEN', 'Only a reviewer may do that.')
  if (verb === 'approve' && !['draft', 'rejected'].includes(String(a.state))) return refuse(409, 'E_CONFLICT', `It is ${a.state}, not awaiting review.`)
  if (verb === 'reject' && !String(c.body.reason ?? '').trim()) return refuse(422, 'E_INVALID', 'A rejection says why.')
  a.state = verb === 'approve' ? 'approved' : verb === 'reject' ? 'rejected' : 'retired'
  a.reason = verb === 'reject' ? c.body.reason : null
  return ok(a)
}

// The local rrotor's POST /v1/apps (rrotor's docs/architecture.md, 5.8), its
// GET /v1/health (the link's state) and PUT /v1/runtime/token (the link made).
function rrotorRoute(s: State, c: Call): { status: number; body: unknown } {
  if (c.bearer !== RROTOR_TOKEN) return refuse(401, 'E_AUTH', 'Send the local token: Authorization: Bearer <local token>.')
  if (c.method === 'GET' && c.path === '/v1/health') {
    return { status: 200, body: { version: s.rrotor.version, mode: 'local', runtime_id: s.rrotor.runtime_id, link: { state: s.rrotor.link, since: 0, last_close: null, owed: 0, seq: 0 } } }
  }
  if (c.method === 'PUT' && c.path === '/v1/runtime/token') {
    if (!c.body.runtime_id || !c.body.token) return refuse(400, 'E_INVALID', 'Send {runtime_id, token}.')
    s.tokens.push(c.body)
    s.rrotor.runtime_id = String(c.body.runtime_id)
    s.rrotor.link = s.linkStalls ? 'connecting' : s.linkOutcome
    return { status: 200, body: { runtime_id: s.rrotor.runtime_id, link: 'connecting' } }
  }
  if (c.method !== 'POST' || c.path !== '/v1/apps' || s.rrotorOld) return refuse(404, 'E_NOT_FOUND', 'Not Found')
  const name = String(c.body.name ?? '')
  if (!/^[a-z][a-z0-9-]{0,62}$/.test(name)) return refuse(400, 'E_MANIFEST', `${name || '(none)'} is not a program name: ^[a-z][a-z0-9-]{0,62}$.`)
  const version = s.published.filter(a => a.program === name).length + 1
  const type = String(c.body.type ?? 'page')
  if (!TYPES.includes(type)) return refuse(400, 'E_INPUTS', 'type is one of page, dashboard, doc, diagram, deck, design.')
  const made = { program: name, version, commit_sha: 'd'.repeat(40), deployed_at: '2026-11-01T12:00:00Z', type, active: version === 1, state: 'draft', url: `http://127.0.0.1:7777/apps/${name}/`, body: c.body }
  s.published.push(made)
  return { status: 201, body: made }
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
    const query: Record<string, string> = {}
    u.searchParams.forEach((v, k) => { query[k] = v })
    const raw = typeof init.body === 'string' ? init.body : init.body ? atob(init.body.base64) : ''
    const call: Call = { method: init.method ?? 'GET', path: u.pathname, body: raw ? (JSON.parse(raw) as Json) : {}, bearer, query }
    s.calls.push(call)
    if (u.host === '127.0.0.1:7777') {
      if (s.rrotorDown) throw new Error('ECONNREFUSED')
      const r = rrotorRoute(s, call)
      return { status: r.status, ok: r.status < 300, headers: {}, text: JSON.stringify(r.body) }
    }
    const r = await route(s, call)
    return { status: r.status, ok: r.status < 300, headers: {}, text: r.status === 204 ? "" : JSON.stringify(r.body) }
  }

  return { s, fetch, TOKEN }
}
