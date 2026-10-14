// The sign-in card's logic, with no Node in it: the device flow (RFC 8628)
// against the Glyphh server, one sign-in pending at a time, polled no faster
// than the server allows, the install kept by whoever is handed `keep`.
// server.ts wires it to Node; tests/glyphh-mcp.test.ts drives it with fakes.

export type Reply = { status: number; text: string }
export type Install = { install_id: string; token: string }

export type Deps = {
  server: string
  /** One HTTP call; throws when the server cannot be reached. */
  http(method: string, url: string, body?: unknown, bearer?: string): Promise<Reply>
  now(): number
  install(): Promise<Install | undefined>
  keep(install: Install): Promise<void>
  device: { name: string; surface: 'desktop' | 'cli'; mod_version: string }
  /** sha256 of this machine's stable id (hooks/glyphh/machine.ts), sent as machine_id. */
  machineId(): Promise<string>
}

export type Pending = {
  device_code: string
  user_code: string
  verification_uri: string
  verification_uri_complete: string
  interval: number
  expires_at: number
  next_poll_at: number
}

/** What the card draws (the tool's structured content). */
export type Card =
  | { state: 'pending'; user_code: string; verification_uri: string; verification_uri_complete: string; expires_at: number }
  | { state: 'signed_in'; email: string }

export type Status = {
  status: 'pending' | 'signed_in' | 'expired' | 'denied' | 'error'
  email?: string
  message?: string
}

type Json = Record<string, unknown>

const parse = (text: string): Json => {
  try {
    const v = JSON.parse(text) as unknown
    return v && typeof v === 'object' ? (v as Json) : {}
  } catch {
    return {}
  }
}

/** A refusal's code: `{"error": {"code"}}`, or RFC 8628's `{"error": "code"}`. */
export function errorCode(r: Reply): string {
  const err = parse(r.text).error
  const code = typeof err === 'string' ? err : String((err as Json | undefined)?.code ?? `http_${r.status}`)
  return code.toLowerCase().replace(/^e_/, '')
}

export class SignIn {
  pending: Pending | undefined
  private email: string | undefined

  constructor(private readonly d: Deps) {}

  /** One call; a server that cannot be reached is said so. */
  private async call(method: string, path: string, body?: unknown, bearer?: string): Promise<Reply> {
    try {
      return await this.d.http(method, `${this.d.server}${path}`, body, bearer)
    } catch {
      throw new Error(`Cannot reach the Glyphh server at ${this.d.server}.`)
    }
  }

  /** The signed-in account's email, per /v1/me; undefined when not signed in. */
  async whoami(token?: string): Promise<string | undefined> {
    const bearer = token ?? (await this.d.install())?.token
    if (!bearer) return undefined
    const r = await this.call('GET', '/v1/me', undefined, bearer)
    if (r.status === 401) return undefined
    if (r.status >= 400) throw new Error(`The Glyphh server refused /v1/me (${errorCode(r)}).`)
    const me = parse(r.text)
    const user = (me.user ?? me) as Json
    return String(user.email ?? 'your Glyphh account')
  }

  /** The tool: signed in already, the sign-in waiting, or a new one. */
  async start(): Promise<Card> {
    if (this.pending && this.d.now() < this.pending.expires_at) {
      const s = await this.status()
      if (s.status === 'signed_in') return { state: 'signed_in', email: s.email ?? '' }
      if (s.status === 'pending' && this.pending) return this.card(this.pending)
    }
    const email = await this.whoami()
    if (email) return { state: 'signed_in', email }
    return this.card(await this.begin())
  }

  private card(p: Pending): Card {
    const { user_code, verification_uri, verification_uri_complete, expires_at } = p
    return { state: 'pending', user_code, verification_uri, verification_uri_complete, expires_at }
  }

  private async begin(): Promise<Pending> {
    const body = { ...this.d.device, machine_id: await this.d.machineId() }
    const r = await this.call('POST', '/v1/device/code', body)
    if (r.status >= 400) throw new Error(`The Glyphh server would not start a sign-in (${errorCode(r)}).`)
    const b = parse(r.text)
    const interval = Number(b.interval ?? 5)
    const now = this.d.now()
    this.email = undefined
    this.pending = {
      device_code: String(b.device_code),
      user_code: String(b.user_code),
      verification_uri: String(b.verification_uri),
      verification_uri_complete: String(b.verification_uri_complete ?? b.verification_uri),
      interval,
      expires_at: now + Number(b.expires_in ?? 600) * 1000,
      next_poll_at: now + interval * 1000,
    }
    return this.pending
  }

  /** The app's poll: asks the server at most once per interval. */
  async status(): Promise<Status> {
    const p = this.pending
    if (!p) return this.email ? { status: 'signed_in', email: this.email } : { status: 'expired' }
    const now = this.d.now()
    if (now >= p.expires_at) return this.end({ status: 'expired' })
    if (now < p.next_poll_at) return { status: 'pending' }
    let r: Reply
    try {
      r = await this.call('POST', '/v1/device/token', { device_code: p.device_code })
    } catch {
      p.next_poll_at = now + p.interval * 1000 // the server is away for now: try again later
      return { status: 'pending' }
    }
    const b = parse(r.text)
    if (r.status < 400 && typeof b.access_token === 'string') return this.done(String(b.install_id ?? ''), b.access_token)
    return this.answer(p, r.status < 400 ? 'authorization_pending' : errorCode(r))
  }

  private answer(p: Pending, code: string): Status {
    if (code === 'slow_down') p.interval += 5
    if (code === 'authorization_pending' || code === 'slow_down') {
      p.next_poll_at = this.d.now() + p.interval * 1000
      return { status: 'pending' }
    }
    if (code === 'expired_token') return this.end({ status: 'expired' })
    if (code === 'access_denied') return this.end({ status: 'denied' })
    return this.end({ status: 'error', message: `The sign-in failed (${code}).` })
  }

  private end(s: Status): Status {
    this.pending = undefined
    return s
  }

  private async done(install_id: string, token: string): Promise<Status> {
    await this.d.keep({ install_id, token })
    this.pending = undefined
    this.email = (await this.whoami(token).catch(() => undefined)) ?? 'your Glyphh account'
    return { status: 'signed_in', email: this.email }
  }
}

/** The text a host without cards shows, and the model reads. */
export function cardText(c: Card): string {
  if (c.state === 'signed_in') return `Signed in as ${c.email}.`
  return [
    `To sign in to Glyphh, open ${c.verification_uri_complete} and approve the code ${c.user_code}.`,
    `(Or go to ${c.verification_uri} and enter the code.) The sign-in card shows when it is done;`,
    'without the card, call glyphh_sign_in again once approved to finish.',
  ].join(' ')
}
