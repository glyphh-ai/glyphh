// Reading the server's answers loosely: a field may sit at the top or under
// its object (`me.user.name` or `me.name`), so the panels survive small
// differences in the server's shapes.
import type { Json } from '../../types'

export const obj = (v: unknown): Json => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Json) : {})
export const str = (v: unknown, fallback = ''): string => (v === undefined || v === null ? fallback : String(v))

export const userOf = (me: Json | null): Json => obj(me?.user ?? me)
export const orgOf = (me: Json | null): Json => obj(me?.org)
export const planOf = (me: Json | null): Json => obj(me?.plan ?? orgOf(me).plan)
/** The org's Ada Cloud use (/v1/me's `cloud`): `{plan, month, resets_at, models,
 *  precedents: {used, max}, requests: {used, max, over, overage}, requests_per_second}`. */
export const cloudOf = (me: Json | null): Json => obj(me?.cloud)

export const isAdmin = (me: Json | null): boolean => str(userOf(me).role ?? me?.role ?? orgOf(me).role) === 'admin'

export const planName = (me: Json | null): string => {
  const p = me?.plan ?? orgOf(me).plan
  if (typeof p === 'string') return p
  const plan = obj(p)
  return `${str(plan.name, 'unknown')}${plan.version !== undefined ? ` (v${str(plan.version)})` : ''}`
}

/** A cap as read: null is by contract (Enterprise), else the count. */
export const many = (v: unknown): string => (v === null || v === undefined ? 'by contract' : count(v))

/** An id from an item that may call it `id`, `user_id` or `install_id`. */
export const idOf = (item: Json, ...keys: string[]): string => str([...keys, 'id'].map(k => item[k]).find(v => v !== undefined))

export const isSubscribed = (me: Json | null): boolean => {
  const org = orgOf(me)
  if (org.stripe_subscription_id || org.subscribed === true) return true
  return ['active', 'trialing', 'past_due'].includes(str(org.billing_status))
}

/** Cents as dollars: whole dollars when there are no cents, e.g. $99 or $12.34. */
export const money = (cents: number): string => `$${(cents / 100).toFixed(cents % 100 ? 2 : 0)}`

/** A count with thousands marked: 100000 is 100,000. */
export const count = (n: unknown): string => (typeof n === 'number' ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',') : str(n, '0'))

/** Bought with Stripe Checkout; Enterprise is not, it is by contract. */
export const isSelfServe = (plan: Json): boolean => plan.self_serve !== false

/** A plan's price as GET /v1/plans says it: $99/month, $0, or By contract
 *  (Enterprise's price is each customer's own and is never shown). */
export const priceText = (plan: Json): string => {
  const cents = plan.price_cents
  if (typeof cents !== 'number') return 'By contract'
  return plan.interval === 'month' || plan.interval === 'year' ? `${money(cents)}/${plan.interval}` : money(cents)
}

/** A plan's Ada Cloud caps as GET /v1/plans says them (`cloud`), e.g.
 *  100,000 precedents · 1,000,000 reads a month · then $1 per 10,000; none
 *  past the month where it meters none; by contract where it caps none. */
export const cloudLimits = (plan: Json): string => {
  const c = obj(plan.cloud)
  if (c.precedents == null && c.requests_per_month == null) return 'by contract'
  const rate = c.overage_cents_per_10k
  const past = c.overage && typeof rate === 'number' ? `then ${money(rate)} per 10,000` : 'none past the month'
  return `${many(c.precedents)} precedents · ${many(c.requests_per_month)} reads a month · ${past}`
}
