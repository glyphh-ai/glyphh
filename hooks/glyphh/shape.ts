// Reading the server's answers loosely: a field may sit at the top or under
// its object (`me.user.name` or `me.name`), so the panels survive small
// differences in the server's shapes.
import type { Json } from '../../types'

export const obj = (v: unknown): Json => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Json) : {})
export const str = (v: unknown, fallback = ''): string => (v === undefined || v === null ? fallback : String(v))

export const userOf = (me: Json | null): Json => obj(me?.user ?? me)
export const orgOf = (me: Json | null): Json => obj(me?.org)
export const planOf = (me: Json | null): Json => obj(me?.plan ?? orgOf(me).plan)
export const limitsOf = (me: Json | null): Json => obj(planOf(me).limits ?? me?.limits)
export const usedOf = (me: Json | null): Json => obj(me?.used ?? me?.usage)

export const isAdmin = (me: Json | null): boolean => str(userOf(me).role ?? me?.role ?? orgOf(me).role) === 'admin'

export const planName = (me: Json | null): string => {
  const p = me?.plan ?? orgOf(me).plan
  if (typeof p === 'string') return p
  const plan = obj(p)
  return `${str(plan.name, 'unknown')}${plan.version !== undefined ? ` (v${str(plan.version)})` : ''}`
}

/** A limit as read: empty is unlimited. */
export const limitText = (v: unknown): string => (v === null || v === undefined ? 'unlimited' : String(v))

/** An id from an item that may call it `id`, `user_id` or `install_id`. */
export const idOf = (item: Json, ...keys: string[]): string => str([...keys, 'id'].map(k => item[k]).find(v => v !== undefined))

export const isSubscribed = (me: Json | null): boolean => {
  const org = orgOf(me)
  if (org.stripe_subscription_id || org.subscribed === true) return true
  return ['active', 'trialing', 'past_due'].includes(str(org.billing_status))
}

export const priceText = (plan: Json): string => {
  const cents = plan.seat_price_cents ?? obj(plan.version).seat_price_cents
  if (typeof cents === 'number') return `$${(cents / 100).toFixed(cents % 100 ? 2 : 0)}/seat/mo`
  return plan.price !== undefined ? str(plan.price) : ''
}
